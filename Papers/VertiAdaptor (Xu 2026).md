---
tags: [paper]
제목: "VertiAdaptor: Online Kinodynamics Adaptation for Vertically Challenging Terrain"
저자: Tong Xu, Chenhui Pan, Aniket Datar, Xuesu Xiao
연도: 2026
학회: ❓ (arXiv preprint)
arxiv: 2603.06887
소속: George Mason University
플랫폼: Verti-4-Wheeler (1/10 scale) · Verti-Bench 시뮬 (Chrono)
지형: vertically challenging terrain
이해도: 🔴
상태: 질의응답 중
읽은날짜: 2026-09-15
---

# VertiAdaptor (VA)

[[논문 목록]]

> [!warning] 이 노트의 현재 상태
> **본문 정리는 아직 하지 않았다.** 지금은 서지 정보와 「❓ 질문」만 있다.
> 질의응답이 진행되는 대로 아래에 쌓고, 본문 정리는 요청이 있을 때 작성한다.

> [!info] 서지
> `arXiv:2603.06887v3` (2026-06-29) · 8페이지 · 저자 전원 George Mason University 전산학과
> 절 구성: I Introduction · II Related Work · III Method · IV Implementations ·
> V Experiments · VI Conclusions and Limitations

---

## 📖 용어

| 용어·기호 | 이 논문에서의 뜻 | 비고 |
|---|---|---|

---

## ❓ 질문

전체 색인은 [[질문 로그]].

### Q. meta-learning이 무엇인가?

**A.** §II-B 첫 문장이 정의한다.

> *"Meta-learning, or **'learning to learn'**, has significant advancement in robotics as a means of **enabling agents to adapt quickly to new tasks or environments with limited data**."*

**학습 대상이 파라미터가 아니라 초기값이다.** §II-B:

> *"Early approaches, such as MAML, demonstrate that models can be **initialized to adapt rapidly with just a few gradient updates**. Such property is particularly useful for robotics where **real-world data collection is expensive**."*

§IV-C의 baseline 서술이 더 구체적이다:

> *"First-order MAML is designed to **learn initialization parameters** that enable rapid adaptation.
> During offline training, the model learns **across diverse terrain distributions** using the standard MAML objective."*

여기서 **"task" = 지형 종류**다.

**이 논문에서의 위치 — 목표는 공유하되 방법은 쓰지 않는다.**

§I은 방향으로 제시한다:

> *"meta-learning offers a **promising path** toward rapid online adaptation. Meta-trained kinodynamic models
> can be quickly updated with a small amount of recent data to track changes such as new terrain or partial system failures."*

§II-B가 한계를 지적한다:

> *"gradient-based adaptation methods often suffer from **computational overhead and convergence issues** during onboard deployment."*

VA는 gradient 대신 **function encoder의 최소제곱**을 쓴다 (§III-C). 기저함수를 미리 학습해두고
새 지형에서는 계수 $\alpha$ 만 closed form으로 푼다:

$$x_{t+1} - x_t = \sum_{i=1}^{k}\alpha_i\,G_i(x_t, u_t, e_t;\theta_i)$$

**Table II 실측:**

| 방법 | 적응 방식 (§IV-C) | Adaptation Time | MSE (low / med / high) |
|---|---|---|---|
| **VA** | 최소제곱 closed form | **0.309 / 0.306 / 0.311 s** | 0.177 / 0.760 / 2.161 |
| Neural ODE | 500 gradient step | 1.715 / 1.737 / 1.734 s | 0.200 / 0.999 / 3.128 |
| **MAML** | **20,000 gradient step** | **11.175 / 11.366 / 10.616 s** | 0.186 / 0.814 / **2.093** |
| MLP | 40,000 gradient step (마지막 층만) | 40.889 / 40.556 / 40.777 s | 0.214 / 0.904 / 2.214 |

⚠️ **high elevation에서는 MAML(2.093)이 VA(2.161)보다 정확하다.** §V-A는 VA가
*"only a 3.2% higher MSE compared to the best-performing MAML"* 라고 적는다. 차이는 속도 쪽이다.

§V-D:

> *"the **significant computation disallows MAML do adapt online**"*

그래서 시뮬 항법 실험에서는 MAML을 **한 번만 적응시킨 `MAML*`** 로 비교했다.

> [!warning] MAML 인용이 원논문이 아니다
> 논문은 MAML을 §I에서 `[17]`, §II-B에서 `[28]`로 인용하는데 **둘 다 MAML 원논문이 아니다.**
>
> | | 참고문헌 목록의 실제 항목 |
> |---|---|
> | `[17]` | Nagabandi et al., *"Learning to adapt in dynamic, real-world environments through meta-reinforcement learning"*, arXiv:1803.11347, 2018 |
> | `[28]` | Finn, Rajeswaran, Kakade, Levine, *"Online meta-learning"*, ICML 2019 |
>
> `[28]`은 §II-B의 *"Methods such as online meta-learning [28]"* 에서는 맞게 쓰였다. MAML 귀속만 어긋난다.
