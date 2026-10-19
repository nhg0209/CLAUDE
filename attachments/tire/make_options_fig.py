"""(나) Coulomb + DR 과 (다) PhysX 타이어 식 + DR 이 sim 안에서 만드는 힘-slip 곡선 비교.

두 방식 모두 μ 를 env 마다 무작위로 바꾼다 (여기서는 μ = 0.5 · 0.75 · 1.0 세 값).
(나) 는 정지마찰 μ_s, 운동마찰 μ_d = 0.85·μ_s (2단 근사, 비율은 예시).
(다) 는 PhysX computeTireForceMichiganModel + frictionVsSlip, 계수는 make_tire_fig.py 와 같은 예시 값.

실행: python make_options_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
"""
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
MUS = (0.5, 0.75, 1.0)
SHADES = ("#9ec5e8", "#5b8fc7", "#1f4e8c")
STIFF_X = 20.0      # 세로 slip 강성 ÷ Fz (예시)
C_S = 4.718         # 가로 코너링 강성 ÷ Fz [1/rad] (F1TENTH 기본값을 예시로)
RATIO_D = 0.85      # (나) μ_d / μ_s (예시)


def brush(K):
    return np.minimum(1.0, K - K**2 / 3 + K**3 / 27)


def mu_vs_slip(k, pts=((0.0, 1.0), (0.15, 1.0), (1.0, 0.75))):
    (x0, y0), (x1, y1), (x2, y2) = pts
    k = np.abs(k)
    return np.where(k < x1, y0 + (y1 - y0) * (k - x0) / (x1 - x0),
                    np.where(k < x2, y1 + (y2 - y1) * (k - x1) / (x2 - x1), y2))


fig, axes = plt.subplots(2, 2, figsize=(11, 7.2), sharey="row")
k = np.linspace(0, 0.6, 600)
a_deg = np.linspace(0, 40, 600)
a = np.radians(a_deg)
for mu, c in zip(MUS, SHADES):
    lab = f"μ = {mu}"
    # (나) 세로·가로: slip 0 에서 0~μ_s 아무 값, 미끄러지면 μ_d
    axes[0, 0].plot([0, 0, 0.004, 0.6], [0, mu, mu * RATIO_D, mu * RATIO_D], color=c, lw=2.2, label=lab)
    axes[1, 0].plot([0, 0, 0.27, 40], [0, mu, mu * RATIO_D, mu * RATIO_D], color=c, lw=2.2, label=lab)
    # (다) 세로: μ·g(κ)·F̄(C·κ / (μ·g(κ))), 가로: μ·F̄(C_S·tanα / μ)
    m = mu * mu_vs_slip(k)
    axes[0, 1].plot(k, m * brush(STIFF_X * k / m), color=c, lw=2.2, label=lab)
    axes[1, 1].plot(a_deg, mu * brush(C_S * np.tan(a) / mu), color=c, lw=2.2, label=lab)

axes[0, 0].set_title("(나) PhysX 강체 접촉 + DR — 세로")
axes[0, 1].set_title("(다) PhysX 타이어 식 + DR — 세로")
axes[1, 0].set_title("(나) — 가로")
axes[1, 1].set_title("(다) — 가로")
for ax in axes[0]:
    ax.set_xlabel("세로 slip κ")
for ax in axes[1]:
    ax.set_xlabel("미끄럼각 α [deg]")
axes[0, 0].set_ylabel("Fx / Fz")
axes[1, 0].set_ylabel("Fy / Fz")
for ax in axes.flat:
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=8.5, loc="lower right")
axes[0, 0].annotate(f"정지마찰 μ_s → 미끄러지면 μ_d = {RATIO_D}·μ_s\n(정점 뒤 감소의 2단 근사)", xy=(0.05, 0.86),
                    xytext=(0.12, 0.35), fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.8))
axes[1, 0].annotate("한계 전까지 미끄럼각 0\n= understeer 가 생기지 않음", xy=(0.3, 0.6), xytext=(8, 0.25),
                    fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.8))
axes[1, 1].annotate("미끄럼각이 힘에 비례해 커짐\n= understeer 가 생김", xy=(6, 0.42), xytext=(14, 0.2),
                    fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.8))
fig.suptitle("DR 이 흔드는 것: (나) 는 계단의 높이, (다) 는 곡선의 높이와 기울기", fontsize=11.5)
fig.tight_layout()
out = os.path.join(HERE, "options_na_da.png")
fig.savefig(out)
print("wrote", out)
