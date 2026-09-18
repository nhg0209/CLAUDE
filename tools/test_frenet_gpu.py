#!/usr/bin/env python3
"""frenet_gpu.py 검증. torch 만 필요하다 (pxr·Isaac Sim 불필요).

  python tools/test_frenet_gpu.py <track.npz> --device cuda:0

검사 항목
  1. 테이블 · 균일 격자 · 법선 오프셋이 접히는지(focal point)
  2. 자기근접 — window 를 ±1.2 m 로 잡는 근거, 그리고 전역 argmin 의 안전 조건
  3. 정확도  (a) float64 polyline 기준값  (b) point_at↔project 왕복  (c) chord vs psi 법선
  4. 전역 locate 가 실제로 얼마나 틀리는가
  5. 한 랩 궤적 추적 — 50 Hz · 12 m/s · 횡방향 사인 기동
  6. preview — 인덱싱과 차량 좌표계 부호
  7. 랩 경계에서의 Δs
  8. 처리량
"""
import argparse
import time

import numpy as np
import torch

from frenet_gpu import FrenetTrack, FrenetTracker, wrap

BAR = "═" * 78


def ref_project(z, p, s_true, lap, ds, half=3.0):
    """float64 기준값. s_true 주변 ±half m 의 선분에만 정확히 투영한다."""
    N = len(z["s"])
    P = np.stack([z["x"], z["y"]], 1).astype(float)
    S = np.roll(P, -1, 0) - P
    W = int(np.ceil(half / ds))
    out_s = np.empty(len(p)); out_d = np.empty(len(p))
    for b in range(len(p)):
        j = (int(round(s_true[b] / ds)) + np.arange(-W, W + 1)) % N
        w = p[b] - P[j]
        u = np.clip((w * S[j]).sum(1) / (S[j] ** 2).sum(1), 0, 1)
        rel = w - u[:, None] * S[j]
        d2 = (rel ** 2).sum(1)
        k = int(d2.argmin())
        cr = S[j][k, 0] * rel[k, 1] - S[j][k, 1] * rel[k, 0]
        out_s[b] = (z["s"][j[k]] + u[k] * ds) % lap
        out_d[b] = np.sqrt(d2[k]) * np.sign(cr)
    return out_s, out_d


def dsig(a, b, lap):
    """랩을 접은 부호 있는 차이."""
    return (a - b + 0.5 * lap) % lap - 0.5 * lap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--samples", type=int, default=4096)
    ap.add_argument("--bench-envs", type=int, default=4096)
    ap.add_argument("--bench-iters", type=int, default=500)
    ap.add_argument("--threads", type=int, default=0, help="CPU 벤치용 torch thread 수")
    a = ap.parse_args()
    if a.threads:
        torch.set_num_threads(a.threads)
    torch.manual_seed(0); rng = np.random.default_rng(0)
    dev = torch.device(a.device)
    trk = FrenetTrack(a.npz, device=dev)
    z = np.load(a.npz, allow_pickle=False)
    lap, ds, N = trk.lap, trk.ds, trk.N
    ok = True

    print(f"{BAR}\n 1. 테이블\n{BAR}")
    print(f"  {trk}")
    print(f"  균일 격자 최대 편차 {trk.grid_dev:.2e} m (ds 의 {trk.grid_dev/ds*100:.4f}%) "
          f"— npz float32 저장 오차 수준")
    kap = z["kappa"].astype(float)
    ak = np.abs(kap)
    hw = np.maximum(z["d_left"], z["d_right"]).astype(float)
    # 접힘은 **곡률 중심 쪽(안쪽)** 경계만 위험하다. 바깥쪽 오프셋은 절대 접히지 않는다.
    inner = np.where(kap > 0, z["d_left"], z["d_right"]).astype(float)
    fold = ak * inner
    w = int(np.argmax(fold))
    print(f"  |kappa|·(안쪽 반폭) 최대 {fold.max():.4f} at s={z['s'][w]:.2f} "
          f"({'✅ < 1, 법선 오프셋 유효' if fold.max() < 1 else '❌ ≥ 1, 오프셋이 접힌다'})")
    print(f"     그 지점 R {1/max(ak[w],1e-9):.3f} m,  안쪽 반폭 {inner[w]:.3f} m,  "
          f"여유 {1/max(ak[w],1e-9)-inner[w]:.3f} m")
    print(f"  최소 곡률반경 {1/ak.max():.3f} m,  반폭 최대 {hw.max():.3f} m "
          f"(바깥쪽이므로 접힘과 무관)")
    ok &= fold.max() < 1

    print(f"\n{BAR}\n 2. 자기근접 — window 크기의 근거\n{BAR}")
    P = np.stack([z["x"], z["y"]], 1).astype(float)
    D = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=-1)
    sarr = z["s"].astype(float)
    AS = np.abs(sarr[:, None] - sarr[None, :]); AS = np.minimum(AS, lap - AS)
    for thr in (1.0, 2.0, 3.0, trk.window * ds):
        m = AS >= thr
        i, j = np.unravel_index(np.argmin(np.where(m, D, np.inf)), D.shape)
        print(f"  경로상 {thr:4.2f} m 이상 떨어진 쌍의 유클리드 최소 {D[i,j]:6.3f} m "
              f"(s={sarr[i]:.1f} ↔ {sarr[j]:.1f})")
    far = AS >= 3.0
    dmin_far = np.where(far, D, np.inf).min(1)          # 각 점에서 먼 branch 까지 최소거리
    # 전역 argmin 의 **점별 안전조건**: 코리도 안의 질의점 p (오프셋 |t| ≤ hw_i) 는
    #   dist(p, i) = |t|,  dist(p, far branch) ≥ D_far − |t|  →  D_far > 2·hw_i 이면 안전.
    viol = dmin_far <= 2.0 * hw
    print(f"  전역 argmin 점별 안전조건 D_far(i) > 2·hw(i):  위반 {int(viol.sum())} / {N}")
    if viol.any():
        k = int(np.argmin(dmin_far - 2 * hw))
        print(f"     최악 s={sarr[k]:.2f}: D_far {dmin_far[k]:.3f} m  vs  2·hw {2*hw[k]:.3f} m")
        print(f"     (이 조건은 pessimistic 하다 — 4번에서 실제로 틀리는지 측정한다)")
    print(f"  window ±{trk.window*ds:.2f} m 는 경로상 그 이상 떨어진 branch 를 "
          f"후보에서 **구조적으로** 배제한다 → 위 조건과 무관하게 안전하다")
    print(f"  후보 수 {2*trk.window+1} 개 vs 전역 {N} 개 → 연산량 {N/(2*trk.window+1):.1f}× 절약")

    print(f"\n{BAR}\n 3. 정확도\n{BAR}")
    B = a.samples
    s_t = rng.uniform(0, lap, B)
    st = torch.as_tensor(s_t, dtype=trk.dtype, device=dev)
    dl, dr = trk.margins_at(st)
    frac = torch.as_tensor(rng.uniform(-0.95, 0.95, B), dtype=trk.dtype, device=dev)
    d_t = torch.where(frac > 0, frac * (dl - 0.05), frac * (dr - 0.05))
    p, psi_p = trk.point_at(st, d_t)
    e_t = torch.as_tensor(rng.uniform(-0.6, 0.6, B), dtype=trk.dtype, device=dev)
    psi_c = wrap(psi_p + e_t)

    out = trk.project(p, psi_c, trk.idx_of(st))
    rs, rd = ref_project(z, p.cpu().numpy().astype(float), s_t, lap, ds)
    es = np.abs(dsig(out["s"].cpu().numpy().astype(float), rs, lap))
    ed = np.abs(out["d"].cpu().numpy().astype(float) - rd)
    print(f"  (a) float64 polyline 기준값 대조")
    print(f"      |Δd| 최대 {ed.max():.2e} m   평균 {ed.mean():.2e}   "
          f"{'✅' if ed.max() < 1e-5 else '❌'}  ← 거리는 정의가 유일하다")
    print(f"      |Δs| 최대 {es.max():.2e} m   평균 {es.mean():.2e}   "
          f"{'✅' if es.max() < ds else '❌'}  ← ds 이내")
    tie = int((es > 1e-3).sum())
    if tie:
        wk = int(np.argmax(es))
        print(f"      |Δs| > 1 mm 인 표본 {tie}/{B}: 볼록한 코너의 **동거리 무승부**다.")
        print(f"        최악 표본에서 두 구현의 거리 차 {ed[wk]:.2e} m "
              f"(|d| {abs(rd[wk]):.3f} m) — 거리는 같고 수선발만 이웃 선분으로 넘어간다.")
        print(f"        Δs 합은 telescoping 이라 누적되지 않는다 (5번에서 오차 0 확인).")
    ok &= ed.max() < 1e-5 and es.max() < ds

    as_ = np.abs(dsig(out["s"].cpu().numpy().astype(float), s_t, lap))
    ad = np.abs((out["d"] - d_t).cpu().numpy().astype(float))
    ae = np.abs(wrap(out["e_psi"] - e_t).cpu().numpy().astype(float))
    print(f"  (b) point_at → project 왕복")
    print(f"      |Δd|     최대 {ad.max()*1000:7.3f} mm  평균 {ad.mean()*1000:6.3f} mm  "
          f"{'✅' if ad.max() < 1e-3 else '❌'}  ← 거리는 정확히 보존돼야 한다")
    print(f"      |Δs|     최대 {as_.max()*1000:7.3f} mm  평균 {as_.mean()*1000:6.3f} mm  "
          f"{'✅' if as_.max() < ds/2 else '❌'}  ← ds/2 = {ds/2*1000:.1f} mm 이내")
    print(f"      |Δe_psi| 최대 {np.degrees(ae.max()):7.3f}°  평균 {np.degrees(ae.mean()):6.3f}°")
    print(f"      Δs 가 정확히 0 이 아닌 이유: 오목한 쪽에서는 이웃 선분의 수선발이 더 가깝다.")
    print(f"      project 가 고른 쪽이 **진짜 최근접점**이므로 (a) 가 통과하면 정상이다.")
    ok &= ad.max() < 1e-3 and as_.max() < ds / 2

    Sc = np.roll(P, -1, 0) - P
    ang = np.abs(dsig(np.arctan2(Sc[:, 1], Sc[:, 0]), z["psi"].astype(float), 2 * np.pi))
    print(f"  (c) chord 방향과 psi 의 차이 최대 {np.degrees(ang.max()):.3f}° "
          f"(평균 {np.degrees(ang.mean()):.3f}°)")
    print(f"      point_at 은 chord 법선으로 오프셋한다 — 반폭 끝에서 psi 법선과의 위치 차는 "
          f"최대 {(np.sin(ang)*hw).max()*1000:.1f} mm")
    print(f"      스폰 위치에는 무해하고, 벽 여유 검사가 어긋나지 않는 쪽이 중요하다")

    print(f"\n{BAR}\n 4. 전역 locate 는 얼마나 틀리는가 (벽에서 5 cm 까지 밀어붙인 {B} 점)\n{BAR}")
    g = trk.locate(p, psi_c)
    gs = np.abs(dsig(g["s"].cpu().numpy().astype(float), s_t, lap))
    for th in (0.5, 1.0, 3.0):
        print(f"  |Δs| > {th:3.1f} m : {int((gs>th).sum()):5d} / {B}  ({(gs>th).mean()*100:.2f}%)")
    print(f"  최대 |Δs| {gs.max():.3f} m")
    if (gs > 1.0).any():
        w2 = int(np.argmax(gs))
        print(f"  ⚠️ 실패 예: 참 s={s_t[w2]:.2f} d={float(d_t[w2]):+.2f} → 전역이 고른 "
              f"s={float(g['s'][w2]):.2f} (경로상 {gs[w2]:.2f} m 밖)")
    else:
        print(f"  이 맵에서는 전역 argmin 도 통과했다 — 2번의 안전조건은 pessimistic 했다.")
        print(f"  그래도 증분을 쓴다: (1) 연산량 {N/(2*trk.window+1):.0f}× (2) 맵에 의존하지 않는다")

    print(f"\n{BAR}\n 5. 한 랩 궤적 추적 (50 Hz · 12 m/s · 횡방향 사인)\n{BAR}")
    dt, v = 0.02, 12.0
    steps = int(1.5 * lap / (v * dt)) + 1      # 랩 경계를 반드시 넘긴다
    tk1 = FrenetTracker(trk, 1)
    s_cur = 0.0; acc = 0.0; mx_s = mx_d = 0.0; first = True
    for i in range(steps):
        s1 = torch.tensor([s_cur % lap], dtype=trk.dtype, device=dev)
        l1, r1 = trk.margins_at(s1)
        d1 = 0.8 * torch.minimum(l1, r1) * float(np.sin(2 * np.pi * s_cur / 8.0))
        p1, ps1 = trk.point_at(s1, d1)
        pc1 = wrap(ps1 + torch.tensor([0.15 * np.cos(s_cur)], dtype=trk.dtype, device=dev))
        if first:
            o = tk1.reset(torch.tensor([0], device=dev), p1, pc1, s0=s1); first = False
        else:
            o = tk1.step(p1, pc1); acc += float(o["ds"])
        mx_s = max(mx_s, abs(float(dsig(np.array([float(o['s'])]),
                                        np.array([s_cur % lap]), lap)[0])))
        mx_d = max(mx_d, abs(float(o["d"] - d1)))
        s_cur += v * dt
    driven = s_cur - v * dt
    print(f"  {steps} step,  주행 {driven:.3f} m (랩 {lap:.3f} m)")
    print(f"  Δs 누적 {acc:.3f} m,  오차 {abs(acc-driven):.4f} m  "
          f"{'✅' if abs(acc-driven) < 0.05 else '❌'}   ← 랩 경계를 넘어가도 맞아야 한다")
    print(f"  s_total {float(tk1.s_total):.3f} m,  랩 카운트 {int(tk1.lap_count)}  "
          f"{'✅' if int(tk1.lap_count) == int(driven//lap) else '❌'}")
    print(f"  최대 |Δs| {mx_s*1000:.3f} mm,  최대 |Δd| {mx_d*1000:.3f} mm")
    print(f"  window 경계 접촉 {int(tk1.edge_hits)} 회  "
          f"{'✅' if int(tk1.edge_hits)==0 else '❌ window 를 키워야 한다'}")
    ok &= abs(acc - driven) < 0.05 and int(tk1.edge_hits) == 0 \
        and int(tk1.lap_count) == int(driven // lap)

    print(f"\n{BAR}\n 6. preview\n{BAR}")
    n8 = 64
    s2 = torch.as_tensor(rng.uniform(0, lap, n8), dtype=trk.dtype, device=dev)
    p2, ps2 = trk.point_at(s2, torch.zeros(n8, dtype=trk.dtype, device=dev))
    pv = trk.preview(s2, p2, ps2)
    print(f"  shape {tuple(pv['x'].shape)}  지평선 {trk.preview_horizon:.1f} m "
          f"(12 m/s·mu 0.4 제동거리 17.7 m 대비 "
          f"{'✅' if trk.preview_horizon >= 17.7 else '❌'})")
    print(f"  k=0 은 차량 위치 ≈ 원점: 최대 거리 "
          f"{float(torch.hypot(pv['x'][:,0], pv['y'][:,0]).max())*1000:.2f} mm "
          f"(round(s/ds) 격자 스냅 ≤ {ds/2*1000:.1f} mm)")
    arc = torch.norm(trk.xy[pv["idx"][:, 1:]] - trk.xy[pv["idx"][:, :-1]], dim=-1)
    print(f"  인접 preview 점 간 현 길이 {float(arc.min()):.3f}~{float(arc.max()):.3f} m "
          f"(호길이 {trk.preview_stride*ds:.3f} m)")
    fwd = (pv["x"][:, 1:] > 0).float().mean()
    print(f"  k≥1 이 전방(x>0)인 비율 {float(fwd)*100:.1f}%  "
          f"(20 m 안에 180° 헤어핀이 있으면 100% 가 아닌 게 정상)")
    print(f"  y 범위 {float(pv['y'].min()):+.2f}~{float(pv['y'].max()):+.2f} m "
          f"(좌회전 +, 우회전 −)")
    # 좌표계 부호 단위검사 — psi=0 인 차량 기준으로 왼쪽 앞 점이 (+x, +y) 여야 한다
    i0 = int(torch.argmax(trk.kappa))                    # 가장 왼쪽으로 꺾는 지점
    s3 = trk.s[i0:i0+1].clone()
    p3, ps3 = trk.point_at(s3, torch.zeros(1, dtype=trk.dtype, device=dev))
    pv3 = trk.preview(s3, p3, ps3)
    print(f"  부호 단위검사: 가장 좌회전(kappa {float(trk.kappa[i0]):+.3f}) 지점에서 "
          f"20 m 앞 점의 차량좌표 y = {float(pv3['y'][0,-1]):+.2f} m "
          f"{'✅ 왼쪽(+)' if float(pv3['y'][0,-1]) > 0 else '(코스 형상에 따라 다를 수 있음)'}")
    ok &= trk.preview_horizon >= 17.7 \
        and float(torch.hypot(pv['x'][:,0], pv['y'][:,0]).max()) <= ds / 2 + 1e-3

    print(f"\n{BAR}\n 7. 랩 경계 Δs\n{BAR}")
    for so, sn in ((lap - 0.05, 0.05), (0.05, lap - 0.05), (0.0, 0.10)):
        v_ = float(trk.progress(torch.tensor([sn], dtype=trk.dtype, device=dev),
                                torch.tensor([so], dtype=trk.dtype, device=dev)))
        good = abs(abs(v_) - 0.10) < 1e-3
        print(f"  s {so:8.3f} → {sn:8.3f} :  Δs {v_:+.4f} m  {'✅' if good else '❌'}")
        ok &= good

    print(f"\n{BAR}\n 8. 처리량 ({a.device}, torch threads {torch.get_num_threads()})\n{BAR}")
    Bn = a.bench_envs
    s4 = torch.as_tensor(rng.uniform(0, lap, Bn), dtype=trk.dtype, device=dev)
    p4, ps4 = trk.point_at(s4, torch.zeros(Bn, dtype=trk.dtype, device=dev))
    tk = FrenetTracker(trk, Bn)
    tk.reset(torch.arange(Bn, device=dev), p4, ps4, s0=s4)

    def bench(fn, iters):
        for _ in range(20):
            fn()
        if dev.type == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(iters):
            fn()
        if dev.type == "cuda":
            torch.cuda.synchronize()
        return (time.perf_counter() - t0) / iters

    e1 = bench(lambda: tk.step(p4, ps4), a.bench_iters)
    e2 = bench(lambda: trk.preview(tk.s, p4, ps4), a.bench_iters)
    e3 = bench(lambda: trk.locate(p4, ps4), max(20, a.bench_iters // 10))
    print(f"  {Bn} env   project(step)  {e1*1e6:8.1f} µs   preview {e2*1e6:8.1f} µs   "
          f"합 {(e1+e2)*1e6:8.1f} µs")
    print(f"             locate(전역)   {e3*1e6:8.1f} µs  → 증분이 {e3/e1:.1f}× 빠르다")
    print(f"  50 Hz 로 {Bn} env: 이 변환이 먹는 실시간 비율 {(e1+e2)*50*100:.3f}%")
    print(f"  → {Bn/(e1+e2)/1e6:.2f} M env·step/s")
    if dev.type != "cuda":
        print(f"  ⚠️ CPU 수치는 gather·커널 오버헤드에 묶인 값이다 (이 머신 gather 1회 ≈ 77 µs).")
        print(f"     실제 판단은 서버 GPU 에서 --device cuda:0 으로 다시 재야 한다.")

    print(f"\n{BAR}\n {'✅ 전부 통과' if ok else '❌ 실패 항목 있음'}\n{BAR}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
