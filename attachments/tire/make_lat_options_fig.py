"""lateral stiffness 임시값 선택지 — 앞바퀴 Fy/Fz – α 곡선 (Michigan, κ = 0, μ = 1, rest load).

(a) F1TENTH 값 그대로 C_α/Fz = 4.718 /rad
(b) F1TENTH 선형 모델이 μ 에 닿는 각(1/4.718 rad = 12.1°)에서 brush 가 saturation 되게: C_α/Fz = 3 / tan(1/4.718)
(c) 일반 타이어처럼 saturation 각 7° 로: C_α/Fz = 3 / tan(7°)
회색 점선: F1TENTH 선형 모델 Fy/Fz = C_S·α (상한 없음).

실행: python make_lat_options_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
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


def f1(k):
    k = np.minimum(k, 3.0)
    return k - k ** 2 / 3 + k ** 3 / 27


opts = [
    ("(a) F1TENTH 값 그대로", 4.718, "#d1495b"),
    ("(b) F1TENTH 의 한계 각에서 saturation", 3 / math.tan(1 / 4.718), "#1f4e8c"),
    ("(c) saturation 각 7°", 3 / math.tan(math.radians(7.0)), "#2e8b57"),
]
a = np.linspace(0, 40, 800)
t = np.tan(np.radians(a))
fig, ax = plt.subplots(figsize=(9.5, 5.2))
for lab, c, col in opts:
    sat = math.degrees(math.atan(3 / c))
    ax.plot(a, f1(c * t), color=col, lw=2.4, label=f"{lab}:  C_α/Fz = {c:.2f} /rad,  saturation {sat:.1f}°")
    ax.plot([sat], [1.0], "o", color=col, ms=6)
ax.plot(a, 4.718 * np.radians(a), color="#888", lw=1.2, ls="--", label="F1TENTH 선형 모델 C_S·α (상한 없음)")
ax.set_xlim(0, 40)
ax.set_ylim(0, 1.15)
ax.set_xlabel("slip angle α [deg]")
ax.set_ylabel("Fy / Fz")
ax.set_title("앞바퀴 lateral force 곡선 — 세 임시값 (μ = 1, rest load)")
ax.legend(fontsize=8.6, loc="lower right")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "lat_stiffness_options.png"))
for lab, c, col in opts:
    print(lab, round(c, 3), round(math.degrees(math.atan(3 / c)), 2))
