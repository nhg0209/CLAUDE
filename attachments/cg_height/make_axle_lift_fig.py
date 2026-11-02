"""Axle-lift CG height measurement (ISO 10392 style) — side-view schematic."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Polygon

L, r, hc, lf = 0.33, 0.051, 0.024, 0.159   # wheelbase, wheel radius, CG height above axle line, front axle -> CG
th = np.radians(25)
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))

def car(ax, theta, title):
    fx, fz = 0.0, r                        # front wheel centre (on scale top = 0)
    ex = np.array([-np.cos(theta), np.sin(theta)])   # body axis front -> rear (rear goes up)
    ez = np.array([np.sin(theta), np.cos(theta)])    # body up
    F = np.array([fx, fz]); R = F + L * ex
    G = F + lf * ex + hc * ez
    for c in (F, R):
        ax.add_patch(Circle(c, r, fill=False, lw=2))
        ax.plot(*c, "k.", ms=4)
    ax.plot([F[0], R[0]], [F[1], R[1]], "k-", lw=1)                       # axle line
    body = [F + 0.02 * ez - 0.03 * ex, R + 0.02 * ez + 0.03 * ex, R + 0.05 * ez + 0.03 * ex, F + 0.05 * ez - 0.03 * ex]
    ax.add_patch(Polygon(body, closed=True, fill=False, ls="--", color="gray"))
    ax.plot(*G, "o", color="tab:red", ms=9)
    ax.annotate("CG", G + np.array([0.008, 0.008]), color="tab:red")
    foot = F + lf * ex
    ax.plot([foot[0], G[0]], [foot[1], G[1]], color="tab:red", lw=1.5)
    ax.annotate("h_c", (foot + G) / 2 + np.array([0.006, -0.004]), color="tab:red")
    ax.annotate("", G + np.array([0, -0.06]), G, arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax.annotate("W", G + np.array([0.005, -0.055]), color="tab:red")
    ax.add_patch(Rectangle((-0.06, -0.02), 0.12, 0.02, color="tab:blue", alpha=0.4))   # scale
    ax.annotate("scale (front axle)\nreads W_f", (-0.06, -0.06), color="tab:blue", fontsize=9)
    rz = R[1] - r
    ax.add_patch(Rectangle((R[0] - 0.05, -0.02), 0.1, rz + 0.02, color="tab:brown", alpha=0.35))
    if theta > 0:
        ax.annotate(f"block\nH = L sin(theta)", (R[0] - 0.05, rz / 2), fontsize=9)
        ax.annotate(f"theta = {np.degrees(theta):.0f} deg", (F[0] - 0.12, F[1] + 0.03))
    ax.plot([-0.45, 0.12], [0, 0], color="k", lw=0.8)
    ax.annotate("r", (F[0] + 0.004, r / 2))
    ax.set_aspect("equal"); ax.set_xlim(-0.46, 0.14); ax.set_ylim(-0.08, 0.26); ax.axis("off")
    ax.set_title(title)

car(axes[0], 0.0, "1) level: W_f0 = W * l_r / L")
car(axes[1], th, "2) rear lifted: CG moves toward front axle -> W_f increases")
fig.tight_layout()
fig.savefig(__file__.replace("make_axle_lift_fig.py", "axle_lift.png"), dpi=130)
