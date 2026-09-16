#!/usr/bin/env python3
"""트랙 USD + reference path 생성. unicorn 스택의 global_waypoints.json 이 입력.

  # 컨테이너 (Isaac Sim 의 pxr)
  cd /workspace/IsaacLab
  ./isaaclab.sh -p /workspace/tools/gen_track.py /workspace/maps/ifac_0824_mapping_3

  # 독립 실행
  pip install usd-core && python gen_track.py <map_dir>

★ 경계를 어떻게 얻는가 ─────────────────────────────────────────────────
trackbounds_markers 는 3404개(f 맵 기준)의 **순서 없는 sphere marker** 라 메시로
못 쓴다. 대신 IQP raceline 의 (x, y, psi, d_left, d_right) 로 복원한다:

    left  = p + d_left  * n,    right = p - d_right * n,   n = (-sin psi, cos psi)

두 맵에서 실측 검증했다 — 폐곡선 gap 0.0000, 자기교차 0건, psi 방향 100% 일치.
centerline 은 쓰면 안 된다 (gap 0.26~0.47 m, 자기교차 35~47건).
SP 는 더 심하다 (|kappa| 최대 213 = R 0.005 m).

★ 벽 collision ────────────────────────────────────────────────────────
approximation = "none" (triangle mesh) 를 반드시 쓴다.
convexHull 로 하면 42 m 폐루프의 convex hull = **트랙 전체를 메우는 덩어리**가 된다.
PhysX 의 triangle mesh collider 는 정적 바디만 지원하므로 RigidBodyAPI 를 붙이지 않는다.

★ 벽을 닫힌 volume 으로 만드는 이유 ────────────────────────────────────
zero-thickness 면 법선 방향에 따라 한쪽에서만 충돌한다. 닫힌 volume 은 그 문제가 없다.
두께 0.05 m 는 안전하다 — min(R - inner_offset) 이 0.88~1.00 m 로 확인됐다.
"""

import argparse
import json
import os
import sys

import numpy as np

_NEED_APP = False
try:
    from pxr import Gf, Usd, UsdGeom, UsdPhysics  # noqa: F401
except ModuleNotFoundError:
    _NEED_APP = True

if _NEED_APP:
    try:
        from isaaclab.app import AppLauncher
    except ModuleNotFoundError:
        sys.exit("pxr 도 isaaclab 도 없다. `pip install usd-core` 하거나 `./isaaclab.sh -p` 로 실행하라.")
    _p = argparse.ArgumentParser(add_help=False)
    AppLauncher.add_app_launcher_args(_p)
    _k, _rest = _p.parse_known_args()
    _k.headless = True
    _app = AppLauncher(_k)
    _sim_app = _app.app
    sys.argv = [sys.argv[0]] + _rest
    from pxr import Gf, Usd, UsdGeom, UsdPhysics  # noqa: F811
else:
    _sim_app = None

BAR = "═" * 78


# ══ 기하 ═══════════════════════════════════════════════════════════════
def load_raceline(map_dir):
    with open(os.path.join(map_dir, "global_waypoints.json")) as f:
        d = json.load(f)
    w = d["global_traj_wpnts_iqp"]["wpnts"]
    a = {k: np.array([p[k] for p in w], dtype=np.float64)
         for k in ("s_m", "x_m", "y_m", "psi_rad", "kappa_radpm", "vx_mps",
                   "ax_mps2", "d_left", "d_right")}
    # 마지막 점이 첫 점과 중복이면(실측: 거리 0.0000) 떨어낸다.
    # 남겨두면 메시에 퇴화(degenerate) 면이 생긴다.
    dup = np.hypot(a["x_m"][0] - a["x_m"][-1], a["y_m"][0] - a["y_m"][-1]) < 1e-6
    if dup:
        a = {k: v[:-1] for k, v in a.items()}
    lap = float(d["global_traj_wpnts_iqp"]["wpnts"][-1]["s_m"])
    return a, lap, dup, d


def boundaries(a):
    nx, ny = -np.sin(a["psi_rad"]), np.cos(a["psi_rad"])
    L = np.stack([a["x_m"] + a["d_left"] * nx, a["y_m"] + a["d_left"] * ny], 1)
    R = np.stack([a["x_m"] - a["d_right"] * nx, a["y_m"] - a["d_right"] * ny], 1)
    return L, R, np.stack([nx, ny], 1)


def wall_mesh(B, out_dir, height, thick):
    """닫힌 폐루프 경계 B(N,2) 를 두께 있는 벽 volume 으로. out_dir(N,2) 는 트랙 반대편 단위벡터."""
    N = len(B)
    O = B + thick * out_dir
    V = np.concatenate([
        np.c_[B, np.zeros(N)],                       # 0     : inner bottom
        np.c_[B, np.full(N, height)],                # N     : inner top
        np.c_[O, np.zeros(N)],                       # 2N    : outer bottom
        np.c_[O, np.full(N, height)],                # 3N    : outer top
    ])
    IB, IT, OB, OT = 0, N, 2 * N, 3 * N
    F = []
    for i in range(N):
        j = (i + 1) % N
        quads = [
            (IB + i, IB + j, IT + j, IT + i),   # 안쪽 면 (트랙 쪽)
            (OB + j, OB + i, OT + i, OT + j),   # 바깥 면
            (IT + i, IT + j, OT + j, OT + i),   # 윗면
            (IB + j, IB + i, OB + i, OB + j),   # 아랫면
        ]
        for q in quads:
            F.append((q[0], q[1], q[2]))
            F.append((q[0], q[2], q[3]))
    F = np.array(F, dtype=np.int64)
    # 부호 있는 부피로 법선 방향을 판정하고, 안쪽을 향하면 전부 뒤집는다.
    # 수동으로 winding 을 따지는 대신 기하로 검증한다.
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    vol = float(np.einsum("ij,ij->i", p0, np.cross(p1, p2)).sum() / 6.0)
    if vol < 0:
        F = F[:, ::-1].copy()
        vol = -vol
    return V, F, vol


def watertight(F):
    """모든 유향 간선이 정확히 한 번씩, 그리고 반대 방향도 한 번씩 나타나는가."""
    from collections import Counter
    e = Counter()
    for a, b, c in F:
        e[(a, b)] += 1; e[(b, c)] += 1; e[(c, a)] += 1
    bad_dup = sum(1 for v in e.values() if v != 1)
    bad_pair = sum(1 for (a, b) in e if e.get((b, a), 0) != 1)
    return bad_dup, bad_pair


def surface_mesh(L, R):
    """좌우 경계 사이를 덮는 시각용 바닥 리본 (collision 없음)."""
    N = len(L)
    V = np.concatenate([np.c_[L, np.zeros(N)], np.c_[R, np.zeros(N)]])
    F = []
    for i in range(N):
        j = (i + 1) % N
        F.append((i, N + i, N + j))
        F.append((i, N + j, j))
    return V, np.array(F, dtype=np.int64)


# ══ USD ════════════════════════════════════════════════════════════════
def add_mesh(stage, path, V, F, collision):
    m = UsdGeom.Mesh.Define(stage, path)
    m.GetPointsAttr().Set([Gf.Vec3f(*map(float, v)) for v in V])
    m.GetFaceVertexIndicesAttr().Set([int(i) for t in F for i in t])
    m.GetFaceVertexCountsAttr().Set([3] * len(F))
    m.GetExtentAttr().Set([Gf.Vec3f(*map(float, V.min(0))), Gf.Vec3f(*map(float, V.max(0)))])
    m.CreateSubdivisionSchemeAttr().Set("none")
    if collision:
        UsdPhysics.CollisionAPI.Apply(m.GetPrim())
        mc = UsdPhysics.MeshCollisionAPI.Apply(m.GetPrim())
        # ★ convexHull 이면 폐루프의 convex hull = 트랙을 메우는 덩어리가 된다
        mc.CreateApproximationAttr().Set("none")
    return m


def main():
    ap = argparse.ArgumentParser(description="트랙 USD + reference path 생성")
    ap.add_argument("map_dir", help="global_waypoints.json 이 있는 디렉터리")
    ap.add_argument("-o", "--out-dir", default=None, help="출력 디렉터리 (기본: map_dir)")
    ap.add_argument("--height", type=float, default=0.20, help="벽 높이 [m]")
    ap.add_argument("--thick", type=float, default=0.05, help="벽 두께 [m]")
    ap.add_argument("--preview-ds", type=float, default=0.5, help="preview 샘플 간격 [m]")
    ap.add_argument("--preview-n", type=int, default=40, help="preview 점 개수")
    ap.add_argument("--no-surface", action="store_true", help="시각용 바닥 리본 생략")
    a = ap.parse_args()

    name = os.path.basename(os.path.normpath(a.map_dir))
    out_dir = a.out_dir or a.map_dir
    os.makedirs(out_dir, exist_ok=True)
    usd_path = os.path.join(out_dir, f"track_{name}.usd")
    npz_path = os.path.join(out_dir, f"track_{name}.npz")

    wp, lap, dup, raw = load_raceline(a.map_dir)
    N = len(wp["s_m"])
    ds = lap / (N if dup else N - 1)
    L, R, nrm = boundaries(wp)

    print(f"\n{BAR}\n 1. 입력 — {name}\n{BAR}")
    print(f"  IQP raceline {N}점" + ("  (중복된 끝점 1개 제거)" if dup else ""))
    print(f"  랩 길이 {lap:.4f} m,  s 간격 {ds:.6f} m")
    print(f"  bbox  x {wp['x_m'].min():.2f}…{wp['x_m'].max():.2f}  "
          f"y {wp['y_m'].min():.2f}…{wp['y_m'].max():.2f}")
    print(f"  트랙 폭 {(wp['d_left']+wp['d_right']).min():.3f}…{(wp['d_left']+wp['d_right']).max():.3f} m")
    print(f"  최소 곡률반경 {1/np.abs(wp['kappa_radpm']).max():.3f} m")

    print(f"\n{BAR}\n 2. 경계 복원 검증\n{BAR}")
    # 끝점을 떨어냈으므로 마지막→첫점 간격은 "다른 구간들과 비슷해야" 정상이다.
    # 경계는 raceline 에서 offset 되어 있어 간격이 0.09~0.24 m 로 변한다 —
    # ds(0.0999)와 비교하면 안 된다.
    def wrap_ok(P):
        seg = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)
        return seg[-1], seg[:-1].max(), seg[-1] <= seg[:-1].max() * 1.5
    gapL, maxL, okL = wrap_ok(L); gapR, maxR, okR = wrap_ok(R)
    Rc = np.where(np.abs(wp["kappa_radpm"]) > 1e-9,
                  1 / np.maximum(np.abs(wp["kappa_radpm"]), 1e-9), np.inf)
    inner = np.where(wp["kappa_radpm"] > 0, wp["d_left"], wp["d_right"])
    fold = (inner + a.thick >= Rc).sum()
    print(f"  마지막→첫점 간격  L {gapL:.4f} (다른 구간 최대 {maxL:.4f})  "
          f"{'✅' if okL else '⚠️'}")
    print(f"                    R {gapR:.4f} (다른 구간 최대 {maxR:.4f})  "
          f"{'✅' if okR else '⚠️'}")
    print(f"  자기교차 (두께 {a.thick} 포함)  {fold} / {N}   "
          f"{'✅ 없음' if fold == 0 else '❌ 있음 — --thick 을 줄여라'}")
    print(f"  여유 min(R − offset)      {(Rc - inner).min():.4f} m")
    ok = (fold == 0) and okL and okR

    print(f"\n{BAR}\n 3. 벽 메시\n{BAR}")
    meshes = {}
    for nm, B, od in (("left", L, nrm), ("right", R, -nrm)):
        V, F, vol = wall_mesh(B, od, a.height, a.thick)
        bd, bp = watertight(F)
        print(f"  {nm:<6} 정점 {len(V):>6,}  삼각형 {len(F):>6,}  부피 {vol:8.4f} m³")
        print(f"         watertight: 중복간선 {bd}  짝없는간선 {bp}   "
              f"{'✅' if bd == 0 and bp == 0 else '❌ 메시가 닫히지 않았다'}")
        ok &= (bd == 0 and bp == 0)
        meshes[nm] = (V, F)
    # 이론 부피와 대조 — 둘레 × 높이 × 두께
    peri = np.linalg.norm(np.diff(np.vstack([L, L[:1]]), axis=0), axis=1).sum()
    print(f"  좌측 둘레 {peri:.2f} m → 이론 부피 {peri*a.height*a.thick:.4f} m³ (곡률로 약간 차이)")

    print(f"\n{BAR}\n 4. USD 작성\n{BAR}")
    if os.path.exists(usd_path):
        os.remove(usd_path)
    stage = Usd.Stage.CreateNew(usd_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/track")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.Scope.Define(stage, "/track/walls")
    for nm, (V, F) in meshes.items():
        add_mesh(stage, f"/track/walls/{nm}", V, F, collision=True)
        print(f"  /track/walls/{nm:<6} CollisionAPI + approximation='none' (정적)")
    if not a.no_surface:
        SV, SF = surface_mesh(L, R)
        add_mesh(stage, "/track/surface", SV, SF, collision=False)
        print(f"  /track/surface       시각용. collision 없음 ({len(SF):,} 삼각형)")
    stage.GetRootLayer().Save()
    print(f"  ✅ {usd_path}  ({os.path.getsize(usd_path):,} bytes)")

    print(f"\n{BAR}\n 5. reference path (.npz)\n{BAR}")
    stride = int(round(a.preview_ds / ds))
    np.savez(npz_path,
             s=wp["s_m"].astype(np.float32), x=wp["x_m"].astype(np.float32),
             y=wp["y_m"].astype(np.float32), psi=wp["psi_rad"].astype(np.float32),
             kappa=wp["kappa_radpm"].astype(np.float32),
             d_left=wp["d_left"].astype(np.float32), d_right=wp["d_right"].astype(np.float32),
             vx_planner=wp["vx_mps"].astype(np.float32),
             left_bound=L.astype(np.float32), right_bound=R.astype(np.float32),
             ds=np.float32(ds), lap_length=np.float32(lap),
             preview_ds=np.float32(a.preview_ds), preview_n=np.int32(a.preview_n),
             preview_stride=np.int32(stride), map_name=name)
    print(f"  ✅ {npz_path}  ({os.path.getsize(npz_path):,} bytes)")
    print(f"  s 격자가 균일({ds:.6f} m)하므로 preview 는 탐색 없이 인덱스로 뽑는다:")
    print(f"     idx = (round(s/ds) + k*{stride}) % {N},   k = 0..{a.preview_n-1}")
    print(f"     지평선 {a.preview_n*a.preview_ds:.1f} m  "
          f"(12 m/s·mu=0.4 제동거리 17.7 m 대비 {'✅' if a.preview_n*a.preview_ds>=17.7 else '❌ 부족'})")
    print(f"  ⚠️ vx_planner 는 ggv(자리표시자)에서 나온 값이다. policy 관측에 넣지 않는다.")
    print(f"     Pure Pursuit 베이스라인만 쓴다 — PP 가 저마찰에서 무너지는 이유가 이것이기 때문.")

    print(f"\n{BAR}\n 6. 스폰 후보 (직선 구간)\n{BAR}")
    HALF = 0.2255 / 2
    kap = np.abs(wp["kappa_radpm"]); mn = np.minimum(wp["d_left"], wp["d_right"])
    win = max(1, int(round(2.0 / ds)))
    km = np.array([kap[i:i + win].max() for i in range(N - win)])
    mm = np.array([mn[i:i + win].min() for i in range(N - win)])
    sel = (km < 0.10) & (mm > HALF + 0.05)
    if sel.any():
        idx = np.where(sel)[0]; runs = []; st = pv = idx[0]
        for i in idx[1:]:
            if i != pv + 1:
                runs.append((st, pv)); st = i
            pv = i
        runs.append((st, pv)); runs.sort(key=lambda r: -(r[1] - r[0]))
        b0, b1 = runs[0]; mid = (b0 + b1) // 2
        print(f"  가장 긴 직선  s {wp['s_m'][b0]:.2f}–{wp['s_m'][b1]:.2f} m "
              f"({wp['s_m'][b1]-wp['s_m'][b0]:.2f} m)")
        print(f"  ★ 테스트 스폰  s={wp['s_m'][mid]:.2f}  idx={mid}  "
              f"x={wp['x_m'][mid]:.3f} y={wp['y_m'][mid]:.3f} psi={wp['psi_rad'][mid]:.4f}")
        print(f"     d_left={wp['d_left'][mid]:.3f}  d_right={wp['d_right'][mid]:.3f}")
    lo = -(wp["d_right"] - (HALF + 0.05)); hi = wp["d_left"] - (HALF + 0.05)
    print(f"  학습용 무작위 d 범위가 유효한 지점: {(hi > lo).sum()} / {N}  "
          f"{'✅' if (hi>lo).all() else '⚠️'}  (가장 좁은 곳 {np.min(hi-lo):.3f} m)")

    print(f"\n{BAR}")
    print("  ★ 전체 통과" if ok else "  ⚠️ 위 지적 사항 확인")
    return 0 if ok else 1


if __name__ == "__main__":
    rc = main()
    if _sim_app is not None:
        _sim_app.close()
    sys.exit(rc)
