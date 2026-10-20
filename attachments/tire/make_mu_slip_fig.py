"""μ-slip 3점 그래프 설명 그림 — (a) 그래프 자체, (b) 노면 μ 별 세로 힘, (c) 헛돌 때 옆 힘.

식은 PhysX VhTireFunctions.cpp (computeTireFriction, computeTireForceMichiganModel) 를 numpy 로 1:1 옮긴 것.
계수는 합의한 임시값: 정지 하중 8.8 N, 세로 강성 176 N (= 20·Fz), 가로 강성 latStiffY 47.45 N/rad · latStiffX 2,
3점 (0, 1.0) · (0.15, 1.0) · (1.0, 0.8).

실행: python make_mu_slip_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
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
PTS = ((0.0, 1.0), (0.15, 1.0), (1.0, 0.8))
FLAT = ((0.0, 1.0), (0.15, 1.0), (1.0, 1.0))
REST = 8.8
LONG = 20.0 * REST
LAT_X = 2.0


def f1(K):
    return min(1.0, K - K * K / 3 + K ** 3 / 27)


LAT_Y = 4.718 * REST / f1(3.0 / LAT_X)


def g(k, pts):
    (x0, y0), (x1, y1), (x2, y2) = pts
    k = abs(k)
    if k < x1:
        return y0 + (y1 - y0) * (k - x0) / (x1 - x0)
    if k < x2:
        return y1 + (y2 - y1) * (k - x1) / (x2 - x1)
    return y2


def force(kappa, alpha, mu_road, pts, fz=REST):
    mu = mu_road * g(kappa, pts)
    lat = alpha if abs(alpha) >= 1e-5 else 0.0
    lng = kappa if abs(kappa) >= 1e-5 else 0.0
    lat_stiff = LAT_Y * f1(fz / REST * 3.0 / LAT_X)
    if lat == 0 and lng == 0:
        return 0.0, 0.0
    T = math.tan(lat)
    K = math.hypot(lat_stiff * T, LONG * lng) / (mu * fz)
    fb = f1(K)
    nu = 1.0
    if K <= 2 * math.pi:
        r = lat_stiff / LONG
        nu = 0.5 * (1 + r - (1 - r) * math.cos(K * 0.5))
    f0 = mu * fz / math.sqrt(lng * lng + (nu * T) ** 2)
    return lng * fb * f0, -nu * T * fb * f0


fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.6))
k = np.linspace(0, 1.3, 800)

# (a) 그래프 자체
ax1.plot(k, [g(x, PTS) for x in k], color="#1f4e8c", lw=2.4, label="임시값 (0,1.0)·(0.15,1.0)·(1.0,0.8)")
ax1.plot(k, [g(x, FLAT) for x in k], color="#9aa0a6", lw=1.6, ls="--", label="평평한 그래프 (감소 없음, 비교용)")
for (x, y), lab, xt in zip(PTS, ("점 0 (x0, y0)\nslip 0 에서의 배율", "점 1 (x1, y1)\n정점 slip · 정점 배율",
                                  "점 2 (x2, y2)\n끝 slip · 미끄러질 때 배율"),
                           ((-0.02, 1.13), (0.38, 1.05), (0.75, 0.68))):
    ax1.plot(x, y, "o", color="#d1495b", ms=7, zorder=5)
    ax1.annotate(lab, xy=(x, y), xytext=xt, fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.7))
ax1.set_xlabel("|세로 slip κ|")
ax1.set_ylabel("g(|κ|) = 노면 μ 에 곱하는 배율")
ax1.set_title("(a) μ-slip 3점 그래프")
ax1.set_ylim(0.6, 1.2)
ax1.legend(fontsize=8.3, loc="lower left")

# (b) 노면 μ 별 세로 힘 — 그래프 있음/없음
k2 = np.linspace(0, 0.8, 600)
for mu, c in ((1.0, "#1f4e8c"), (0.5, "#5b8fc7")):
    ax2.plot(k2, [force(x, 0.0, mu, PTS)[0] / REST for x in k2], color=c, lw=2.2, label=f"μ = {mu}")
    ax2.plot(k2, [force(x, 0.0, mu, FLAT)[0] / REST for x in k2], color=c, lw=1.2, ls="--",
             label=f"μ = {mu}, 평평한 그래프")
    ks = 3 * mu * REST / LONG
    ax2.axvline(ks, color=c, lw=0.8, ls=":")
    ax2.annotate(f"brush 포화\nκ = 3μFz/C = {ks:.3f}", xy=(ks, mu * 0.55), xytext=(ks + 0.03, mu * 0.55),
                 fontsize=8)
ax2.plot(k2, LONG * k2 / REST, color="k", lw=0.8, ls=":", label="선형 C·κ (작은 slip 근사)")
ax2.axvline(0.15, color="#d1495b", lw=0.8)
ax2.text(0.155, 0.08, "점 1 (0.15)", color="#d1495b", fontsize=8.5)
ax2.set_xlabel("세로 slip κ")
ax2.set_ylabel("Fx / Fz")
ax2.set_title("(b) 세로 힘 — 작은 slip 은 그래프와 무관")
ax2.set_ylim(0, 1.15)
ax2.legend(fontsize=7.8, loc="lower right")

# (c) 옆 미끄럼각을 고정하고 헛돌기를 키우면
alpha = math.radians(3.0)
fx = [force(x, alpha, 1.0, PTS)[0] / REST for x in k2]
fy = [-force(x, alpha, 1.0, PTS)[1] / REST for x in k2]
ax3.plot(k2, fy, color="#d1495b", lw=2.2, label="옆 힘 |Fy|/Fz (α = 3° 고정)")
ax3.plot(k2, fx, color="#1f4e8c", lw=2.2, label="세로 힘 Fx/Fz")
ax3.plot(k2, np.hypot(fx, fy), color="#555", lw=1.2, ls="--", label="합력 / Fz (= μ·g 에서 포화)")
ax3.set_xlabel("세로 slip κ (헛돎이 커짐 →)")
ax3.set_ylabel("힘 / Fz")
ax3.set_title("(c) 헛돌면 옆 힘이 줄어든다 (μ = 1)")
ax3.set_ylim(0, 1.15)
ax3.legend(fontsize=8.3, loc="center right")

fig.tight_layout()
out = os.path.join(HERE, "mu_slip_graph.png")
fig.savefig(out)
print("wrote", out)
