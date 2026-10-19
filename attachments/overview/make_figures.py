"""프로젝트 한눈에 — 그림 5장을 만든다 (MOC/프로젝트 한눈에.md 에 들어가는 PNG).

숫자는 전부 볼트 §8-6(rl-racing 구조) 에 기록된 서버 출력이다. 곡선은 모델(식)이고,
점은 실측이다 — 그림마다 범례에 구분해 적는다.

실행: python make_figures.py   (matplotlib, numpy 필요. 한글 글꼴: WenQuanYi Zen Hei)
"""
import math
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({
    "font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 10.5,
})
C_MODEL = "#3b6ea8"   # 모델·예측
C_MEAS = "#d1495b"    # 실측
C_OLD = "#9aa0a6"     # 이전 상태
C_OK = "#2e8b57"      # 맞는 것

R = 0.0508            # 바퀴 반지름 [m]
J_LINK = 9.032e-5     # 바퀴 링크 스핀 관성 [kg m²]
J_EFF = 1.0903e-3     # 바퀴 관절 관성 = 링크 + armature 1e-3
DT = 0.005            # 물리 step [s]
M_EFF = 5.162         # 등가질량 [kg] (3.47 + 4·J_EFF/r²), 실험 A 기울기에서
L = 0.33              # wheelbase [m]
TRACK = 0.2255        # 좌우 바퀴 간격 [m]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, name), facecolor="white")
    plt.close(fig)
    print("wrote", name)


# ── 1. 가속 붕괴의 원인과 수정 ─────────────────────────────────────────
def fig_accel():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

    # (a) 4차 진단: max_angular_velocity=1000 "deg/s" → 17.45 rad/s 위에서 브레이크
    w_lim = math.radians(1000.0)          # 17.453 rad/s
    c_w = J_LINK / DT                      # 바퀴당 등가 점성 [N·m·s/rad]
    tau = np.linspace(0.0, 0.7, 100)
    v_term = R * (w_lim + tau / c_w)       # 토크 = 브레이크 가 되는 끝속도
    ax1.plot(tau, v_term, color=C_MODEL, lw=2, label="브레이크 모델 예측 (조정 상수 없음)")
    t_meas = [0.1, 0.2, 0.4, 0.629]
    v_meas = [1.1683, 1.4495, 2.0120, 2.6559]
    ax1.plot(t_meas, v_meas, "o", color=C_MEAS, ms=8, label="실측 끝속도 (토크를 고정하고 직진)")
    ax1.axhline(R * w_lim, color=C_OLD, ls="--", lw=1)
    ax1.text(0.01, R * w_lim + 0.05, "0.887 m/s — 바퀴가 17.45 rad/s 에 닿는 속도", color="#555", fontsize=9)
    ax1.set_xlabel("바퀴당 토크 [N·m]")
    ax1.set_ylabel("더 이상 빨라지지 않는 속도 [m/s]")
    ax1.set_title("수정 전: 바퀴 각속도 한계가 브레이크로 작동\n(1000 을 rad/s 로 생각했지만 Isaac 은 deg/s 로 읽는다)", fontsize=10.5)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.set_ylim(0, 3.2)
    ax1.text(0.40, 0.55, "네 점 모두 예측과 0.04% 이내", color=C_MEAS, fontsize=9.5)

    # (b) 5차 이후: 가속도 = 4τ/(r·m_eff)
    slope = 4.0 / (R * M_EFF)              # 15.25 (m/s²)/(N·m)
    ax2.plot(tau, slope * tau, color=C_MODEL, lw=2, label="예측 a = 4τ / (r·m_eff)")
    ax2.plot([0.1, 0.2, 0.4], [1.5254, 3.0516, 6.104], "o", color=C_MEAS, ms=8, label="실측 (토크 고정 직진, 수정 후)")
    ax2.plot([0.629], [8.278], "s", color=C_MEAS, ms=9, mfc="white", mew=2,
             label="실측 μ=1, 최대 토크 = 8.28 (앞바퀴 헛돎)")
    ax2.plot([0.629], [9.595], "D", color=C_OK, ms=8, mfc="white", mew=2,
             label="8차 예측: 센터 잠김이면 ≈ 9.6")
    ax2.annotate("가속하면 무게가 뒤로 쏠려\n앞바퀴가 먼저 미끄러진다\n(하중 이동 예측 8.33)", xy=(0.629, 8.278), xytext=(0.30, 8.6),
                 fontsize=9, arrowprops=dict(arrowstyle="->", color="#555"))
    ax2.set_xlabel("바퀴당 토크 [N·m]")
    ax2.set_ylabel("가속도 [m/s²]")
    ax2.set_title("수정 후: 토크만큼 정확히 가속한다", fontsize=10.5)
    ax2.legend(loc="lower right", fontsize=8.5)
    ax2.set_ylim(0, 11)
    save(fig, "accel.png")


# ── 2. 마찰계수가 설정대로 걸리는가 ──────────────────────────────────
def fig_friction():
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    mu = np.array([1.0, 0.5, 0.25, 0.12])
    mu_eff = [1.0000, 0.4945, 0.2484, 0.1195]          # 실험 B 중앙값 (6~7차)
    a_over_g = np.array([0.993, 0.996, 0.997]) * mu[1:]  # check_env ③ a/μg 비 × μ
    x = np.linspace(0, 1.05, 10)
    ax.plot(x, x, color=C_MODEL, lw=1.5, label="설정한 μ = 실제 μ")
    ax.plot(mu, mu_eff, "o", color=C_MEAS, ms=8, label="바퀴 힘 ÷ 하중 (미끄러지는 동안의 중앙값)")
    ax.plot(mu[1:], a_over_g, "s", color=C_OK, ms=7, mfc="white", mew=2, label="미끄러질 때 가속도 ÷ g (μ 별 가속 시험)")
    ax.set_xlabel("설정한 마찰계수 μ")
    ax.set_ylabel("측정한 마찰계수")
    ax.set_title("마찰은 설정한 값 그대로 걸린다 (오차 1% 이내)", fontsize=10.5)
    ax.legend(fontsize=8.5, loc="upper left")
    ax.set_xlim(0, 1.08)
    ax.set_ylim(0, 1.08)
    save(fig, "friction.png")


# ── 3. 조향: 명령한 곡률이 실제로 나오는가 ─────────────────────────────
def fig_curvature():
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    delta = [0.1, 0.2, 0.3, 0.4189]
    rounds = [
        ("5차: 두 앞바퀴 같은 각 + 약한 경첩(강성 8)", [0.919, 0.983, 1.023, 0.852], C_OLD, "o--"),
        ("6차: Ackermann + 약한 경첩", [0.826, 0.905, 0.921, 0.926], "#e0a030", "s--"),
        ("7차: Ackermann + 서보 모델 + 강한 경첩(강성 120)", [0.989, 0.998, 0.996, 0.994], C_OK, "D-"),
    ]
    ax.axhspan(0.97, 1.03, color=C_OK, alpha=0.10, label="목표 ±3%")
    ax.axhline(1.0, color="#555", lw=1)
    for label, vals, col, style in rounds:
        ax.plot(delta, vals, style, color=col, lw=2, ms=7, label=label)
    ax.set_xlabel("명령 조향각 δ [rad]")
    ax.set_ylabel("실측 곡률 ÷ 명령 곡률 (tanδ / L)")
    ax.set_title("고정 조향 원 주행 (1 m/s): 차수마다 원인을 하나씩 제거", fontsize=10.5)
    ax.set_ylim(0.80, 1.06)
    ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, frameon=False)
    save(fig, "curvature.png")


# ── 4. 조향 계단 응답: 서보 모델 vs 실측 ──────────────────────────────
def hinges(d):
    if abs(d) < 1e-12:
        return 0.0, 0.0
    tl = math.atan2(L * math.tan(d), L - (TRACK / 2) * math.tan(d))
    tr = math.atan2(L * math.tan(d), L + (TRACK / 2) * math.tan(d))
    return tl, tr


def fig_step():
    tau_s, rate, tgt = 0.06, 3.2, 0.3
    alpha = 1 - math.exp(-DT / tau_s)
    n = 80
    df, out = 0.0, []
    for _ in range(n):
        df += max(-rate * DT, min(rate * DT, alpha * (tgt - df)))
        out.append(df)
    t = np.arange(1, n + 1) * DT
    TL, TR = hinges(tgt)
    hl = np.array([hinges(x)[0] for x in out]) / TL
    hr = np.array([hinges(x)[1] for x in out]) / TR
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.plot(t, np.array(out) / tgt, color="#555", lw=1.2, ls=":", label="서보 출력 δ_f (모델)")
    ax.plot(t, hl, color=C_MODEL, lw=2, label="왼쪽(안쪽) 바퀴 목표각 (모델)")
    ax.plot(t, hr, color="#7fa7d6", lw=2, label="오른쪽(바깥) 바퀴 목표각 (모델)")
    fr = [0.1, 0.632, 0.9]
    ax.plot([0.010, 0.075, 0.155], fr, "o", color=C_MEAS, ms=8, label="7차 실측 왼쪽")
    ax.plot([0.010, 0.065, 0.145], fr, "^", color=C_MEAS, ms=8, mfc="white", mew=2, label="7차 실측 오른쪽")
    ax.plot([0.010, 0.075, 0.190], fr, "x", color=C_OLD, ms=9, mew=2, label="6차 설정 실측 왼쪽")
    ax.plot([0.005, 0.075, 0.260], fr, "+", color=C_OLD, ms=11, mew=2, label="6차 설정 실측 오른쪽")
    ax.set_xlabel("계단 명령 후 시간 [s]")
    ax.set_ylabel("최종값 대비 비율")
    ax.set_title("조향 계단 응답 (δ 0 → 0.3, τ = 0.06 s, 속도 한계 3.2 rad/s)\n실측은 모델보다 한 물리 step(5 ms) 늦을 뿐", fontsize=10.5)
    ax.set_xlim(0, 0.3)
    ax.set_ylim(0, 1.08)
    ax.legend(fontsize=8, loc="lower right")
    save(fig, "steer_step.png")


# ── 5. 센터 잠김 결합: 강도와 "한 step 늦음" ────────────────────────────
def coupling_run(a, b, late, d_t=1.258, n=60, enabled=True):
    k, c = a * J_EFF / DT ** 2, b * J_EFF / DT
    dw = tw = prev = 0.0
    hist = []
    for _ in range(n):
        meas = prev if late else dw
        tw += DT * meas
        tc = (k * tw + c * meas) if enabled else 0.0
        prev = dw
        dw += DT * (d_t - tc) / J_EFF
        hist.append(dw)
    return np.arange(1, n + 1) * DT, np.array(hist)


def fig_coupling():
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    t, open_ = coupling_run(0, 0, False, enabled=False)
    ax.plot(t, open_, color=C_OLD, lw=2, ls="--", label="결합 없음 (지금 모델): 앞바퀴가 계속 빨라진다")
    for (a, b, late, col, ls, lab) in [
        (0.1, 0.5, False, C_OK, "-", "제안값 (스프링 0.1, 감쇠 0.5), 제때 읽음"),
        (0.1, 0.5, True, C_OK, ":", "제안값, 한 step 늦게 읽음 → 그래도 수렴"),
        (0.5, 0.5, False, C_MODEL, "-", "더 강하게 (0.5, 0.5), 제때 읽음"),
        (0.5, 0.5, True, C_MEAS, ":", "더 강하게, 한 step 늦게 읽음 → 발산"),
    ]:
        t, h = coupling_run(a, b, late)
        out = np.nonzero(np.abs(h) > 22)[0]
        if len(out):                      # 발산하는 선은 그림 밖으로 나가는 곳에서 멈춘다
            t, h = t[: out[0] + 1], h[: out[0] + 1]
            ax.annotate("발산", xy=(t[-1], -21), xytext=(t[-1] + 0.02, -17), color=col,
                        fontsize=9, arrowprops=dict(arrowstyle="->", color=col))
        ax.plot(t, h, color=col, ls=ls, lw=2, label=lab)
    ax.axhline(0, color="#555", lw=1)
    ax.set_ylim(-22, 26)
    ax.set_xlim(0, 0.3)
    ax.set_xlabel("앞바퀴가 접지를 잃은 뒤 시간 [s]")
    ax.set_ylabel("앞축 평균 − 뒤축 평균 바퀴 속도 [rad/s]")
    ax.set_title("센터 잠김을 소프트웨어 결합으로 흉내낼 때 (장난감 모델, 바퀴가 떠 있는 최악 조건)", fontsize=10)
    ax.legend(fontsize=8, loc="upper right")
    save(fig, "coupling.png")


# ── 6. Pure Pursuit 기하 (개념 그림) ─────────────────────────────────
def fig_pp():
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    xs = np.linspace(-0.5, 3.2, 200)
    ax.plot(xs, 0.08 * xs ** 2 + 0.15 * xs, color="#888", lw=6, alpha=0.35, label="따라갈 경로")
    eta = math.radians(28)
    ld = 2.0
    gx, gy = ld * math.cos(eta), ld * math.sin(eta)
    rr = ld / (2 * math.sin(eta))
    th = np.linspace(-math.pi / 2, -math.pi / 2 + 2 * eta, 60)
    ax.plot(rr * np.cos(th), rr + rr * np.sin(th), color=C_MODEL, lw=2, label="차가 그릴 원호 (반지름 R)")
    ax.plot([0, gx], [0, gy], "--", color=C_MEAS, lw=1.5)
    ax.text(gx / 2 - 0.35, gy / 2 + 0.12, "$L_d$ (lookahead 거리)", color=C_MEAS)
    ax.plot([gx], [gy], "o", color=C_MEAS, ms=9)
    ax.text(gx + 0.08, gy - 0.05, "목표점", color=C_MEAS)
    ax.add_patch(plt.Rectangle((-0.12, -0.12), 0.45, 0.24, color="#444", alpha=0.25))
    ax.plot([0, 0.33], [0, 0], color="#222", lw=3)
    ax.plot([0], [0], "s", color="#222", ms=6)
    ax.text(-0.45, -0.32, "뒤 차축\n(차의 기준점)", fontsize=9)
    ax.annotate("", xy=(1.1, 0), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color="#222"))
    ax.text(1.12, -0.13, "차의 진행 방향", fontsize=9)
    a = np.linspace(0, eta, 30)
    ax.plot(0.7 * np.cos(a), 0.7 * np.sin(a), color="#222", lw=1)
    ax.text(0.75, 0.13, "η", fontsize=13)
    ax.plot([0, 0], [0, rr], ":", color=C_MODEL, lw=1)
    ax.plot([0], [rr], "+", color=C_MODEL, ms=10, mew=2)
    ax.text(0.06, rr - 0.1, "원의 중심", color=C_MODEL, fontsize=9)
    ax.set_title("Pure Pursuit: 목표점을 지나는 원을 그리도록 조향\n"
                 "$\\kappa = 2\\sin\\eta / L_d$,   $\\delta = \\arctan(L\\,\\kappa)$", fontsize=10.5)
    ax.set_aspect("equal")
    ax.set_xlim(-0.7, 3.0)
    ax.set_ylim(-0.6, 2.4)
    ax.legend(loc="lower right", fontsize=8.5)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    save(fig, "pp_geometry.png")


# ── 7. Frenet 좌표 (개념 그림) ───────────────────────────────────────
def fig_frenet():
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    x = np.linspace(0, 7, 400)
    y = 1.0 * np.sin(x / 1.6)
    dx, dy = np.gradient(x), np.gradient(y)
    nrm = np.hypot(dx, dy)
    nx, ny = -dy / nrm, dx / nrm                      # 왼쪽 법선
    ax.plot(x, y, color="#444", lw=2.5, label="raceline (기준 경로, d = 0)")
    d_ref = 0.35
    ax.plot(x + d_ref * nx, y + d_ref * ny, "--", color=C_MODEL, lw=2, label="planner 가 준 경로 $d_{ref}(s)$")
    i = 250
    d = 0.75
    px, py = x[i] + d * nx[i], y[i] + d * ny[i]
    seg = np.hypot(np.diff(x[: i + 1]), np.diff(y[: i + 1]))
    ax.plot(x[: i + 1], y[: i + 1], color=C_OK, lw=6, alpha=0.35)
    ax.text(x[i // 2] - 0.9, y[i // 2] - 0.62, f"s = 경로를 따라 잰 거리 ({seg.sum():.1f} m)", color=C_OK, fontsize=9.5)
    ax.plot([x[i], px], [y[i], py], color="#222", lw=1)
    ax.plot([x[i]], [y[i]], "o", color="#222", ms=5)
    ax.plot([px], [py], "s", color=C_MEAS, ms=10, label="차")
    rx, ry = x[i] + d_ref * nx[i], y[i] + d_ref * ny[i]
    ax.annotate("", xy=(px, py), xytext=(rx, ry), arrowprops=dict(arrowstyle="<->", color=C_MEAS, lw=2))
    ax.text(px + 0.12, (py + ry) / 2, "$e_d = d - d_{ref}$\n(추종 오차)", color=C_MEAS, fontsize=10)
    ax.text(x[i] + 0.3, y[i] - 0.02, "d (왼쪽 +)", fontsize=9.5)
    ax.set_aspect("equal")
    ax.set_title("Frenet 좌표: 위치를 (s, d) 로 — 경로를 따라 얼마나 왔나, 옆으로 얼마나 벗어났나", fontsize=10.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=3, fontsize=8.5, frameon=False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    save(fig, "frenet.png")


if __name__ == "__main__":
    fig_accel()
    fig_friction()
    fig_curvature()
    fig_step()
    fig_coupling()
    fig_pp()
    fig_frenet()
