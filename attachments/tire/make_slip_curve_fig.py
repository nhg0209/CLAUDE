"""check_env ⑦ slip 곡선 시험 결과 그림 (서버 2026-10-23, rl-racing dev 60b4281, --tire-model).

입력: check7/slip_curve_mu1.0.csv · slip_curve_mu0.5.csv (check_env 가 쓴 0.1 s bin 표 그대로)
  f_meas  = M·Δv_x/Δt (차 전체 가속도 — 타이어 force 합의 독립 측정)
  f_model = 기록된 κ'·tanα'·F_z 를 Michigan 식(du = 0)에 넣은 네 바퀴 합
  f_applied = env 가 실제로 가한 Σf_x
(a) F/(μ·M·g) – κ'max  (b) 시간에 따른 오차 err = |f_meas − f_model|/(μ·M·g), 5% 판정선

실행: python make_slip_curve_fig.py   (matplotlib, numpy. 한글 글꼴: WenQuanYi Zen Hei)
"""
import os

import matplotlib
import matplotlib.ticker
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({
    "font.family": ["WenQuanYi Zen Hei", "DejaVu Sans"], "axes.unicode_minus": False,
    "figure.dpi": 110, "savefig.dpi": 150, "axes.grid": True, "grid.alpha": 0.3,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10.5,
    "mathtext.fontset": "dejavusans",
})
M, G = 3.47, 9.81
COL = {1.0: "#1f4e8c", 0.5: "#d1495b"}


def load(mu):
    d = np.genfromtxt(os.path.join(HERE, "check7", f"slip_curve_mu{mu}.csv"), delimiter=",", names=True,
                      dtype=None, encoding="utf-8")
    pre = np.array([str(x) == "True" for x in d["in_pre"]])
    return d, pre


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 5.0))
for mu in (1.0, 0.5):
    d, pre = load(mu)
    n = mu * M * G
    k = d["kappa_max"]
    ok = k < 0.55 if mu == 0.5 else np.ones_like(k, bool)
    ax1.plot(k, d["f_model"] / n, color=COL[mu], lw=1.6, label=f"μ = {mu}: Michigan 식 (기록된 κ'·F_z)")
    ax1.plot(k[pre], d["f_meas"][pre] / n, "o", color=COL[mu], ms=5, label=f"μ = {mu}: 측정 M·a — 정점 전(판정)")
    ax1.plot(k[~pre & ok], d["f_meas"][~pre & ok] / n, "o", mfc="none", color=COL[mu], ms=5,
             label=f"μ = {mu}: 측정 — 보고만")
    if mu == 0.5:
        bad = ~ok
        ax1.plot(k[bad], np.clip(d["f_meas"][bad] / n, -0.05, None), "x", color=COL[mu], ms=6,
                 label="μ = 0.5: 측정 — κ' > 0.55 (차가 돌기 시작, 아래 설명)")
    ax2.semilogy(d["t_mid"], np.maximum(d["err"], 1e-5), "o-", color=COL[mu], ms=4, lw=1.2, label=f"μ = {mu}")
ax1.axvline(0.15, color="#999", lw=0.9, ls=":")
ax1.text(0.16, 0.25, "μ-slip 정점\nκ' = 0.15", fontsize=8.5, color="#555")
ax1.set_xlabel("κ' max (네 바퀴 중 최대 휨 비율)")
ax1.set_ylabel("F / (μ·M·g)")
ax1.set_title("(a) slip 곡선 — 측정 M·a 대 Michigan 식")
ax1.set_xlim(0, 1.02)
ax1.set_ylim(-0.05, 1.1)
ax1.legend(fontsize=7.6, loc="lower right")
ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
ax2.axhline(0.05, color="#555", lw=1.0, ls="--")
ax2.text(0.6, 0.065, "판정선 5%", fontsize=8.5, color="#555")
ax2.axvspan(3.65, 4.55, color=COL[0.5], alpha=0.08)
ax2.text(3.0, 2.5, "μ = 0.5 정점 뒤 wheelspin\n→ 차가 돌기 시작해\nM·Δv_x/Δt 가 force 측정이 아님", fontsize=8.3, color=COL[0.5])
ax2.set_xlabel("시간 [s] (0.5 s 정착 뒤 4 s 토크 램프)")
ax2.set_ylabel("err = |F_meas − F_model| / (μ·M·g)")
ax2.set_title("(b) 구간별 오차 — 정점 전 최대 0.21% (μ 1) · 0.52% (μ 0.5)")
ax2.legend(fontsize=8.5, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "slip_curve_check7.png"))
print("wrote")
