#!/usr/bin/env python3
"""비교군 어댑터 검증 — 스택 `Controller.py` 를 **수정 없이** Isaac 쪽에서 돌린다.

  python tools/test_controller_adapter.py <track.npz> --stack /home/user/unicorn-racing-stack

검사
  A. 스텁 주입으로 import·생성·1스텝 실행이 되는가
  B. reset 후 결정성 — 같은 입력이 항상 같은 (delta, speed) 를 내는가
  C. 보정 레이어 8겹이 **실제로** 출력을 바꾸는가 (shipped yaml 값 기준)
  D. lookahead 점 정의 차이 — 스택 방식 vs s+L_d 보간
  E. 종방향 base 의 kappa_eff 창 크기

★ 주석이 아니라 코드를 읽고 확인한 사실 ─────────────────────────────────
· ROS 의존은 visualization_msgs 하나뿐이지만 **converter(FrenetConverter)가 생성자 필수 인자**다.
  (Controller.py:63, 123 / 632 에서 get_frenet 호출)
· waypoint_at_distance_before_car 의 docstring 은 "frenet distance" 라고 하지만
  코드는 **폴리라인 현 길이의 누적합 + searchsorted** 다. 보간이 없어 격자로 양자화되고,
  cum_lengths[i-1] < d 이므로 **항상 d 보다 조금 짧은 점**을 돌려준다.
· calc_future_position 의 IMU 분기는 lambda_weight=gamma_weight=1.0 이라 **죽은 코드**다.
  beta_fused = beta_model, future_psi = future_psi_model 로 고정.
· start_mode 는 __init__ 에서 False 이고 Controller.py 안에서 바뀌지 않는다
  → acc_scaling / steer_scaling_for_lat_err 의 조기 return 은 발생하지 않는다.
· boost_mode / cur_state_speed 는 manager 가 외부에서 주입한다 (manager:221-222).
· 호출 간 살아남는 상태는 **4개가 아니라 아래 12개**다.
"""
import argparse
import os
import sys
import types

import numpy as np
import torch

BAR = "═" * 78

# 호출 간 살아남는 상태 — AST 로 열거하고 __init__ 를 읽어 확인한 목록
RESET_DEL = ["filtered_heading_error", "heading_error_integral", "prev_heading_error"]
RESET_SET = {
    "_speed_cmd_prev": None, "_trailing_handoff": None, "_trailing_entry": None,
    "_aeb_engaged": False, "_aeb_cycles": 0,
    "boost_mode": False, "i_gap": 0, "trailing_command": 2,
    "curr_steering_angle": 0, "current_steer_command": 0, "yaw_rate": 0,
    "speed_command": None, "curvature_waypoints": 0,
    "future_lat_err": 0.0, "future_lat_e_norm": 0.0,
}


def inject_ros_stub():
    """visualization_msgs 를 더미로 대체. Controller.py 는 MarkerArray()/Marker() 를
    무조건 만들고 속성을 대입하지만, predict_pub 이 None 이면 publish 하지 않는다."""
    class _D:
        SPHERE = 2
        def __init__(self, *a, **k): object.__setattr__(self, "_d", {})
        def __getattr__(self, n): return _D()
        def __setattr__(self, n, v): pass
        def __call__(self, *a, **k): return _D()
        def append(self, *a): pass
    m = types.ModuleType("visualization_msgs")
    msg = types.ModuleType("visualization_msgs.msg")
    msg.Marker, msg.MarkerArray = _D, _D
    m.msg = msg
    sys.modules["visualization_msgs"] = m
    sys.modules["visualization_msgs.msg"] = msg


def reset_controller(c):
    for n in RESET_DEL:
        if hasattr(c, n):
            delattr(c, n)
    for n, v in RESET_SET.items():
        setattr(c, n, v)


class NpzConverter:
    """Controller 가 요구하는 FrenetConverter 인터페이스 중 get_frenet 만."""
    def __init__(self, trk):
        self.trk = trk

    def get_frenet(self, xs, ys):
        p = torch.tensor([[float(xs[0]), float(ys[0])]], dtype=self.trk.dtype)
        o = self.trk.locate(p, torch.zeros(1, dtype=self.trk.dtype))
        return np.array([float(o["s"])]), np.array([float(o["d"])])


def local_window(z, i0, n=200):
    """스택의 local_wpnts 를 흉내 낸 9열 배열. 컬럼 정의는 manager:304-311 에서 확인."""
    N = len(z["s"])
    idx = (i0 + np.arange(n)) % N
    dl, dr = z["d_left"][idx], z["d_right"][idx]
    col3 = np.where(dl + dr != 0, np.minimum(dl, dr) / np.where(dl + dr == 0, 1, dl + dr), 0.0)
    return np.stack([z["x"][idx], z["y"][idx], z["vx_planner"][idx], col3,
                     z["s"][idx], z["kappa"][idx], z["psi"][idx],
                     np.zeros(n), np.zeros(n)], 1).astype(np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--stack", default="/home/user/unicorn-racing-stack")
    ap.add_argument("--yaml", default=None)
    a = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from frenet_gpu import FrenetTrack
    trk = FrenetTrack(a.npz, device="cpu")
    z = np.load(a.npz, allow_pickle=False)

    print(f"{BAR}\n A. 스텁 주입 · import · 생성\n{BAR}")
    inject_ros_stub()
    sys.path.insert(0, os.path.join(a.stack, "controller/controller/combined/src"))
    import Controller as Cmod
    print(f"  import Controller   ✅  ({Cmod.__file__})")

    ypath = a.yaml or os.path.join(a.stack, "stack_master/config/controller.yaml")
    import re
    P = {}
    for line in open(ypath):
        m = re.match(r"\s*([a-zA-Z_0-9]+):\s*(-?[\d.]+)\s*$", line)
        if m:
            P[m.group(1)] = float(m.group(2))
    print(f"  controller.yaml     ✅  파라미터 {len(P)} 개")

    WB = 0.33
    c = Cmod.Controller(
        t_clip_min=P["t_clip_min"], t_clip_max=P["t_clip_max"],
        m_l1=P["m_l1"], q_l1=P["q_l1"], curvature_factor=P["curvature_factor"],
        KP=P["KP"], KI=P["KI"], KD=P["KD"],
        heading_error_thres=P["heading_error_thres"], steer_gain_for_speed=P["steer_gain_for_speed"],
        future_constant=P["future_constant"], speed_lookahead=P["speed_lookahead"],
        lat_err_coeff=P["lat_err_coeff"], acc_scaler_for_steer=P["acc_scaler_for_steer"],
        dec_scaler_for_steer=P["dec_scaler_for_steer"], start_scale_speed=P["start_scale_speed"],
        end_scale_speed=P["end_scale_speed"], downscale_factor=P["downscale_factor"],
        speed_lookahead_for_steer=P["speed_lookahead_for_steer"],
        trailing_gap=P["trailing_gap"], trailing_vel_gain=P["trailing_vel_gain"],
        trailing_p_gain=P["trailing_p_gain"], trailing_i_gain=P["trailing_i_gain"],
        trailing_d_gain=P["trailing_d_gain"], blind_trailing_speed=P["blind_trailing_speed"],
        loop_rate=50.0, wheelbase=WB,
        speed_factor_for_lat_err=P["speed_factor_for_lat_err"],
        speed_factor_for_curvature=P["speed_factor_for_curvature"],
        speed_diff_thres=P["speed_diff_thres"], start_speed=P["start_speed"],
        start_curvature_factor=P["start_curvature_factor"], AEB_thres=P["AEB_thres"],
        converter=NpzConverter(trk), predict_pub=None,
        logger_info=lambda *x: None, logger_warn=lambda *x: None)
    c.l1_lat_err_cap = P["l1_lat_err_cap"]
    c.max_accel_mps2 = P["max_accel_mps2"]; c.max_decel_mps2 = P["max_decel_mps2"]
    print(f"  Controller 생성     ✅  (converter 는 npz 어댑터로 주입)")

    def one_step(s_m, d_m, v, dv=0.0):
        st = torch.tensor([s_m], dtype=trk.dtype)
        p, psi = trk.point_at(st, torch.tensor([d_m], dtype=trk.dtype))
        pos = np.array([[float(p[0, 0]), float(p[0, 1]), float(psi[0])]])
        i0 = int(trk.idx_of(st)) - 5
        wp = local_window(z, i0)
        o = trk.locate(p, psi)
        return c.main_loop("GB_TRACK", pos, wp, v, None,
                           np.array([float(o["s"]), float(o["d"]), v]),
                           np.array([dv]), trk.lap)

    r = one_step(12.40, 0.0, 5.0)
    print(f"  main_loop 1스텝     ✅  speed {r[0]:.4f}  delta {r[3]:+.5f} rad "
          f"({np.degrees(r[3]):+.3f}°)  L1 {r[5]:.3f} m")

    print(f"\n{BAR}\n B. reset 후 결정성\n{BAR}")
    seq = [(s, 0.3 * np.sin(s), 5.0) for s in np.arange(10.0, 14.0, 0.25)]
    reset_controller(c)                      # ← A 단계에서 이미 상태가 생겼다. 기준선부터 깨끗하게.
    run1 = [one_step(*x) for x in seq]
    mid = [one_step(s, 0.0, 9.0) for s in np.arange(20.0, 26.0, 0.25)]   # 상태를 오염시킨다
    print(f"  중간에 다른 구간 {len(mid)} 스텝을 흘려 상태를 오염시킴")
    hdr = (f"  오염 직후 상태: integral {getattr(c,'heading_error_integral',0):+.5f}  "
           f"filtered {getattr(c,'filtered_heading_error',0):+.5f}  "
           f"speed_prev {c._speed_cmd_prev}")
    print(hdr)
    run2_no_reset = [one_step(*x) for x in seq]
    reset_controller(c)
    run3_reset = [one_step(*x) for x in seq]

    d_nr = max(abs(x[3] - y[3]) for x, y in zip(run1, run2_no_reset))
    s_nr = max(abs(x[0] - y[0]) for x, y in zip(run1, run2_no_reset))
    d_r = max(abs(x[3] - y[3]) for x, y in zip(run1, run3_reset))
    s_r = max(abs(x[0] - y[0]) for x, y in zip(run1, run3_reset))
    print(f"  reset 없이 :  max|Δdelta| {d_nr:.3e} rad   max|Δspeed| {s_nr:.3e} m/s   "
          f"{'✅ 같다' if max(d_nr,s_nr)<1e-12 else '❌ 다르다 — 숨은 상태가 산다'}")
    print(f"  reset 후   :  max|Δdelta| {d_r:.3e} rad   max|Δspeed| {s_r:.3e} m/s   "
          f"{'✅ 복원됨' if max(d_r,s_r)<1e-12 else '❌ 복원 실패'}")
    ok_reset = max(d_r, s_r) < 1e-12

    print(f"\n{BAR}\n C. 보정 레이어가 실제로 작동하는가 (shipped yaml)\n{BAR}")
    kap = np.abs(z["kappa"]).astype(float)
    N = len(kap)
    cw = np.array([np.mean(kap[(i + 10) % N:(i + 10) % N + 10]) for i in range(N)])
    curv_term = np.clip(2 * (cw / 0.8) - 2, 0, 1)
    print(f"  curvature_waypoints = mean(|kappa|[i+10:i+20])  범위 {cw.min():.4f}~{cw.max():.4f}")
    print(f"    speed_adjust_lat_err 의 curv = clip(2·(mean/0.8)−2, 0, 1) → "
          f"최대 {curv_term.max():.4f}")
    print(f"    {'⚠️ 항상 0 → 이 레이어는 이 트랙에서 완전한 no-op' if curv_term.max()==0 else '활성 구간 있음'}"
          f"  (mean|kappa| 가 0.8 을 넘어야 한다)")

    print(f"\n  각 레이어에 1.0 을 넣어 배수를 잰다:")
    print(f"  {'레이어':<28}{'조건':<26}{'배수':>9}")
    c.acc_now = np.array([0.0]); f1 = c.acc_scaling(1.0)
    c.acc_now = np.array([2.0]); f2 = c.acc_scaling(1.0)
    c.acc_now = np.array([-4.0]); f3 = c.acc_scaling(1.0)
    print(f"  {'acc_scaling':<28}{'가속 0 / +2 / −4':<26}{f1:>4.3f}/{f2:.3f}/{f3:.3f}")
    for v in (3.0, 6.5, 8.0, 10.08):
        print(f"  {'speed_steer_scaling':<28}{f'v = {v:.2f} m/s':<26}{c.speed_steer_scaling(1.0, v):>9.4f}")
    for le in (0.0, 0.2, 0.5, 1.0):
        print(f"  {'steer_scaling_for_lat_err':<28}{f'lat_err = {le:.2f} m':<26}{c.steer_scaling_for_lat_err(1.0, le):>9.4f}")
    c.curvature_waypoints = cw.max()
    for ln in (0.0, 0.5, 1.0):
        print(f"  {'speed_adjust_lat_err':<28}{f'lat_e_norm = {ln:.1f} (최악곡률)':<26}{c.speed_adjust_lat_err(1.0, ln):>9.4f}")
    for he in (0.0, 9.0, 20.0, 45.0, 90.0):
        c.position_in_map = np.array([[0.0, 0.0, np.radians(he)]])
        c.waypoint_array_in_map = np.zeros((3, 9)); c.idx_nearest_waypoint = 0
        print(f"  {'speed_adjust_heading':<28}{f'heading err = {he:.0f}°':<26}{c.speed_adjust_heading(1.0):>9.4f}")

    print(f"\n{BAR}\n D. lookahead 점 정의 — 스택 vs s+L_d 보간\n{BAR}")
    print(f"  스택: 최근접 waypoint 부터 현 길이 누적 → searchsorted → **보간 없음**")
    print(f"  우리: s + L_d 를 FrenetTrack 으로 보간 조회")
    print(f"  {'v[m/s]':>7}{'L_d[m]':>8}{'스택 실제호길이':>15}{'부족분[m]':>11}{'두 점 거리[m]':>13}")
    rng = np.random.default_rng(0)
    worst = 0.0
    for v in (2.0, 3.0, 5.0, 8.0, 10.08):
        Ld = float(np.clip(P["m_l1"] * v + P["q_l1"], P["t_clip_min"], P["t_clip_max"]))
        errs, gaps = [], []
        for s0 in rng.uniform(0, trk.lap, 60):
            st = torch.tensor([s0], dtype=trk.dtype)
            i0 = int(trk.idx_of(st))
            wp = local_window(z, i0 - 5)
            pt = c.waypoint_at_distance_before_car(Ld, wp[:, :2], 5)
            seg = np.linalg.norm(np.diff(wp[5:, :2], axis=0), axis=1)
            k = int(np.argmin(np.linalg.norm(wp[5:, :2] - pt, axis=1)))
            arc = seg[:k].sum()
            p_ours, _ = trk.point_at(torch.tensor([s0 + Ld], dtype=trk.dtype))
            errs.append(Ld - arc)
            gaps.append(float(np.linalg.norm(p_ours[0].numpy() - pt)))
        worst = max(worst, max(gaps))
        print(f"  {v:>7.2f}{Ld:>8.3f}{Ld-np.mean(errs):>15.3f}{np.mean(errs):>11.4f}{np.mean(gaps):>13.4f}")
    print(f"  두 점 사이 최대 거리 {worst:.4f} m   (격자 ds = {trk.ds:.4f} m)")

    # 그 차이가 delta 로 얼마인가 — 같은 PP 수식에 두 점을 넣어 비교한다
    def pp_delta(car_xy, yaw, tgt, Ld):
        vec = np.asarray(tgt) - np.asarray(car_xy)
        n = np.linalg.norm(vec)
        eta = np.arcsin(np.clip(np.dot([-np.sin(yaw), np.cos(yaw)], vec) / max(n, 1e-9), -1, 1))
        return np.arctan(2 * WB * np.sin(eta) / Ld)

    print(f"\n  같은 PP 수식에 두 점을 넣었을 때 delta 차이:")
    print(f"  {'v[m/s]':>7}{'L_d[m]':>8}{'평균|Δdelta|':>13}{'최대|Δdelta|':>13}{'최대[deg]':>11}"
          f"{'delta_max 대비':>15}")
    for v in (2.0, 3.0, 5.0, 8.0, 10.08):
        Ld = float(np.clip(P["m_l1"] * v + P["q_l1"], P["t_clip_min"], P["t_clip_max"]))
        dd = []
        for s0 in rng.uniform(0, trk.lap, 120):
            st = torch.tensor([s0], dtype=trk.dtype)
            pc, yaw = trk.point_at(st, torch.tensor([0.0], dtype=trk.dtype))
            car = pc[0].numpy(); yw = float(yaw[0])
            wp = local_window(z, int(trk.idx_of(st)) - 5)
            pt_stack = c.waypoint_at_distance_before_car(Ld, wp[:, :2], 5)
            pt_ours, _ = trk.point_at(torch.tensor([s0 + Ld], dtype=trk.dtype))
            dd.append(abs(pp_delta(car, yw, pt_stack, Ld) - pp_delta(car, yw, pt_ours[0].numpy(), Ld)))
        dd = np.array(dd)
        print(f"  {v:>7.2f}{Ld:>8.3f}{dd.mean():>13.5f}{dd.max():>13.5f}"
              f"{np.degrees(dd.max()):>11.3f}{dd.max()/0.4189*100:>14.2f}%")
    print(f"  → 순수 PP 는 **보간 방식**을 쓴다. 우리 방법의 부품이지 스택 재현이 아니다.")
    print(f"     단 이 차이는 ①과 ② 를 비교할 때 lookahead 정의 차이로 남는다 — 문서에 남긴다.")

    print(f"\n{BAR}\n E. 종방향 base 의 kappa_eff 창 크기\n{BAR}")
    print(f"  v_ref = sqrt(a_lat_max/|kappa_eff|),  a_lat_max = 3.5")
    print(f"  {'창[m]':>7}{'v_ref 최소':>11}{'v_ref 최대':>11}{'IQP 대비 평균비':>16}")
    vx = z["vx_planner"].astype(float)
    for win_m in (1.0, 2.0, 4.0, 6.0, 10.0):
        w = max(1, int(round(win_m / trk.ds)))
        keff = np.array([np.abs(z["kappa"][(i + np.arange(w)) % N]).max() for i in range(N)])
        vref = np.clip(np.sqrt(3.5 / np.maximum(keff, 1e-6)), 0, 10.078)
        print(f"  {win_m:>7.1f}{vref.min():>11.3f}{vref.max():>11.3f}{np.mean(vref/vx):>16.3f}")
    print(f"  IQP vx_planner  최소 {vx.min():.3f}  최대 {vx.max():.3f}  평균 {vx.mean():.3f} m/s")

    print(f"\n  고정 창의 문제: 창이 제동거리보다 짧으면 코너에 **너무 빨리 도착**한다")
    A = 3.5
    print(f"  {'v[m/s]':>7}{'v_corner':>10}{'필요 제동거리[m]':>18}   (a_dec = a_lat_max = 3.5)")
    for v1 in (5.0, 8.0, 10.078):
        v2 = 2.144
        print(f"  {v1:>7.2f}{v2:>10.2f}{(v1*v1-v2*v2)/(2*A):>18.2f}")

    print(f"\n  속도 의존 창 W(v) = clip(v²/(2·a_lat_max), W_min, W_max) 로 하면:")
    print(f"  {'W_min':>6}{'W_max':>7}{'v_ref 최소':>11}{'v_ref 최대':>11}{'IQP 대비 평균비':>16}"
          f"{'자기일관성':>12}")
    for wmin, wmax in ((1.0, 8.0), (1.0, 12.0), (2.0, 10.0)):
        # 고정점 반복: v_ref 로 창을 정하고 그 창으로 v_ref 를 다시 구한다
        vref = np.full(N, 10.078)
        for _ in range(30):
            W = np.clip(vref**2 / (2*A), wmin, wmax)
            w_idx = np.maximum(1, np.round(W / trk.ds).astype(int))
            keff = np.array([np.abs(z["kappa"][(i + np.arange(w_idx[i])) % N]).max() for i in range(N)])
            vnew = np.clip(np.sqrt(A / np.maximum(keff, 1e-6)), 0, 10.078)
            if np.abs(vnew - vref).max() < 1e-4:
                vref = vnew; break
            vref = 0.5*vref + 0.5*vnew
        # 자기일관성: 앞 구간에서 요구되는 감속이 a_lat_max 안에 드는가
        dv = np.diff(np.append(vref, vref[0]))
        need = np.abs(np.where(dv < 0, (vref**2 - np.roll(vref, -1)**2) / (2*trk.ds), 0)).max()
        print(f"  {wmin:>6.1f}{wmax:>7.1f}{vref.min():>11.3f}{vref.max():>11.3f}"
              f"{np.mean(vref/vx):>16.3f}{need:>11.2f}x")
    print(f"  ※ 자기일관성 = 프로파일이 요구하는 최대 감속 [m/s²]. a_lat_max 3.5 보다 크면")
    print(f"     base 가 스스로 못 따라가는 프로파일을 내는 것이다.")
    print(f"  ❌ '창 안 최대 kappa' 는 코너가 창에 들어오는 순간 v_ref 가 한 칸에서 뚝 떨어진다")
    print(f"     = 계단 함수. 창 크기를 어떻게 잡아도 못 고친다.")

    print(f"\n  ★ 대안: backward/forward pass 로 **오프라인 1회** 계산 (npz 에 넣는다)")
    kap_a = np.maximum(np.abs(z["kappa"]).astype(float), 1e-6)
    VMAX = 10.078
    def profile(a_lat, a_lon):
        v = np.minimum(np.sqrt(a_lat / kap_a), VMAX)
        for _ in range(3):                       # 폐루프라 두 바퀴 이상 돌려 수렴시킨다
            for i in range(N - 1, -1, -1):       # backward: 앞 코너를 위해 미리 감속
                j = (i + 1) % N
                v[i] = min(v[i], np.sqrt(v[j]**2 + 2*a_lon*trk.ds))
            for i in range(N):                   # forward: 가속도 한계
                j = (i - 1) % N
                v[i] = min(v[i], np.sqrt(v[j]**2 + 2*a_lon*trk.ds))
        return v
    print(f"  {'a_lat':>6}{'a_lon':>7}{'v_ref 최소':>11}{'v_ref 최대':>11}"
          f"{'IQP 대비 평균비':>16}{'요구 감속':>11}{'요구 가속':>11}")
    for a_lat, a_lon in ((3.5, 3.5), (3.5, 5.0), (2.5, 3.5), (4.5, 4.5)):
        v = profile(a_lat, a_lon)
        vn = np.roll(v, -1)
        dec = ((v**2 - vn**2) / (2*trk.ds)).max()
        acc = ((vn**2 - v**2) / (2*trk.ds)).max()
        print(f"  {a_lat:>6.1f}{a_lon:>7.1f}{v.min():>11.3f}{v.max():>11.3f}"
              f"{np.mean(v/vx):>16.3f}{dec:>11.2f}{acc:>11.2f}")
    print(f"  → 요구 감속·가속이 정확히 a_lon 으로 묶인다 (구성상 보장).")
    print(f"     런타임 비용 0 (vx_at 처럼 조회), sim/real 동일, 파라미터 2개.")
    v35 = profile(3.5, 3.5)
    print(f"\n  a_lat=a_lon=3.5 프로파일 vs IQP:")
    print(f"  {'s[m]':>7}{'kappa':>9}{'base':>8}{'IQP':>8}{'비율':>7}")
    for si in (0.0, 5.0, 12.4, 20.0, 30.0, 40.0):
        i = int(round(si / trk.ds)) % N
        print(f"  {si:>7.1f}{z['kappa'][i]:>9.3f}{v35[i]:>8.2f}{vx[i]:>8.2f}{v35[i]/vx[i]:>7.2f}")

    print(f"\n{BAR}\n {'✅ A·B 통과' if ok_reset else '❌ B 실패'}\n{BAR}")
    return 0 if ok_reset else 1


if __name__ == "__main__":
    raise SystemExit(main())
