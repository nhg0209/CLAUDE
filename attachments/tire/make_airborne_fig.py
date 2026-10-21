"""바퀴가 떴다가 착지할 때 carcass deflection u 처리 세 가지 — 장난감 계산.

R1(relaxation_update, 직렬 β = |v|·c/C) + R2a(damped_tire_force, Michigan) 식을 dt = 5 ms 로 그대로 돌린다.
slip velocity 는 정해 준 값(바퀴·차체 동역학은 풀지 않는다). 차속 |v| = 2 m/s 일정.
 (a) longitudinal — 60 ms 공중에서 구동 토크로 헛돌기 시작(s = ωr − v: 0.02 → 1.0 m/s), 착지 뒤 30 ms 시정수로 0.02 로 복귀
 (b) lateral — 코너링 중(α 0.05 rad, v_lat = |v|·tan α) 60 ms 공중, 착지 뒤 같은 α
 (c) lateral — 같은 코너링에서 한 physics step(5 ms)만 접촉이 끊김 (요철·접촉 센서 값이 순간 0)
공중에서는 lateral C_α(load 0) = 0 → series_factor 의 β = 0.
계수는 임시값: σ 0.02 m, c 15 N·s/m, C_κ 176 N, C_α(rest) 41.5184 N/rad, rest load 8.8 N, μ 1, μ-slip 3점, cap 1.
(3) 의 τ = c·σ / C(rest) — 공중의 carcass 가 spring c_c = C/σ 와 damper c 로만 돌아올 때: longitudinal 1.7 ms, lateral 7.2 ms.

실행: python make_airborne_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
"""
import math
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({
    "font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False,
    "figure.dpi": 110, "savefig.dpi": 150, "axes.grid": True, "grid.alpha": 0.3,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10.5,
})
DT, V, SIG, C_DAMP, FZ0, MU, CAP = 0.005, 2.0, 0.02, 15.0, 8.8, 1.0, 1.0
C_K, C_A = 176.0, 41.5184
PTS = ((0.0, 1.0), (0.15, 1.0), (1.0, 0.8))
ALPHA = 0.05


def g(k):
    k = abs(k)
    (x0, y0), (x1, y1), (x2, y2) = PTS
    if k < x1:
        return y0 + (y1 - y0) * (k - x0) / (x1 - x0)
    if k < x2:
        return y1 + (y2 - y1) * (k - x1) / (x2 - x1)
    return y2


def f1(k):
    k = min(k, 3.0)
    return k - k * k / 3 + k ** 3 / 27


def relax(u, s, stiff):
    beta = 0.0 if stiff == 0.0 else V * C_DAMP / stiff
    a = V / (SIG * (1 + beta))
    un = u * math.exp(-a * DT) + (s / (1 + beta)) * (-math.expm1(-a * DT)) / a
    return max(-CAP * SIG, min(CAP * SIG, un))


def force_mag(u, dudt, fz, stiff, long_dir):
    """한 방향만 slip 이 있을 때 |F| (Michigan: K = C·|slip|/(μ_eff·Fz), F = F̄(K)·μ_eff·Fz) + damping, 상한."""
    if fz <= 0.0:
        return 0.0
    x = u / SIG
    mu_eff = MU * (g(x) if long_dir else 1.0)
    f = 0.0 if abs(x) < 1e-5 else f1(stiff * abs(x) / (mu_eff * fz)) * mu_eff * fz
    f = math.copysign(f, x) + C_DAMP * dudt
    return min(abs(f), mu_eff * fz)


def run(slip, air, stiff_rest, long_dir, opt):
    u, out = 0.0, []
    u = SIG * slip(0.0) / V if not long_dir else u
    for ti in T:
        a = air(ti)
        fz = 0.0 if a else FZ0
        stiff = stiff_rest if (long_dir or not a) else 0.0
        if a and opt == 2:
            un = 0.0
        elif a and opt == 3:
            un = u * math.exp(-DT / (C_DAMP * SIG / stiff_rest))
        else:
            un = relax(u, slip(ti), stiff)
        out.append(force_mag(un, (un - u) / DT, fz, stiff_rest, long_dir))
        u = un
    return np.array(out)


T = np.arange(0.0, 0.30, DT)


def s_long(t):
    if t < 0.10:
        return 0.02
    if t < 0.16:
        return 0.02 + 0.98 * (t - 0.10) / 0.06
    return 0.02 + 0.98 * math.exp(-(t - 0.16) / 0.03)


def s_lat(t):
    return V * math.tan(ALPHA)


cases = [
    ("(a) longitudinal — 60 ms 공중에서 wheelspin 뒤 착지", s_long, lambda t: 0.10 <= t < 0.16, C_K, True, (0.10, 0.16)),
    ("(b) lateral — 코너링 중 60 ms 공중 뒤 착지 (α 0.05)", s_lat, lambda t: 0.10 <= t < 0.16, C_A, False, (0.10, 0.16)),
    ("(c) lateral — 한 step(5 ms)만 접촉이 끊김", s_lat, lambda t: 0.10 <= t < 0.105, C_A, False, (0.10, 0.105)),
]
lab = {1: "(1) 공중에서도 그대로 갱신", 2: "(2) 공중이면 u = 0", 3: "(3) 공중이면 carcass 시정수로 감쇠"}
col = {1: "#d1495b", 2: "#1f4e8c", 3: "#2e8b57"}
sty = {1: "-", 2: "-", 3: "--"}
fig, axes = plt.subplots(1, 3, figsize=(16, 4.7))
for ax, (title, slip, air, stiff, long_dir, span) in zip(axes, cases):
    ax.axvspan(span[0] * 1e3, span[1] * 1e3, color="#999", alpha=0.2)
    for o in (1, 2, 3):
        f = run(slip, air, stiff, long_dir, o)
        ax.step(T * 1e3, f, where="post", color=col[o], ls=sty[o], lw=2.0, label=lab[o])
        i = int(round(span[1] / DT))
        print(title[:3], o, [round(x, 2) for x in f[i - 1:i + 6]])
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("시간 [ms]  (한 칸 = physics step 5 ms, 회색 = Fz 0)")
    ax.set_xlim(60, 260)
axes[0].set_ylabel("|Fx| [N]")
axes[1].set_ylabel("|Fy| [N]")
axes[2].set_ylabel("|Fy| [N]")
axes[0].text(170, 3.0, "셋 다 착지 step 에 상한 근처\n(큰 slip velocity → damping force 가\n바로 채움 = 접지면 전체 sliding)",
             fontsize=8.3, color="#444")
axes[1].text(165, 0.55, "(1) 착지 즉시 정상 상태 Fy\n(2)·(3) 약 17 ms 에 걸쳐 쌓임\n= σ(1+β)/|v|", fontsize=8.3, color="#444")
axes[2].text(112, 0.55, "(2) 만 다시 쌓는 데 17 ms\n(3) 은 절반(e^(−5/7.2)) 남김", fontsize=8.3, color="#444")
for ax in axes:
    ax.legend(fontsize=7.8, loc="lower right")
fig.tight_layout()
out = os.path.join(HERE, "airborne_options.png")
fig.savefig(out)
print("wrote", out)
