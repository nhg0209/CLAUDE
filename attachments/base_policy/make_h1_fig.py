"""H1: Pure Pursuit geometry and the two clipping orders (residual curvature)."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [1, 1.25]})

# --- left: pure pursuit geometry -------------------------------------------
ax = axes[0]
Ld, eta = 0.7, np.radians(45)
P = np.array([Ld * np.sin(eta), Ld * np.cos(eta)])          # look-ahead point (car heading = +y)
kappa = 2 * np.sin(eta) / Ld
R = 1 / kappa
th = np.linspace(0, 2 * np.arcsin(Ld / (2 * R)), 100)
ax.plot(R - R * np.cos(th), R * np.sin(th), "tab:blue", lw=2, label=f"PP arc: kappa_PP = 2 sin(eta)/L_d = {kappa:.2f} 1/m")
Rmax = 1 / 1.349
th2 = np.linspace(0, 1.4, 100)
ax.plot(Rmax - Rmax * np.cos(th2), Rmax * np.sin(th2), "tab:red", ls="--", lw=1.5,
        label="tightest the car can turn: kappa_max = 1.35 1/m (24 deg)")
ax.annotate("", (0, 0.35), (0, 0), arrowprops=dict(arrowstyle="->", lw=2))
ax.text(-0.11, 0.15, "car\nheading", fontsize=9)
ax.plot([0, P[0]], [0, P[1]], "k:", lw=1)
ax.plot(*P, "o", color="tab:green", ms=9)
ax.text(P[0] + 0.03, P[1], "look-ahead point\n(distance L_d = 0.7 m)", fontsize=9, color="tab:green")
ax.text(0.04, 0.26, "eta = 45 deg", fontsize=9)
ax.plot(0, 0, "ks", ms=8)
ax.set_aspect("equal"); ax.set_xlim(-0.3, 1.5); ax.set_ylim(-0.15, 1.0)
ax.set_title("Pure Pursuit, 1 m/s, tight corner:\nPP circle (blue) is tighter than the car can turn (red)")
ax.legend(fontsize=8, loc="lower right"); ax.axis("off")

# --- right: clipping orders --------------------------------------------------
ax = axes[1]
kmax, kpp, b = 1.349, 2.02, 0.40
rows = [
    ("(A) add, then clip once", [(kpp - b, kpp + b, "kappa_PP + dk  (RL range)")], (kmax, kmax)),
    ("(B) clip PP, add, clip again", [(kmax - b, kmax + b, "clip(kappa_PP) + dk")], (kmax - b, kmax)),
]
for i, (name, spans, final) in enumerate(rows):
    y = 1 - i
    ax.text(0.0, y + 0.32, name, fontsize=11, weight="bold")
    for lo, hi, lab in spans:
        ax.plot([lo, hi], [y + 0.12, y + 0.12], color="tab:blue", lw=6, alpha=0.6)
        ax.text(lo, y + 0.18, lab, fontsize=9, color="tab:blue")
    ax.plot([final[0], final[1] + 1e-3], [y - 0.1, y - 0.1], color="tab:red", lw=6)
    if final[0] == final[1]:
        ax.plot(final[0], y - 0.1, "o", color="tab:red", ms=9)
        ax.text(final[0] + 0.05, y - 0.16, "after clip: always 1.35 -> RL output has NO effect", fontsize=9, color="tab:red")
    else:
        ax.text(final[0], y - 0.26, f"after clip: {final[0]:.2f} .. {final[1]:.2f} -> RL can still steer LESS", fontsize=9, color="tab:red")
    ax.axvline(kmax, color="tab:red", ls="--", lw=1)
ax.axvline(kpp, color="gray", ls=":", lw=1)
ax.text(kpp + 0.02, 1.62, "kappa_PP = 2.02", fontsize=9, color="gray")
ax.text(kmax + 0.02, 1.62, "kappa_max = 1.35", fontsize=9, color="tab:red")
ax.set_xlim(0, 2.7); ax.set_ylim(-0.6, 1.75); ax.set_yticks([])
ax.set_xlabel("curvature kappa [1/m]  (bigger = tighter turn)")
ax.set_title("Where to clip the curvature (RL correction dk in [-0.40, +0.40])")
fig.tight_layout()
fig.savefig(__file__.replace("make_h1_fig.py", "h1_clip.png"), dpi=130)
