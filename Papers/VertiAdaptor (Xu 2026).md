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
| $f_\theta$ | 상태 변화율을 내놓는 forward kinodynamic model = **ODE의 우변** | §III-A |
| $\theta = \{\theta_1,\dots,\theta_k\}$ | 각 기저함수 신경망의 가중치 | **오프라인 학습 후 frozen** (§III-D-1) |
| $\boldsymbol{\alpha} = [\alpha_1,\dots,\alpha_k]$ | 기저함수 **결합 계수** | **온라인에서 5초마다 최소제곱** (§III-D-2) |
| $G_i(\cdot\,;\theta_i)$ | $g_i$ 를 $\Delta t$ 동안 **RK4로 적분**한 것. 상태 **변화량**을 출력 | §III-C, Alg. 1 line 17 |
| $g_i$ | **신경망 본체.** 상태 **변화율**을 출력. $\theta_i$ 가 붙는 곳 | §III-C, Alg. 1 line 3 |
| $e_t = [e_{\text{elev}}, e_{\text{sem}}]$ | 차량 아래 지형의 elevation + semantic embedding | §III-B |
| $k$ | 기저함수 개수 = **24** | Table I |
| **SWAE** | Sliced-Wasserstein Autoencoder [16]. elevation·semantic 맵을 latent로 압축 | §III-B, §IV-A. **원리 설명은 없음** |
| $e_{\text{elev}}, e_{\text{sem}}$ | 각각 $\mathbb{R}^8$. SWAE 인코더 출력을 3-layer MLP로 추가 압축 | §IV-A |
| ⚠️ $\alpha$ (Alg. 1) | **학습률로도 쓰인다** — line 1, line 25 | 계수 $\alpha$ 와 충돌 |

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

### Q. "The function $f_\theta$ is parameterized by a set of neural ODEs" — parameterized가 무슨 뜻인가?

**A.** 두 겹이다.

**① $f_\theta$ 의 아래첨자** — 함수를 하나로 고정하지 않고 **파라미터로 지정되는 함수 집합**으로 둔다는 표시.
$\theta$ 를 정하면 함수 하나가 정해진다. *(일반 표기 관례이고 논문이 정의하지는 않는다.)*

**② "by a set of neural ODEs"** — 그 함수의 **형태**를 무엇으로 잡았는가.

§III-A에서 $f_\theta$ 는 **ODE의 우변**이다:

$$\dot{x}_t = f_\theta(x_t, u_t, e_t)$$

고전 kinodynamic 모델은 이 우변을 물리 법칙으로 손으로 쓰고, neural ODE는 **신경망으로 대체**한다.
§II-A가 고전 모델을 버린 이유:

> *"The assumption of known, constant terrain parameters rarely holds in practice, and the models often fail to capture
> nonlinear effects such as **dynamic loading, tire deformation, and complex multi-terrain interactions**."*

적분은 RK4로 수치 계산한다 (§III-C).

**③ ★ 이 논문에서 파라미터가 두 층으로 갈린다.** §III-C:

$$x_{t+1} - x_t = \sum_{i=1}^{k}\alpha_i\,G_i(x_t, u_t, e_t;\theta_i)$$

> *"where $G_i(\cdot;\theta_i)$ are a set of learnable basis functions **parameterized by neural ODEs and $\theta_i$**"*

| 파라미터 | 무엇 | 언제 정해지나 |
|---|---|---|
| $\theta$ | 기저함수 신경망 가중치 | **오프라인** — Alg. 1 line 25: $\theta \leftarrow \theta - \alpha\nabla_\theta L$ |
| $\boldsymbol{\alpha}$ | 기저함수 결합 계수 | **온라인** — 최소제곱 식 (1) |

§III-D-1 마지막 문장:

> *"After convergence, the **basis functions are frozen** and ready for online adaptation."*

§III-D-2:

> *"During deployment, VA continuously adapts **the coefficients $\alpha$ every 5 seconds** using recent trajectories."*

신경망 가중치를 건드리지 않고 계수 $k=24$개만 다시 풀기 때문에 gradient가 필요 없고,
§III-C의 표현대로 *"a maximum time complexity of $O(k^3)$"* 로 끝난다 (→ Table II의 0.31 s).

구조는 Table I: 기저함수 $k = 24$, hidden dim $\lfloor 64\sqrt{k}\rfloor = 313$, ReLU, 출력 6차원(6-DoF 상태 변화).

> [!warning] Algorithm 1의 기호 충돌
> $\alpha$ 가 같은 알고리즘 안에서 두 뜻으로 쓰인다.
>
> | 위치 | 뜻 |
> |---|---|
> | line 1 *"learning rate $\alpha$"* | 학습률 |
> | line 10 *"Compute coefficients $\alpha^{*(f)}$"* | 기저함수 계수 |
> | line 25 $\theta \leftarrow \theta - \alpha\nabla_\theta L$ | 학습률 |
>
> 논문은 이를 언급하지 않는다.

### Q. SWAE가 무엇인가?

**A.** 이 논문에서의 역할은 **지형 맵을 작은 벡터로 압축**하는 것이다. §III-B:

> *"To facilitate efficient modeling and adaptation, we use SWAE [16] to
> **project raw elevation and semantic maps into a compact latent space**."*

**파이프라인** (§IV-A):

```
차량 아래 128×128 픽셀 패치, 10 Hz, 차체 헤딩에 정렬
  ├ elevation : 2.5D 맵 (차량 현재 고도를 기준으로 중심화)
  └ semantic  : BEV RGB 이미지
        ↓  SWAE 인코더
     64차원 latent
        ↓  3-layer MLP로 추가 압축
  e_elev ∈ R^8 ,  e_sem ∈ R^8
        ↓
  상태벡터 [0, 0, 0, roll, pitch, 0, e_elev, e_sem] ∈ R^22
```

22 = 6(pose) + 8 + 8. 위치 $(x,y,z)$ 와 yaw를 0으로 두는 이유는 §IV-A가 밝힌다:

> *"Since the mobile robot's kinodynamics are **invariant under translation and rotation**,
> we adopt a **gravity-aligned body frame** to enhance data efficiency and improve model accuracy."*

roll·pitch는 world frame 값을 유지한다.

**왜 압축이 필요한가** — §I:

> *"unifying elevation and semantics with real-time adaptation within a single framework remains an open challenge,
> due to the **large space and variability of the elevation and semantic input** and **limited onboard computation**."*

> [!note] SWAE의 원리는 논문 밖 내용
> 논문은 SWAE를 **인용만 하고 원리를 설명하지 않는다.** 참고문헌 [16]의 제목이
> 성격을 보여준다 — Kolouri, Pope, Martin, Rohde,
> *"Sliced-Wasserstein autoencoder: An embarrassingly simple generative model"*, arXiv:1804.01947, 2018.
>
> (일반 설명: 오토인코더의 latent 분포를 미리 정한 분포에 맞추도록 정규화하는 변형.
> 고차원 분포 거리를 직접 재는 대신 무작위 방향으로 1차원 사영(slice)해 Wasserstein 거리를 재고 평균낸다.)

**논문에 없는 것 ❓**
- SWAE의 원리·학습 방법
- **SWAE를 다른 인코더로 바꾼 비교.** Table III의 ablation은 embedding을 *빼는* 실험이지
  SWAE 자체를 대체한 실험이 아니다 → "SWAE여야 했는가"의 근거는 없다
- *"64-dimensional latent"* 가 elevation·semantic **각각 64인지 합쳐서 64인지** 미명시.
  최종이 8+8인 것만 확실하다

**참고 — Table III (ablation, MSE)**

| Variant | Low | Medium | High |
|---|---|---|---|
| VA (Proposed) | **0.177** | **0.760** | **2.161** |
| VA w/o semantic | 0.201 | 0.761 | 2.292 |
| VA w/o elevation | 0.220 | 0.840 | 2.559 |
| VA w/o both | **0.177** | 0.761 | 3.038 |

§V-B의 해석: high elevation에서 elevation 제거 시 **+18.4%**, semantic 제거 시 **+6.1%**,
둘 다 제거 시 **+40.5%**. 단 low elevation에서는 *"the VA w/o both **also achieves an MSE of 0.177**,
indicating that for low elevation level, basic kinodynamic modeling using only the 6-DoF pose is sufficient"*.

### Q. latent이 무엇이고, "무작위 방향으로 1차원에 사영해 Wasserstein 거리를 잰다"는 게 무슨 뜻인가?

> [!warning] 전부 논문 밖 내용
> VertiAdaptor는 SWAE를 **인용만 하고 원리를 다루지 않는다.** 아래는 일반 설명이다.
> 용어 정의는 [[용어 사전]]에도 넣었다.

**① latent** — 오토인코더가 입력을 압축한 중간 벡터. 이 논문 기준:

```
128×128 elevation 맵   (숫자 16,384개)
        ↓  인코더
     64개 숫자                    ← latent
        ↓  디코더
   128×128 맵 복원
```

"잠재"인 이유는 그 64개 축이 원본에 직접 보이지 않기 때문이다. 축에 이름이 없다 — 학습으로 생긴 것이라서.

**② 왜 latent 분포에 제약을 거는가** — 보통 오토인코더는 복원만 잘 되면 끝이라
latent 점들이 제멋대로 흩어진다. 뭉치거나 빈 구멍이 생긴다.
빈 구멍의 latent를 디코더에 넣으면 쓰레기가 나오고, 비슷한 입력끼리 멀어질 수도 있다.
그래서 "정규분포처럼 고르게 퍼져 있어라"는 제약을 건다.

**③ Wasserstein 거리** — 두 분포가 얼마나 다른지 재는 방법. 별명 **earth mover's distance**.

```
P를 Q 모양으로 만들려면 흙을 얼마나 멀리, 얼마나 많이 옮겨야 하나?
그 최소 비용 = Wasserstein 거리
```

**④ 왜 sliced인가 — 계산 비용** — 고차원에서는 최적수송 문제라 비싸다.
**1차원에서는 정렬 후 순서대로 빼면 끝**이고, 그것이 최적임이 증명돼 있다.

```
P = [3, 1, 7, 5]      Q = [2, 8, 4, 6]
정렬 →  P = [1, 3, 5, 7]   Q = [2, 4, 6, 8]
|1-2| + |3-4| + |5-6| + |7-8| = 4
```

**⑤ 사영(slice) 절차**

```
1. 무작위 방향 벡터 v 를 뽑는다
2. 모든 latent 점을 v 방향으로 사영     → 1차원 숫자들
3. 목표 분포(정규분포)도 같은 방향으로 사영
4. 두 1차원 집합의 Wasserstein 거리 = 정렬 후 빼기
5. 방향을 여러 개 뽑아 반복하고 평균
```

사영은 **그림자**다. 여러 방향에서 본 그림자가 전부 같으면 원래 분포도 같다고 본다
(여러 각도의 X선 그림자로 내부를 복원하는 CT와 같은 원리).

**한 줄**: 어려운 고차원 거리 계산을 *"여러 방향의 1차원 그림자에서 정렬하고 빼기"* 로 바꾼 것.
[16]의 제목이 *"An **embarrassingly simple** generative model"* 인 이유.

### Q. SWAE를 쓰는 이유는 결국 고차원 elevation·semantic 정보를 state 배열에 넣기 위해 압축하는 것이고, 그 벡터에 지형 정보가 녹아 있어야 하는 것인가?

**A.** 그렇다. §IV-A가 두 가지를 다 적는다:

> *"we employ the SWAE generative model to embed elevation and semantic patches into a 64-dimensional latent space,
> **preserving both geometric and semantic information** for downstream kinodynamic modeling."*

**압축**이 목적, **정보 보존**이 요구조건. 세 가지를 더 정확히 잡아둔다.

**① 압축이 두 단계다.** SWAE만으로 8차원까지 가지 않는다.

```
128×128 패치
    ↓  SWAE 인코더
  64차원
    ↓  3-layer MLP          ← 별도 단계
  e_elev ∈ R^8 , e_sem ∈ R^8
```

§IV-A: *"The terrain embeddings e_elev ∈ R^8 and e_sem ∈ R^8 are derived from the SWAE encoder
and **further compressed by a 3-layer MLP**."*

**② state 배열에 넣는 이유는 ODE의 형태다.** §III-A:

$$\dot{x}_t = f_\theta(x_t, u_t, e_t)$$

$e_t$ 가 $f_\theta$ 의 **인자**다. 지형 정보가 없으면 같은 상태·같은 조향에 항상 같은 결과가 나온다.
§III-B가 그러면 안 되는 이유를 든다:

> *"a large boulder may cause rollover, while deformable sand may get the vehicle stuck"*

구현(§IV-A)에서는 상태벡터에 이어붙인다:

```
[0, 0, 0, roll, pitch, 0, e_elev, e_sem] ∈ R^22
 └────── 6 ──────┘  └─ 8 ─┘ └─ 8 ─┘
```

**③ ★ 출력에서는 지형 embedding을 예측하지 않는다.** §IV-A 마지막 문장:

> *"**We omit $e_{\text{elev}}$ and $e_{\text{sem}}$ in the prediction since they can be acquired from perception.**"*

Table I의 `Output dimension: 6` 이 그 결과다.

```
입력 R^22  =  pose 6 + e_elev 8 + e_sem 8
               ↓  f_θ
출력 R^6   =  [Δx, Δy, Δz, roll_{t+1}, pitch_{t+1}, Δψ]      ← 지형 없음
```

다음 스텝의 지형 embedding은 모델이 만드는 것이 아니라 **perception이 매번 새로 넣는다.**

> [!question] SWAE 학습에 대한 서술이 논문에 없다 ❓
> 언제·어떤 데이터로 학습했는지, kinodynamic 모델과 **따로인지 합동인지** 전부 서술이 없다.
> 앞 질문의 "SWAE 대체 실험이 없다"와 합치면, SWAE는 이 논문에서 근거가 가장 얇은 구성요소다.

### Q. §III-C의 $G_i$ 와 $g_i$ 는 각각 무엇인가?

**A.** 핵심 차이는 **미분(변화율) vs 적분(변화량)** 이다. §III-C의 식이 정의 전부다:

$$x_{t+1} - x_t = \sum_{i=1}^{k}\alpha_i \int_{t}^{t+\Delta t} g_i\big(x(\tau), u(\tau), e(\tau)\big)\,d\tau
= \sum_{i=1}^{k}\alpha_i\,G_i(x_t, u_t, e_t;\theta_i)$$

| | 무엇 | 출력 |
|---|---|---|
| $g_i$ | **신경망 그 자체.** 상태 **변화율**을 낸다 | 6차원 (Table I `Output dimension: 6`) |
| $G_i$ | $g_i$ 를 $\Delta t$ 동안 **적분한 것.** 상태 **변화량**을 낸다 | 6차원 |

> §III-C: *"**$g_i$ is the basis function state change rate to be integrated into $G_i$.**
> Each $G_i$ outputs the predicted state change."*

**θ는 $g_i$ 에 붙는다.** Algorithm 1 line 3:

> *"Initialize each basis function state change rate **$g_i$ as a neural network with parameters $\theta_i$**"*

학습되는 신경망은 $g_i$ 이고 $G_i$ 는 적분기를 통과시켜 얻는 **유도량**이다.
`G_i(· ; θ_i)` 에서 세미콜론 앞은 입력, 뒤는 파라미터.

**계산은 RK4.** §III-C: *"we approximate the integral $G_i$ using the **fourth-order Runge-Kutta (RK4)** numerical integrator."*

Algorithm 1:

```
16:  for i = 1, ..., k do
17:      G_i(·) ← RK4(g_i, x_pred_{t-1}, u_{t-1}, Δt)      ← k=24번 반복
18:  end for
19:  x_pred_t ← x_pred_{t-1} + Σ(i=1..k) α_i · G_i(·)      ← 그다음 결합
```

한 스텝마다 **기저함수 24개를 각각 따로 적분**하고 그다음 계수로 합친다.

**★ 왜 둘로 나누는가 — 최소제곱이 성립하려면 $G$ 수준이어야 한다.**

수학적으로는 적분이 선형이라 $\sum\alpha_i\int g_i = \int\sum\alpha_i g_i$ 로 같다.
그러나 **계산 순서가 달라지면 할 수 있는 일이 달라진다.**

```
(A) 적분 먼저, 결합 나중  ← 논문의 방식
    θ가 frozen이므로 G_1..G_24를 데이터만으로 미리 계산 가능
       ↓  y ≈ α_1·G_1 + ... + α_24·G_24
    선형회귀 → α를 closed form으로

(B) 결합 먼저, 적분 나중
    α가 적분 안에 들어가 미리 계산해둘 수 없음 → 매번 gradient
```

식 (1)이 그램 행렬인 이유가 이것이다 — 성분이 전부 $\langle G_i, G_j\rangle$, $\langle y, G_i\rangle$ 로
**$G$ 끼리의 내적**이다.

**관측된 상태 변화 $y$ 와 단위가 같은 것은 $G_i$ 이지 $g_i$ 가 아니다.**
$g_i$ 는 변화율이라 $y$ 와 직접 비교할 수 없다. 적분으로 단위를 맞춘 뒤에야 선형 문제가 되고,
그 결과가 §III-C의 $O(k^3)$ 이다.
