"""저속 감쇠항 형태 비교 그림 — toy/ 의 바퀴 하나 장난감 모델 (relaxation length σ 2 cm, exp 갱신, |u/σ| ≤ 1).

(a) wheelspin 출발(τ 1.0 N·m): 감쇠 force 를 friction 한계로 자르지 않으면 μ·Fz(8.5 N)를 넘는다.
(b) 1.5 m/s 주행 중 slip velocity 0.05 m/s transient: 감쇠 없음 / (나) v_low 1 m/s / (나) 항상 켬.
(가)·(나) 는 정지 근처에서 같은 식이 되므로 (b) 에는 (나) 만 그린다.

실행: python make_damping_fig.py   (matplotlib. 한글 글꼴: WenQuanYi Zen Hei)
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "toy"))
import damp2  # noqa: E402
import toy  # noqa: E402

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
DT = 0.005
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.3))

for form, clamp, c, ls, lab in (("none", True, "#999", "--", "감쇠 없음"),
                                ("slipvel", False, "#d1495b", "-", "(가) 감쇠, friction 한계로 안 자름"),
                                ("slipvel", True, "#1f4e8c", "-", "(가)·(나) 감쇠, 한계로 자름")):
    Fs, _, _ = damp2.run(1.0, 0.25, form, clamp=clamp)
    ax1.plot([DT * (i + 1) for i in range(len(Fs))], Fs, color=c, ls=ls, lw=1.6, label=lab)
ax1.axhline(toy.MU * toy.FZ, color="k", lw=0.8, ls=":")
ax1.text(0.16, toy.MU * toy.FZ + 0.4, "μ·Fz = 8.5 N", fontsize=9)
ax1.set_xlabel("시간 [s]")
ax1.set_ylabel("Fx [N]")
ax1.set_title("(a) wheelspin 출발 (τ 1.0 N·m)")
ax1.legend(fontsize=8.5, loc="upper right")
ax1.set_ylim(0, 17)

v0 = 1.5
for form, vlow, c, ls, lab in (("none", 1.0, "#999", "--", "감쇠 없음 (relaxation 자체 감쇠만)"),
                               ("udot", 1.0, "#2e8b57", "-", "(나) v_low 1 m/s — 1.5 m/s 에서는 꺼져 있음"),
                               ("udot", 1e9, "#1f4e8c", "-", "(나) 항상 켬 (c 40 N·s/m)")):
    Fs, _, _ = damp2.run(0.0, 0.12, form, clamp=True, w0=(v0 + 0.05) / toy.R, v0=v0, vlow=vlow)
    ax2.plot([DT * (i + 1) for i in range(len(Fs))], Fs, color=c, ls=ls, lw=1.6, label=lab)
ax2.axhline(0, color="k", lw=0.6)
ax2.set_xlabel("시간 [s]")
ax2.set_ylabel("Fx [N]")
ax2.set_title("(b) 1.5 m/s 주행 중 slip velocity 0.05 m/s transient")
ax2.legend(fontsize=8.5, loc="upper right")

fig.tight_layout()
out = os.path.join(HERE, "damping_forms.png")
fig.savefig(out)
print("wrote", out)
