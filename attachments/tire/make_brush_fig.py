"""brush model 설명 그림 — (a) contact patch 안의 힘 분포, (b) 힘 곡선과 adhesion 비율, (c) combined slip 의 ν.

Pacejka, Tire and Vehicle Dynamics 3장의 brush model (rigid carcass, 포물선 pressure 분포) 을 정규화해서 그린다.
λ = θ·σ (θ = 2·c_p·a² / (3·μ·Fz), σ = slip) 이고 PhysX Michigan 식의 K 와 K = 3λ 관계다.
(c) 의 ν 는 PhysX VhTireFunctions.cpp computeTireForceMichiganModel 의 식, r = C_α/C_κ 는 합의한 임시값(41.52/176).

실행: python make_brush_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
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
C_ADH = "#2e8b57"
C_SLD = "#d1495b"
C_LIM = "#555555"

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15.5, 4.7))

# (a) contact patch: ξ = 0 leading edge → 1 trailing edge. 한계 μ·q_z ∝ 4ξ(1−ξ), bristle 힘 ∝ 4λξ
xi = np.linspace(0, 1, 400)
limit = 4 * xi * (1 - xi)
ax1.plot(xi, limit, color=C_LIM, lw=1.6, ls="--", label="friction 한계 μ·q_z(x) (포물선 pressure)")
for lam in (0.25, 0.9):
    ax1.plot(xi, np.minimum(4 * lam * xi, limit), color="#7f9cc0", lw=1.3, label=f"λ = {lam}")
    ax1.plot([1 - lam], [4 * lam * (1 - lam)], "o", color="#7f9cc0", ms=4)
lam = 0.5
q = np.minimum(4 * lam * xi, limit)
ax1.plot(xi, q, color="#1f4e8c", lw=2.4, label="λ = 0.5 (색칠)")
ax1.fill_between(xi, 0, q, where=xi <= 1 - lam, color=C_ADH, alpha=0.25)
ax1.fill_between(xi, 0, q, where=xi >= 1 - lam, color=C_SLD, alpha=0.25)
ax1.plot([1 - lam], [4 * lam * (1 - lam)], "o", color="#1f4e8c", ms=6)
ax1.annotate("adhesion 구간\nbristle 이 노면에 붙어\n들어온 뒤 거리에 비례해 휨", xy=(0.25, 0.2), xytext=(0.03, 0.62),
             fontsize=8.5, color=C_ADH, arrowprops=dict(arrowstyle="->", lw=0.7, color=C_ADH))
ax1.annotate("sliding 구간\n힘 = μ·q_z (한계에 붙음)", xy=(0.75, 0.35), xytext=(0.55, 0.08), fontsize=8.5,
             color=C_SLD, arrowprops=dict(arrowstyle="->", lw=0.7, color=C_SLD))
ax1.plot([], [], "o", color="#1f4e8c", ms=6, label="adhesion → sliding 전환점 (위치 1 − λ)")
ax1.set_xlabel("contact patch 안의 위치  (0 = leading edge → 1 = trailing edge)")
ax1.set_ylabel("단위 길이당 힘 / 최대 한계")
ax1.set_title("(a) contact patch 안의 bristle 힘")
ax1.set_ylim(0, 1.12)
ax1.legend(fontsize=8, loc="upper right")

# (b) 힘 곡선 F/(μFz) = 1 − (1−λ)³, adhesion 비율 1 − λ
lam = np.linspace(0, 1.4, 500)
lc = np.minimum(lam, 1.0)
ax2.plot(lam, 1 - (1 - lc) ** 3, color="#1f4e8c", lw=2.4, label="F / (μ·Fz) = 1 − (1 − λ)³")
ax2.plot(lam, 3 * lam, color="k", lw=0.9, ls=":", label="선형 3λ  (= C·σ / (μ·Fz))")
ax2.plot(lam, np.maximum(1 - lam, 0), color=C_ADH, lw=1.8, ls="--", label="adhesion 비율 = 1 − λ")
ax2.axvline(1.0, color=C_SLD, lw=0.9)
ax2.text(1.03, 0.62, "λ = 1 (K = 3)\n전부 sliding\n→ saturation", color=C_SLD, fontsize=8.5)
top = ax2.secondary_xaxis("top", functions=(lambda x: 3 * x, lambda k: k / 3))
top.set_xlabel("PhysX 의 K = 3λ = C·σ / (μ·Fz)")
ax2.set_xlabel("λ = θ·σ")
ax2.set_ylabel("F / (μ·Fz)")
ax2.set_title("(b) 힘 곡선과 adhesion 비율", pad=24)
ax2.set_ylim(0, 1.15)
ax2.legend(fontsize=8.3, loc="lower right")

# (c) combined slip: ν(K), r = C_α/C_κ
r = 41.5184 / 176.0
K = np.linspace(0, 8, 500)
nu = np.where(K <= 2 * np.pi, 0.5 * (1 + r - (1 - r) * np.cos(K / 2)), 1.0)
ax3.plot(K, nu, color="#1f4e8c", lw=2.4, label=f"ν(K),  r = C_α/C_κ = {r:.3f} (임시값)")
ax3.axhline(r, color=C_ADH, lw=0.9, ls="--")
ax3.axhline(1.0, color=C_SLD, lw=0.9, ls="--")
ax3.text(4.6, r + 0.03, "K → 0: ν = C_α/C_κ\n힘 방향 ∝ stiffness × slip", color=C_ADH, fontsize=8.5)
ax3.text(0.15, 0.9, "K ≥ 2π: ν = 1\n힘 방향 = sliding 속도 반대", color=C_SLD, fontsize=8.5)
ax3.axvline(3.0, color="#999", lw=0.8, ls=":")
ax3.text(3.05, 0.5, "K = 3\n(saturation)", color="#666", fontsize=8)
ax3.set_xlabel("K")
ax3.set_ylabel("ν (nu)")
ax3.set_title("(c) combined slip 에서 힘 방향을 섞는 ν")
ax3.set_ylim(0, 1.1)
ax3.legend(fontsize=8.3, loc="lower right")

fig.tight_layout()
out = os.path.join(HERE, "brush_model.png")
fig.savefig(out)
print("wrote", out)
