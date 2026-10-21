"""타이어 모델 전체 흐름 — 매 물리 step(5 ms)마다 무엇을 계산하는지와 지금까지 끝난 단계.

실행: python make_pipeline_fig.py   (matplotlib. 한글 글꼴: WenQuanYi Zen Hei)
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False,
                     "savefig.dpi": 150})
DONE, DOING, TODO = "#d8efe0", "#fde3c2", "#e6e6e6"
EDGE = {DONE: "#2e8b57", DOING: "#d9822b", TODO: "#888888"}

fig, ax = plt.subplots(figsize=(16, 6.6))
ax.set_xlim(0, 16)
ax.set_ylim(0.1, 6.6)
ax.axis("off")


def box(x, y, w, h, title, body, tag, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.15",
                                fc=color, ec=EDGE[color], lw=1.8))
    ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="top", fontsize=12.5, fontweight="bold")
    ax.text(x + w / 2, y + h - 0.85, body, ha="center", va="top", fontsize=10, linespacing=1.45)
    ax.text(x + w / 2, y + 0.18, tag, ha="center", va="bottom", fontsize=9, color="#333")


def arrow(x0, y0, x1, y1, color="#444"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=16, lw=1.6, color=color))


W, H, Y = 2.75, 2.55, 1.1
xs = [0.2, 3.35, 6.5, 9.65, 12.8]
box(xs[0], Y, W, H, "① 바퀴 상태 읽기", "ω : 바퀴가 도는 속도\nv : 바퀴가 실제로\n움직이는 속도", "끝남", DONE)
box(xs[1], Y, W, H, "② 미끄러짐", "slip velocity\n= 바퀴 둘레 속도 − v\n(얼마나 헛도나·밀리나)", "끝남", DONE)
box(xs[2], Y, W, H, "③ 고무 휨 u", "미끄러진 만큼 휘고\n굴러가면서 풀린다\n(u = 고무가 휜 양)",
    "계산 함수 끝남\n시뮬레이터에 연결 중 ◀ 지금", DOING)
box(xs[3], Y, W, H, "④ 타이어 힘", "휜 양 → 힘\n많이 휘면 한계(μ·Fz)\n에서 더 안 늘어남", "계산 함수 끝남\n시뮬레이터 연결 남음", TODO)
box(xs[4], Y, W, H, "⑤ 차에 힘 가하기", "계산한 힘을 바퀴\n접지점에 가한다\n(PhysX 바퀴 마찰은 0)", "남음 (on/off 스위치로)", TODO)
for i in range(4):
    arrow(xs[i] + W + 0.02, Y + H / 2, xs[i + 1] - 0.02, Y + H / 2)
arrow(xs[4] + W / 2, Y - 0.35, xs[0] + W / 2, Y - 0.35, color="#999")
ax.text(8.0, 0.4, "다음 5 ms step 에서 바퀴 상태가 바뀌어 있다 → 다시 ①", ha="center", fontsize=9.5, color="#666")

IY, IH = 4.45, 1.55
box(4.0, IY, 3.6, IH, "바퀴가 받는 무게 Fz", "접촉 센서로 매 step 읽음", "끝남", DONE)
box(8.6, IY, 3.6, IH, "고무 강도 C", "정지 하중 × (1 N 당 값)", "끝남", DONE)
arrow(5.8, IY - 0.02, xs[2] + W * 0.55, Y + H + 0.02, color="#2e8b57")
arrow(10.4, IY - 0.02, xs[2] + W * 0.8, Y + H + 0.02, color="#2e8b57")
arrow(7.2, IY - 0.02, xs[3] + W * 0.25, Y + H + 0.02, color="#2e8b57")
arrow(10.9, IY - 0.02, xs[3] + W * 0.5, Y + H + 0.02, color="#2e8b57")
ax.text(0.25, 6.25, "타이어 모델 — 매 물리 step(5 ms)마다 하는 계산", fontsize=14, fontweight="bold")
for i, (c, t) in enumerate(((DONE, "끝남"), (DOING, "지금 하는 중"), (TODO, "남음"))):
    ax.add_patch(FancyBboxPatch((12.2 + i * 1.5, 6.12), 0.3, 0.3, boxstyle="round,pad=0.02", fc=c, ec=EDGE[c]))
    ax.text(12.58 + i * 1.5, 6.27, t, va="center", fontsize=9.5)
fig.savefig(os.path.join(HERE, "pipeline.png"), bbox_inches="tight")
print("wrote")
