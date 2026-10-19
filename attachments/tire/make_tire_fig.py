"""타이어 모델 비교 — 지금 sim(PhysX 강체 접촉) vs PhysX Vehicles SDK vs F1TENTH gym 의 힘-slip 곡선.

곡선은 각 소스의 식을 그대로 옮긴 것이다 (계수는 예시, 아래 주석). 점은 8차 wheel_check 실측.
- PhysX Vehicles: physx/source/physxvehicle/src/tire/VhTireFunctions.cpp
  computeTireForceMichiganModel (smoothingFunction1) + computeTireFriction (frictionVsSlip 3점 그래프)
- F1TENTH ST: f1tenth_gym main, gym/f110_gym/envs/dynamic_models.py vehicle_dynamics_st (선형, C_S = 4.718 /rad)
- F1TENTH MB: dev-dynamics 브랜치 multi_body/tire_model.py (Pacejka Magic Formula)

실행: python make_tire_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
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
C_NOW = "#9aa0a6"     # 지금 sim (Coulomb)
C_PX = "#3b6ea8"      # PhysX Vehicles (Michigan = brush)
C_MF = "#2e8b57"      # Pacejka Magic Formula
C_ST = "#c08a1e"      # F1TENTH ST (선형)
C_MEAS = "#d1495b"    # 실측


def brush(K):
    """PhysX smoothingFunction1 — K - K²/3 + K³/27, K ≥ 3 에서 1 (brush model, 포물선 압력 분포)."""
    return np.minimum(1.0, K - K**2 / 3 + K**3 / 27)


def mu_vs_slip(k, pts=((0.0, 1.0), (0.15, 1.0), (1.0, 0.75))):
    """PhysX frictionVsSlip — 3점 직선 보간 (값은 예시)."""
    (x0, y0), (x1, y1), (x2, y2) = pts
    k = np.abs(k)
    return np.where(k < x1, y0 + (y1 - y0) * (k - x0) / (x1 - x0),
                    np.where(k < x2, y1 + (y2 - y1) * (k - x1) / (x2 - x1), y2))


def magic(x, B, C, D=1.0, E=0.0):
    return D * np.sin(C * np.arctan(B * x - E * (B * x - np.arctan(B * x))))


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.4))

# (a) 세로 방향: x = 세로 slip κ = (ωr − v)/|v|
STIFF_X = 20.0                         # 세로 slip 강성 ÷ (μ·Fz), 예시 — 실차 측정 대상
k = np.linspace(0, 0.6, 600)
ax1.plot([0, 0, 0.6], [0, 1, 1], color=C_NOW, lw=3.2, alpha=0.8,
         label="지금 sim (PhysX 강체 접촉, Coulomb)\nslip 0 에서 0~μN 아무 값, 미끄러지면 μN")
m = mu_vs_slip(k)
ax1.plot(k, m * brush(STIFF_X * k / m), color=C_PX, lw=2,
         label="PhysX Vehicles (Michigan = brush)\n× μ-slip 그래프 (0,1)·(0.15,1)·(1,0.75) 예시")
ax1.plot(k, magic(k, B=STIFF_X / 1.65, C=1.65), color=C_MF, lw=2, ls="--",
         label="Pacejka Magic Formula (F1TENTH MB)\nC=1.65, E=0, 같은 초기 기울기")
ax1.scatter([0.002, 0.000, 0.311, 0.313], [0.978, 0.819, 0.998, 1.001], color=C_MEAS, zorder=5, s=34,
            label="8차 wheel_check 실측 (네 바퀴)")
ax1.set_xlabel("세로 slip κ = (ω·r − v) / v")
ax1.set_ylabel("Fx / (μ·Fz)")
ax1.set_title("(a) 가속·제동 방향")
ax1.set_ylim(0, 1.25)
ax1.legend(fontsize=8.3, loc="lower right")

# (b) 가로 방향: x = 미끄럼각 α
C_S = 4.718                            # F1TENTH 기본 앞바퀴 코너링 강성 [1/rad] (하중 1 당)
a_deg = np.linspace(0, 45, 600)
a = np.radians(a_deg)
ax2.plot([0, 0, 45], [0, 1, 1], color=C_NOW, lw=3.2, alpha=0.8, label="지금 sim (Coulomb)")
ax2.plot(a_deg, C_S * a, color=C_ST, lw=2,
         label="F1TENTH ST — Fy = μ·C_S·Fz·α (선형, 상한 없음)\nC_S = 4.718 /rad (기본값)")
ax2.plot(a_deg, brush(C_S * np.tan(a)), color=C_PX, lw=2, label="PhysX Vehicles (brush), 같은 초기 기울기")
ax2.plot(a_deg, magic(a, B=C_S / 1.3, C=1.3), color=C_MF, lw=2, ls="--",
         label="Pacejka MF (F1TENTH MB), C=1.3")
ax2.axhline(1.0, color="k", lw=0.8, ls=":")
ax2.annotate("μ·Fz 를 넘는 힘\n(마찰 한계 없음)", xy=(18, C_S * np.radians(18)), xytext=(24, 1.55),
             fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.8))
ax2.set_xlabel("미끄럼각 α [deg]")
ax2.set_ylabel("Fy / (μ·Fz)")
ax2.set_title("(b) 옆 방향 (코너링)")
ax2.set_ylim(0, 2.1)
ax2.legend(fontsize=8.3, loc="lower right")

fig.tight_layout()
out = os.path.join(HERE, "tire_models.png")
fig.savefig(out)
print("wrote", out)
