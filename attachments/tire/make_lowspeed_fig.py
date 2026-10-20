"""저속 처리 다섯 가지 비교 — 바퀴 하나(차체 질량의 1/4) 장난감 모델을 dt 5 ms 로 돌린다.

모델: J·ω̇ = τ − Fx·r,  m·v̇ = Fx,  Fx = PhysX Michigan 식(longitudinal 만) — μ-slip 그래프 포함.
값: m = 3.47/4 kg, J = 1.0903e-3 kg·m² (바퀴 + armature), r = 0.0508 m, Fz = 8.5 N, μ = 1,
C_κ = 20·Fz = 170 N, μ-slip (0,1)·(0.15,1)·(1,0.8). 힘은 step 시작 값으로 고정(PhysX 에 외력을 거는 것과 같은 명시 계산).
위: 정지에서 출발(바퀴 토크 0.4 N·m, wheelspin 없는 범위). 아래: 정지 상태에서 바퀴만 0.05 m/s 로 돌고 있을 때 멈추는가.
기준(회색 점선) = 같은 식을 dt 1 μs, ε 0.05 로 푼 값.

실행: python make_lowspeed_fig.py   (matplotlib. 한글 글꼴: WenQuanYi Zen Hei)
"""
import math
import os

import matplotlib

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
    "font.size": 9.5,
})
M = 3.47 / 4
J = 1.0903e-3
R = 0.0508
FZ = 8.5
MU = 1.0
C = 20 * FZ
PTS = ((0.0, 1.0), (0.15, 1.0), (1.0, 0.8))
KK = R * R / J + 1 / M          # slip velocity 를 바꾸는 유효 관성의 역수 [1/kg]


def g(k):
    (x0, y0), (x1, y1), (x2, y2) = PTS
    k = abs(k)
    if k < x1:
        return y0 + (y1 - y0) * (k - x0) / (x1 - x0)
    if k < x2:
        return y1 + (y2 - y1) * (k - x1) / (x2 - x1)
    return y2


def f1(K):
    K = min(K, 3.0)
    return K - K * K / 3 + K ** 3 / 27


def fx_of_kappa(k):
    if k == 0:
        return 0.0
    m = MU * g(k)
    return math.copysign(m * FZ * f1(C * abs(k) / (m * FZ)), k)


def f_slip(s, v, eps):
    return fx_of_kappa(s / (abs(v) + eps))


def run(method, tau, w0, T, dt=0.005, eps=0.1, sigma=0.02, vth=2.0, cdamp=50.0, rec=0.0025):
    w, v, u, t, nxt, out = w0, 0.0, 0.0, 0.0, 0.0, []
    for _ in range(int(round(T / dt))):
        s = w * R - v
        if method == "explicit":
            F = f_slip(s, v, eps)
        elif method == "implicit":
            F0 = f_slip(s, v, eps)
            D = (f_slip(s + 1e-6, v, eps) - f_slip(s - 1e-6, v, eps)) / 2e-6
            F = F0 + D * dt * (R * tau / J - F0 * KK) / (1 + dt * D * KK)
        elif method == "relax":
            F = fx_of_kappa(u / sigma)
        else:  # blend
            wg = min(abs(v) / vth, 1.0)
            F = wg * f_slip(s, v, eps) + (1 - wg) * max(-MU * FZ, min(MU * FZ, cdamp * s))
        w += dt * (tau - F * R) / J
        v += dt * F / M
        if method == "relax":
            u += dt * ((w * R - v) - abs(v) * u / sigma)
        t += dt
        if t >= nxt - 1e-12:
            out.append((t, F))
            nxt += rec
    return out


METHODS = [
    ("① ε 0.1 (PhysX 기본), dt 5 ms", dict(method="explicit", eps=0.1)),
    ("① ε 2.0 (지금 임시값)", dict(method="explicit", eps=2.0)),
    ("② 선형화 암묵, ε 0.1", dict(method="implicit", eps=0.1)),
    ("③ physics dt 1.25 ms + ε 0.75", dict(method="explicit", dt=0.00125, eps=0.75)),
    ("④ relaxation length σ 2 cm", dict(method="relax")),
    ("⑤ 저속 감쇠 전환 (2 m/s 아래)", dict(method="blend")),
]
SCEN = [("출발: τ 0.4 N·m", 0.4, 0.0, 0.4), ("정지 유지: τ 0, 바퀴만 0.05 m/s", 0.0, 0.05 / R, 0.3)]

fig, axes = plt.subplots(2, len(METHODS), figsize=(19, 6.2), sharey="row")
for row, (sname, tau, w0, T) in enumerate(SCEN):
    ref = run("explicit", tau, w0, T, dt=1e-6, eps=0.05)
    for col, (mname, kw) in enumerate(METHODS):
        ax = axes[row, col]
        o = run(tau=tau, w0=w0, T=T, **kw)
        ax.plot([x[0] for x in ref], [x[1] for x in ref], color="#999", lw=1.4, ls="--", label="기준")
        ax.plot([x[0] for x in o], [x[1] for x in o], color="#1f4e8c", lw=1.3, label="이 방법")
        ax.set_ylim(-9.5, 9.5)
        if row == 0:
            ax.set_title(mname, fontsize=9.5)
        else:
            ax.set_xlabel("시간 [s]")
        if col == 0:
            ax.set_ylabel(f"{sname}\nFx [N]")
        if row == 0 and col == 0:
            ax.legend(fontsize=8, loc="lower right")
fig.suptitle("저속 처리 비교 — 바퀴 하나 장난감 모델, Fx(t)  (위: 정지에서 출발 / 아래: 정지 유지)", fontsize=11.5)
fig.tight_layout()
out = os.path.join(HERE, "lowspeed_options.png")
fig.savefig(out)
print("wrote", out)
