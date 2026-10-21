"""longitudinal stiffness · lateral (cornering) stiffness 설명 그림.

(a) longitudinal: Fx/Fz – κ 곡선과 처음 기울기 C_κ/Fz (Michigan, α = 0)
(b) lateral: Fy/Fz – α 곡선과 처음 기울기 C_α/Fz, F1TENTH 선형 모델(상한 없음)과 비교
(c) normal load 에 따른 stiffness — PhysX 식: longStiff 는 상수, lateral 은 latStiffY·f1(3·Fz/(rest·latStiffX))
식은 PhysX VhTireFunctions.cpp (tire.py T2b 와 같다). 계수는 합의한 임시값(앞바퀴): rest load 8.8 N, C_κ/Fz 20,
C_α/Fz 4.718 /rad, latStiffX 2, μ 1, μ-slip 3점 (0,1)·(0.15,1)·(1,0.8).

실행: python make_stiffness_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
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
REST, MU, LAT_X = 8.8, 1.0, 2.0
C_K = 20.0 * REST
PTS = ((0.0, 1.0), (0.15, 1.0), (1.0, 0.8))


def f1(k):
    k = np.minimum(k, 3.0)
    return k - k ** 2 / 3 + k ** 3 / 27


LAT_Y = 4.718 * REST / f1(3.0 / LAT_X)


def g(k):
    k = np.abs(k)
    (x0, y0), (x1, y1), (x2, y2) = PTS
    return np.where(k < x1, y0 + (y1 - y0) * (k - x0) / (x1 - x0),
                    np.where(k < x2, y1 + (y2 - y1) * (k - x1) / (x2 - x1), y2))


def c_alpha(fz):
    return LAT_Y * f1(fz / REST * 3.0 / LAT_X)


fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 4.8))

# (a) longitudinal
k = np.linspace(0, 0.5, 600)
mu_eff = MU * g(k)
fx = mu_eff * f1(C_K * k / (mu_eff * REST))
ax1.plot(k, fx, color="#1f4e8c", lw=2.4, label="Fx/Fz (Michigan, α = 0)")
ax1.plot(k[k < 0.06], 20 * k[k < 0.06], color="k", lw=1.0, ls="--", label="처음 기울기 C_κ/Fz = 20")
ax1.axvline(0.15, color="#d1495b", lw=0.9, ls=":")
ax1.text(0.155, 0.35, "saturation\nκ = 3μ/(C_κ/Fz) = 0.15\n(= μ-slip 정점에 맞춤)", fontsize=8.5, color="#d1495b")
ax1.annotate("κ 0.01 → Fx ≈ 0.2·Fz\n(1% slip 로 체중의 20%)", xy=(0.01, 0.197), xytext=(0.05, 0.62), fontsize=8.5,
             arrowprops=dict(arrowstyle="->", lw=0.7))
ax1.set_xlabel("slip ratio κ")
ax1.set_ylabel("Fx / Fz")
ax1.set_title("(a) longitudinal stiffness C_κ — Fx–κ 의 처음 기울기")
ax1.set_ylim(0, 1.15)
ax1.legend(fontsize=8.5, loc="lower right")

# (b) lateral
a_deg = np.linspace(0, 45, 600)
t = np.tan(np.radians(a_deg))
fy = MU * f1(c_alpha(REST) * t / (MU * REST))
ax2.plot(a_deg, fy, color="#2e8b57", lw=2.4, label="Fy/Fz (Michigan, κ = 0)")
ax2.plot(a_deg, 4.718 * np.radians(a_deg), color="#888", lw=1.2, ls="-.", label="F1TENTH 선형 모델 C_S·α (상한 없음)")
sat = math.degrees(math.atan(3 * MU / 4.718))
lin = math.degrees(MU / 4.718)
ax2.axvline(sat, color="#d1495b", lw=0.9, ls=":")
ax2.text(sat + 0.6, 0.3, f"saturation\ntanα = 3μ/(C_α/Fz)\n→ α = {sat:.1f}°", fontsize=8.5, color="#d1495b")
ax2.axvline(lin, color="#888", lw=0.8, ls=":")
ax2.text(lin + 0.5, 1.05, f"선형 모델이 μ 에 닿는 α = {lin:.1f}°\n(brush 는 여기서 70%)", fontsize=8.2, color="#666")
ax2.set_xlabel("slip angle α [deg]")
ax2.set_ylabel("Fy / Fz")
ax2.set_title("(b) cornering stiffness C_α — Fy–α 의 처음 기울기")
ax2.set_ylim(0, 1.2)
ax2.legend(fontsize=8.3, loc="lower right")

# (c) stiffness vs load
fz = np.linspace(0, 3.2 * REST, 400)
ax3.plot(fz, c_alpha(fz), color="#2e8b57", lw=2.4, label="C_α(Fz) = latStiffY·f1(3·Fz/(rest·latStiffX))")
ax3.plot(fz, np.full_like(fz, C_K) / 4, color="#1f4e8c", lw=2.0, label="C_κ / 4 (PhysX: load 와 무관한 상수)")
ax3.plot(fz, 20 * fz / 4, color="#1f4e8c", lw=1.0, ls="--", label="C_κ / 4 가 Fz 에 비례한다면 (실제 타이어에 가까움)")
ax3.plot([REST], [c_alpha(REST)], "o", color="#2e8b57", ms=6)
ax3.annotate(f"rest load 8.8 N → {c_alpha(REST):.1f} N/rad\n(= 4.718 × 8.8)", xy=(REST, c_alpha(REST)),
             xytext=(10.5, 20), fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.7))
ax3.axvline(LAT_X * REST, color="#999", lw=0.8, ls=":")
ax3.text(LAT_X * REST + 0.3, 27, f"latStiffX·rest = {LAT_X * REST:.1f} N\n이후 평평 (latStiffY = {LAT_Y:.1f})", fontsize=8.2, color="#555")
d = 4.4
s0, s1 = 2 * c_alpha(REST), c_alpha(REST + d) + c_alpha(REST - d)
ax3.text(0.6, 52, f"load transfer: 8.8±4.4 N 이면 축 합 C_α\n{s0:.1f} → {s1:.1f} N/rad ({(s1 / s0 - 1) * 100:+.0f}%)",
         fontsize=8.5, color="#2e8b57")
ax3.set_xlabel("normal load Fz [N]")
ax3.set_ylabel("stiffness [N/rad] · [N/unit slip ÷ 4]")
ax3.set_title("(c) normal load 에 따른 stiffness (PhysX 식)")
ax3.set_ylim(0, 62)
ax3.legend(fontsize=7.8, loc="lower right")

fig.tight_layout()
out = os.path.join(HERE, "stiffness.png")
fig.savefig(out)
print("wrote", out, " sat", round(sat, 2), "lin", round(lin, 2), "axle", round(s0, 2), round(s1, 2),
      " brush at lin", round(float(f1(1.0)), 3), " Kus rad/g", round(1 / 4.718 - 1 / 5.4562, 4),
      "deg/g", round(math.degrees(1 / 4.718 - 1 / 5.4562), 3))
