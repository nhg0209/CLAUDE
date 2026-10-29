"""Pure delay d + first-order lag tau: step and sine responses (T3 options)."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DT = 0.001
CASES = [  # label, d [s], tau [s], style
    ("real fit  d=15ms  tau=0.10s", 0.015, 0.10, dict(color="black", lw=2.2)),
    ("(A) delay only  d=55ms  tau=0.06s", 0.055, 0.06, dict(color="tab:red", lw=1.6)),
    ("(B) split like real  d=25ms  tau=0.09s", 0.025, 0.09, dict(color="tab:blue", lw=1.6, ls="--")),
]


def respond(u, d, tau):
    n = int(round(d / DT))
    ud = np.concatenate([np.full(n, u[0]), u[:-n or None]]) if n else u
    a = 1.0 - np.exp(-DT / tau)
    y = np.empty_like(u)
    y[0] = u[0]
    for k in range(1, len(u)):
        y[k] = y[k - 1] + a * (ud[k - 1] - y[k - 1])
    return y


fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))

t = np.arange(-0.05, 0.40, DT)
u = (t >= 0).astype(float)
ax = axes[0]
ax.plot(t * 1000, u, color="gray", lw=1, label="command")
for label, d, tau, st in CASES:
    ax.plot(t * 1000, respond(u, d, tau), label=label, **st)
ax.axhline(0.632, color="gray", lw=0.6, ls=":")
ax.axvline(115, color="gray", lw=0.6, ls=":")
ax.set_title("Step command: all reach 63% near d+tau = 115 ms")
ax.set_xlabel("time [ms]")
ax.set_ylabel("steering angle / command")
ax.legend(fontsize=8, loc="lower right")

for ax, f in zip(axes[1:], [1.0, 4.0]):
    t = np.arange(0, 3.0, DT)
    u = np.sin(2 * np.pi * f * t)
    m = t >= 3.0 - 2.0 / f
    ax.plot(t[m] * 1000, u[m], color="gray", lw=1, label="command")
    for label, d, tau, st in CASES:
        w = 2 * np.pi * f
        amp = 1 / np.sqrt(1 + (w * tau) ** 2)
        lag = (w * d + np.arctan(w * tau)) / w * 1000
        ax.plot(t[m] * 1000, respond(u, d, tau)[m], label=f"amp {amp:.2f}, lag {lag:.0f} ms", **st)
    ax.set_title(f"Sine command {f:.0f} Hz")
    ax.set_xlabel("time [ms]")
    ax.legend(fontsize=8, loc="lower right")

fig.tight_layout()
fig.savefig(__file__.replace("make_delay_fig.py", "delay_vs_lag.png"), dpi=130)
