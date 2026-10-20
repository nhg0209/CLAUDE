"""병렬(지금 합의한 식) vs 직렬(carcass spring‖damper 가 contact 와 직렬) — 타이어만의 step 응답.

차체를 고정(무한 질량)하고 slip velocity s 가 t = 0 에 step 으로 생길 때 force F(t)/F_정상 (선형 구간 해석해).
  a = |v|/σ,  β = |v|·k/C,  F_정상 = C·s/|v|
  병렬: F/F_정상 = (1 − e^(−a·t)) + (k·|v|/C)·e^(−a·t)
  직렬: F/F_정상 = (1 − e^(−a'·t)) + (k·|v|/C)/(1+β)·e^(−a'·t),   a' = a/(1+β)
σ = 2 cm, |v| = 3 m/s (저속 코너), C_κ = 170 N (longitudinal), C_α = 41.5 N/rad (lateral, front 임시값).

실행: python make_series_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
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
    "font.size": 10,
})
SIG, V = 0.02, 3.0
t = np.linspace(0, 0.06, 600)


def resp(C, k, series):
    a = V / SIG
    beta = V * k / C
    jump = V * k / C
    if series:
        a, jump = a / (1 + beta), jump / (1 + beta)
    e = np.exp(-a * t)
    return (1 - e) + jump * e


fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4), sharey=True)
for ax, (name, C) in zip(axes, (("longitudinal (C_κ 170 N)", 170.0), ("lateral (C_α 41.5 N/rad)", 41.5))):
    ax.plot(t * 1000, resp(C, 0.0, False), color="#555", lw=1.6, ls="--", label="감쇠 없음 (k 0)")
    for k, col in ((10.0, "#2e8b57"), (40.0, "#1f4e8c")):
        ax.plot(t * 1000, resp(C, k, False), color=col, lw=2.0, label=f"병렬 k {k:.0f}")
        ax.plot(t * 1000, resp(C, k, True), color=col, lw=2.0, ls=":", label=f"직렬 k {k:.0f}")
    ax.axhline(1.0, color="k", lw=0.7)
    ax.set_title(f"{name}, |v| = {V} m/s, σ = 2 cm")
    ax.set_xlabel("slip velocity step 뒤 시간 [ms]")
    ax.legend(fontsize=8.3, loc="upper right")
axes[0].set_ylabel("F(t) / F_정상")
axes[0].set_ylim(0, 3.1)
fig.suptitle("타이어만의 step 응답 (차체 고정, 선형 구간) — 병렬 vs 직렬", fontsize=11.5)
fig.tight_layout()
out = os.path.join(HERE, "series_vs_parallel.png")
fig.savefig(out)
print("wrote", out)

for name, C in (("long", 170.0), ("lat", 41.5)):
    for k in (10.0, 40.0):
        beta = V * k / C
        print(f"{name} k={k:.0f}: 병렬 시작값 {V*k/C:.2f}, τ {SIG/V*1000:.1f} ms | 직렬 시작값 {V*k/C/(1+beta):.2f}, τ {SIG*(1+beta)/V*1000:.1f} ms")
