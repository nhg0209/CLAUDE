---
tags: [paper, SAC, max-entropy, off-policy, actor-critic]
제목: "Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor"
저자: Tuomas Haarnoja, Aurick Zhou, Pieter Abbeel, Sergey Levine
연도: 2018
학회: ICML 2018
arxiv: 1801.01290
계열: maximum entropy RL / off-policy actor-critic
선행논문: ["[[DDPG (Lillicrap 2015)]]", "[[TD3 (Fujimoto 2018)]]", "[[Soft Q-Learning (Haarnoja 2017)]]"]
이해도: 🟡
상태: 본문 완독
읽은날짜: 2026-09-14
---

# SAC (Haarnoja 2018)

> [!abstract] 한 줄 요약
> reward 만이 아니라 **reward + policy 의 entropy** 를 최대화하면,
> off-policy 의 sample efficiency 를 지키면서도 **seed 를 바꿔도 재현되는 안정성**을 얻는다.

> [!info] 좌표
> **계열**: maximum entropy RL × off-policy actor-critic
> **직전 논문**: [[DDPG (Lillicrap 2015)]] 의 off-policy actor-critic 구조와 [[TD3 (Fujimoto 2018)]] 의 twin Q + `min` 을 이어받음.
> [[Soft Q-Learning (Haarnoja 2017)]] 의 maximum entropy 목적함수를 actor-critic 으로 옮김.
> **이 논문이 바꾼 것**: DDPG 계열의 **deterministic actor 를 stochastic actor 로** 바꾸고,
> exploration noise 를 **손으로 주입하는 대신 목적함수에서 나오게** 했다.

> [!warning] ⚠️ 우리가 실제로 쓸 것은 이 논문이 아니다
> 이 노트는 **v1** (1801.01290) 이다. 실제 구현은 전부 **[[SAC v2 (Haarnoja 2018)]]** (1812.05905) 를 따른다.
> | | v1 (이 논문) | v2 (실제 표준) |
> |---|---|---|
> | value network | $V_\psi$ + target $V_{\bar\psi}$ **별도 존재** | **삭제**. target 을 $Q$ 에 직접 |
> | 온도 $\alpha$ | **고정**. 손으로 튜닝 (= reward scale) | **자동 조절**. $\bar{\mathcal{H}} = -\dim(\mathcal{A})$ |
> SB3, CleanRL, Spinning Up(구조상) 모두 v2 계열이다.

---

## 1. 기호 정리

공통 표기는 [[기호 사전]] 참고.

| 기호 | 의미 | 형태/차원 | 비고 |
|---|---|---|---|
| $\pi_\phi(a_t\mid s_t)$ | policy | $\phi$ = policy 파라미터 | |
| $Q_\theta(s_t,a_t)$ | soft Q-function | $\theta$ = Q 파라미터 | |
| $V_\psi(s_t)$ | soft value function | v1 에만 존재 | v2 에서 삭제 |
| $V_{\bar\psi}$ | target value network | EMA, $\tau=0.005$ | |
| $\alpha$ | temperature | 스칼라 | entropy 항의 상대 가중치 |
| $\mathcal{H}(\pi(\cdot\mid s_t))$ | entropy | 스칼라 | $-\mathbb{E}_{a\sim\pi}[\log\pi(a\mid s_t)]$ |
| $\rho_\pi$ | state-action marginal | | $\pi$ 로 굴렸을 때의 방문 분포 |
| $\mathcal{D}$ | replay buffer | | |
| $Z^{\pi_{\text{old}}}(s_t)$ | partition function | | **gradient 에서 사라진다** |
| $u$ | squash 전 Gaussian 샘플 | $\in\mathbb{R}^D$ | $a=\tanh(u)$ |
| $\xi$ | reparameterization noise | $\sim\mathcal{N}(0,I)$ | |

> [!warning] ⚠️ 표기 충돌 — 반드시 기억할 것
> **Spinning Up 과 이 논문은 $\theta,\phi$ 가 정반대다.**
> | | policy | Q |
> |---|---|---|
> | **SAC 논문** | $\phi$ | $\theta$ |
> | **Spinning Up** | $\theta$ | $\phi$ |
> 코드(CleanRL 등)는 대개 Spinning Up 쪽을 따른다. 논문 수식을 코드에 옮길 때 여기서 가장 많이 틀린다.

---

## 2. 문제 정의

### 무엇을 풀려고 하는가

model-free deep RL 의 **두 가지 병**을 동시에 잡는 것.

1. **sample complexity 가 너무 높다.** on-policy(TRPO/PPO/A3C)는 업데이트마다 새 샘플이 필요하다 — 매 gradient step 마다 데이터를 버린다.
2. **hyperparameter 에 brittle 하다.** off-policy(DDPG)는 sample efficient 하지만 **수렴이 극도로 불안정**하다.

> 저자의 프레이밍: *"the combination of off-policy learning and high-dimensional, nonlinear function approximation with neural networks presents a major challenge for stability and convergence"* — 즉 **deadly triad**.

### 기존 방법이 구체적으로 어디서 깨지는가

| 방법 | 깨지는 지점 |
|---|---|
| **PPO/TRPO** (on-policy) | 샘플을 한 번 쓰고 버린다. 고차원일수록 안정적 학습에 **큰 batch** 가 필요 → 더 느려진다 |
| **DDPG** (off-policy, deterministic) | actor 와 critic 의 상호작용이 불안정. **exploration noise 를 손으로 설계**해야 함(OU noise, scale 스케줄) → 하이퍼파라미터에 극도로 민감. §5.2 에서 seed 마다 결과가 천차만별임을 직접 보임 |
| **Soft Q-Learning** (Haarnoja 2017) | maximum entropy 는 맞지만 **actor 가 없다**. 연속 action 에서 $\exp(Q)$ 로부터 샘플링하려면 매 step SVGD 같은 근사 샘플러가 필요 → 느리고 복잡 |

> [!note] SAC 가 실제로 메우는 구멍
> "DDPG 의 sample efficiency" + "stochastic policy 의 안정성" 을 한 알고리즘에.
> **exploration 을 알고리즘 바깥의 트릭이 아니라 목적함수 안으로 넣은 것**이 본질이다.

---

## 3. 핵심 아이디어

수식 없이 한 문단:

> 보통의 RL 은 "보상을 최대로 하는 행동 하나"를 찾는다. SAC 는 **"보상도 높으면서 동시에 최대한 무작위한 policy"** 를 찾는다. 목적함수에 entropy 항을 더하면, policy 는 **성공하는 방법이 여러 개 있으면 그것들을 전부 유지**하게 된다. 그 결과 (1) 탐험이 공짜로 따라오고, (2) 한 가지 방법이 막혀도 다른 방법이 남아 있어 **모델 오차·환경 변화에 강해지며**, (3) 한 모드에 조기 붕괴하지 않아 **학습이 안정적**이다. exploration noise 를 손으로 넣을 필요가 사라진다.

$$
J(\pi)=\sum_{t=0}^{T}\mathbb{E}_{(s_t,a_t)\sim\rho_\pi}\Big[r(s_t,a_t)+\alpha\,\mathcal{H}\big(\pi(\cdot\mid s_t)\big)\Big]
$$

> [!tip] 우리 프로젝트(TM07 재현)와의 연결
> (2) 번 성질 — *"robust in the face of model and estimation errors"* (§1, Ziebart 2010 인용) — 이 **sim-to-real 의 이론적 근거**다.
> 우리는 시뮬의 동역학이 실차와 다르다는 것을 안다. deterministic policy 는 시뮬 동역학의 한 점에 과적합되지만,
> maximum entropy policy 는 **같은 보상을 주는 행동들의 분포 전체**를 유지하므로 동역학이 어긋나도 붕괴가 덜하다.
> → [[Domain Randomization]] 과 **곱셈적으로** 작동한다.

---

## 4. 수식 유도

### 4-1. §3.2 — $\alpha$ 는 reward 에 흡수된다 ⭐

목적함수에서 $\alpha$ 로 나누면:

$$
\frac{1}{\alpha}J(\pi)=\sum_t\mathbb{E}\Big[\tfrac{1}{\alpha}r(s_t,a_t)+\mathcal{H}(\pi)\Big]
$$

즉 **$\alpha$ 를 바꾸는 것과 reward 를 $1/\alpha$ 배 스케일하는 것은 완전히 같다.**

> [!warning] 여기서 나오는 실전 결론
> "reward scale" 과 "temperature" 는 **별개의 하이퍼파라미터가 아니다.** 같은 것의 두 얼굴이다.
> §5.2 의 reward scale ablation 이 이것의 실험적 증거다.
> → v1 에서 reward 함수를 건드릴 때마다 **탐험량이 같이 변한다.** 이게 v2 가 필요한 이유.

$\alpha\to 0$ 이면 기존의 maximum-return 목적함수로 환원된다 (논문에 명시).

### 4-2. §4.1 — soft policy iteration (tabular)

| | 내용 | 보장 |
|---|---|---|
| **soft policy evaluation** (Lemma 1) | soft Bellman backup 을 반복 적용 | $Q^k \to Q^\pi$ 로 수렴 |
| **soft policy improvement** (Lemma 2) | 식 (4) 로 policy 갱신 | $Q^{\pi_{\text{new}}}\ge Q^{\pi_{\text{old}}}$ (모든 $s,a$) |
| **soft policy iteration** (Theorem 1) | 둘을 번갈아 | optimal $\pi^*$ 로 수렴 |

soft Bellman backup:
$$
\mathcal{T}^\pi Q(s_t,a_t)\triangleq r(s_t,a_t)+\gamma\,\mathbb{E}_{s_{t+1}\sim p}\big[V(s_{t+1})\big],\quad
V(s_t)=\mathbb{E}_{a_t\sim\pi}\big[Q(s_t,a_t)-\alpha\log\pi(a_t\mid s_t)\big]
$$

**policy improvement — 식 (4)**:
$$
\pi_{\text{new}}=\arg\min_{\pi'\in\Pi} D_{\mathrm{KL}}\!\left(\pi'(\cdot\mid s_t)\ \Big\|\ \frac{\exp\!\big(\tfrac{1}{\alpha}Q^{\pi_{\text{old}}}(s_t,\cdot)\big)}{Z^{\pi_{\text{old}}}(s_t)}\right)
$$

읽는 법:
1. $\exp(\frac{1}{\alpha}Q)$ 는 **Q 를 확률분포로 바꾼 것** (Boltzmann/energy-based). $Q$ 가 큰 action 에 큰 확률.
2. $Z$ 는 정규화 상수 — **$a$ 에 의존하지 않는다.**
3. $\Pi$ 로 제한($\arg\min_{\pi'\in\Pi}$)하는 이유: 실제 policy 는 Gaussian 같은 **표현 가능한 족**에 갇혀 있다. 목표 분포에 정확히 도달 못 하니 **가장 가까운 것으로 투영**한다 → **I-projection**.

> [!note] $Z$ 가 사라지는 이유 (⭐ "convenient" 의 정체)
> $$D_{\mathrm{KL}}=\mathbb{E}_{a\sim\pi'}\Big[\log\pi'(a\mid s_t)-\tfrac{1}{\alpha}Q(s_t,a)+\log Z(s_t)\Big]$$
> $\log Z(s_t)$ 는 $\pi'$ 의 파라미터와 무관한 **상수** → $\nabla_\phi \log Z = 0$.
> **계산 불가능한 적분이 gradient 단계에서 통째로 증발한다.** KL 을 쓴 이유가 이것이다.

> [!question] 왜 tabular 에서만 증명하나
> *"Our derivation is based on a tabular setting, to enable theoretical analysis and convergence guarantees."*
> tabular = 상태·행동이 유한하고 $Q$ 를 **표 하나**로 완전히 표현. 그래야 $\mathcal{T}^\pi$ 가 contraction 임을 보이고 고정점 수렴을 말할 수 있다.
> **§4.2 에서 신경망으로 넘어가는 순간 이 보장은 전부 사라진다.** 남는 것은 §5.2 의 경험적 seed 안정성뿐이다.

### 4-3. §4.2 — function approximation

세 개의 네트워크를 **번갈아가며 SGD**. policy iteration 을 수렴할 때까지 돌리지 않고 **각각 1 step 씩**.

| 목적함수 | 대상 | 형태 |
|---|---|---|
| $J_V(\psi)$ | $V_\psi$ | $\mathbb{E}_{s_t\sim\mathcal{D}}\big[\tfrac12\big(V_\psi(s_t)-\mathbb{E}_{a_t\sim\pi_\phi}[Q_\theta(s_t,a_t)-\log\pi_\phi(a_t\mid s_t)]\big)^2\big]$ |
| $J_Q(\theta)$ | $Q_\theta$ | $\mathbb{E}_{(s_t,a_t)\sim\mathcal{D}}\big[\tfrac12(Q_\theta(s_t,a_t)-\hat Q(s_t,a_t))^2\big]$, $\ \hat Q = r+\gamma\,\mathbb{E}_{s_{t+1}}[V_{\bar\psi}(s_{t+1})]$ |
| $J_\pi(\phi)$ | $\pi_\phi$ | 식 (4) 의 KL. **reparameterization** 으로 미분 |

> [!warning] ⚠️ 기댓값이 어느 분포에 대한 것인지 — 여기가 핵심
> - $s_t, a_t, r, s_{t+1}$ : **replay buffer $\mathcal{D}$** 에서 (과거 policy 가 만든 것 — off-policy)
> - $a_t \sim \pi_\phi$ (식 5, 10 안쪽) : **현재 policy** 에서 새로 샘플 (buffer 의 $a$ 가 아님!)
>
> **이 분리가 SAC 가 off-policy 인 메커니즘 그 자체다.**
> $s'$ 는 환경이 만든 것이라 buffer 에서 가져와야 하고, $a'$ 는 **평가 대상 policy 가 지금 할 행동**이라 새로 뽑아야 한다.
> → 그래서 **replay buffer 에 `next_action` 을 저장하지 않는다.** 저장해봐야 낡은 policy 의 행동이라 쓸모가 없다. ([[질문 로그]] 참고)

**reparameterization trick**:
$$
\tilde a_\phi(s_t,\xi_t)=\tanh\big(\mu_\phi(s_t)+\sigma_\phi(s_t)\odot\xi_t\big),\qquad \xi_t\sim\mathcal{N}(0,I)
$$

- **무작위성을 파라미터 바깥으로 뺀다.** $\xi$ 는 $\phi$ 와 무관 → $\tilde a$ 가 $\phi$ 에 대해 **미분 가능**.
- 그냥 샘플링하면 score function estimator(REINFORCE)를 써야 하고 **분산이 크다**. reparameterization 은 **critic 을 통과하는 pathwise gradient** 를 준다 → 분산이 훨씬 작다.
- $\odot$ 는 elementwise — 즉 **대각 공분산 Gaussian**. action 차원 간 상관을 모델링하지 않는다.

**twin Q**: $Q_{\theta_1},Q_{\theta_2}$ 를 독립으로 학습하고 $V$ 와 $\pi$ 업데이트에 $\min(Q_{\theta_1},Q_{\theta_2})$ 를 쓴다 → [[TD3 (Fujimoto 2018)]] 의 overestimation bias 완화. 학습 속도도 빨라진다고 보고.

**target network**: $\bar\psi \leftarrow \tau\psi + (1-\tau)\bar\psi$ (EMA, polyak).

### 4-4. Appendix C — tanh log-prob 보정 ⭐ 구현 필수

$a=\tanh(u)$ 는 **부피를 바꾸는 변환**이므로 밀도를 그대로 쓰면 틀린다. change of variables:

$$
\pi(a\mid s)=\mu(u\mid s)\left|\det\!\left(\frac{da}{du}\right)\right|^{-1}\tag{20}
$$

Jacobian 이 **대각**($\frac{da_i}{du_i}=1-\tanh^2 u_i$, $i\ne j$ 는 0)이므로 $\log\det$ 가 합으로 분해된다:

$$
\log\pi(a\mid s)=\log\mu(u\mid s)-\sum_{i=1}^{D}\log\big(1-\tanh^2(u_i)\big)\tag{21}
$$

부호 점검: $1-\tanh^2 u\in(0,1]$ → $\log \le 0$ → **빼면 $\log\pi$ 가 커진다.** tanh 가 공간을 압축하니 밀도는 높아져야 맞다. ✅

> [!warning] 빠뜨렸을 때의 조용한 실패 사슬
> `log π` 과소평가 → entropy **과대**평가 → ($\alpha$ auto-tuning 시) $\alpha$ 가 줄어듦 → **탐험 소멸** → 나쁜 local minimum.
> 에러가 안 난다. 성능만 나쁘다. 가장 찾기 어려운 버그.

> [!note] 논문에 없지만 구현에 반드시 필요한 두 가지
> **① 수치 안정성.** $|u|$ 가 크면 $1-\tanh^2u\to 0$ → `log(0) = -inf`.
> ```python
> # 나쁨: torch.log(1 - a.pow(2) + 1e-6)
> # 좋음: 수학적으로 동일하고 안정적
> log_det = 2 * (math.log(2) - u - F.softplus(-2 * u))
> ```
> **② action scaling 항.** $(-1,1)$ 을 실제 범위로 매핑하면 $\sum_i\log(\text{scale}_i)$ 가 추가로 붙는다.
> gradient 에는 상수라 무해하지만 **$\log\pi$ 의 절대값을 바꾼다** → $\alpha$ auto-tuning 의 타깃 $\bar{\mathcal{H}}$ 비교에 **직접 영향**. v2 에서는 반드시 포함해야 한다.

> [!tip] 부수 효과 — 우리 $\kappa$ clip 과 관련
> 경계 근처 action($|a|\to1$)은 $\log\pi$ 가 **크다** → entropy 가 작다 → 목적함수가 싫어한다.
> **SAC 는 구조적으로 action saturation 을 회피한다.** 우리가 걱정하던 "policy 가 $\kappa$ clip 에 붙어버리는" 문제를 부분적으로 막아준다.

---

## 5. 알고리즘

```
Algorithm 1  Soft Actor-Critic (v1)
  초기화 ψ, ψ̄, θ₁, θ₂, φ
  for each iteration do
      for each environment step do
          a_t ~ π_φ(·|s_t)
          s_{t+1} ~ p(·|s_t, a_t)
          D ← D ∪ {(s_t, a_t, r(s_t,a_t), s_{t+1})}
      for each gradient step do
          ψ  ← ψ  − λ_V ∇̂_ψ J_V(ψ)              # value
          θ_i ← θ_i − λ_Q ∇̂_θi J_Q(θ_i)   i∈{1,2} # twin Q
          φ  ← φ  − λ_π ∇̂_φ J_π(φ)               # policy (reparam)
          ψ̄  ← τψ + (1−τ)ψ̄                       # target EMA
```

### 구현 관점

| 단계 | 텐서 shape | 주의점 |
|---|---|---|
| buffer 샘플 | `s (B,obs)`, `a (B,act)`, `r (B,1)`, `s' (B,obs)`, `d (B,1)` | **`a'` 는 저장하지 않는다** |
| policy forward | `μ (B,act)`, `log_σ (B,act)` | `log_σ` 를 `[-20, 2]` 로 clamp (논문 밖, 표준 관행) |
| reparam | `ξ (B,act)` → `u (B,act)` → `a = tanh(u)` | |
| `log π` | `(B,1)` | 식 (21) 의 합은 **action 차원에 대한 `sum(dim=-1)`** — `mean` 아님 |
| twin Q | `Q1 (B,1)`, `Q2 (B,1)` → `min` | policy loss 의 Q 는 **actor gradient 가 critic 으로 흐르지 않게** 하지 않는다 (흘러야 함) |
| Q target | `(B,1)` | `with torch.no_grad()` 필수 |

**`d` (done) 의 의미**: 종료 플래그. target 에 `(1 - d)` 를 곱해 terminal 이후의 부트스트랩을 끊는다.
$$\hat Q = r + \gamma(1-d)\,V_{\bar\psi}(s_{t+1})$$

> [!warning] ⚠️ `d` 의 고전적 함정 — 우리 환경에 직결
> **time limit 으로 인한 종료는 `d=1` 이 아니다.**
> 충돌·트랙 이탈(진짜 종료) → `d=1`. 에피소드 최대 스텝 도달(임의 절단) → **`d=0`** 으로 부트스트랩해야 한다.
> 그렇지 않으면 policy 가 "에피소드 끝 = 가치 0" 으로 배워서 **랩 끝에서 이상하게 감속**한다.
> Gymnasium 의 `terminated` / `truncated` 구분이 정확히 이것이다.

---

## 6. 실험 (§5)

**프로토콜**: seed 5개, 1000 env step 마다 evaluation rollout, 실선 = 평균, 음영 = **min/max**.
비교군: DDPG, PPO, TD3, SQL (+ Appendix E 의 Trust-PCL).

### 저자의 주장
sample efficiency 와 최종 성능이 **state of the art 를 넘는다**.

### 실제로 근거가 되는 결과
- **어려운 task 에서만 명확하다.** `Ant-v1`, `Humanoid-v1`, `Humanoid(rllab, 21-dim)` 에서 DDPG 는 **진전이 전혀 없다.**
- 쉬운 task 에서는 baseline 과 **사실상 동률**이다.
- ⭐ **Figure 2 (stochastic vs deterministic)** — 이 논문에서 가장 값어치 있는 그림.
  deterministic 변형(≈DDPG + twin Q)은 **seed 마다 결과가 천차만별**이고, stochastic 은 5개 seed 가 거의 겹친다.
  주장하는 것은 *평균 성능*이 아니라 **분산**이다.

### 근거가 약하거나 과장된 부분
- §4.1 의 수렴 보장은 **tabular 전용**이다. §4.2 의 실제 알고리즘에는 적용되지 않는데, 논문 구성은 마치 이어지는 것처럼 읽힌다.
- "*hyperparameter 에 robust 하다*"고 하면서 §5.2 는 **reward scale 에 극도로 민감**함을 보인다. 정확히는 *"튜닝할 하이퍼파라미터가 하나로 줄었다"* 가 맞는 주장이다.
- 저차원 연속 제어에서 TD3 대비 우위는 근거가 약하다.

### Ablation 에서 진짜 중요했던 변수

| 변수 | 결과 | 결론 |
|---|---|---|
| **stochastic vs deterministic** | seed 분산이 압도적 차이 | ⭐ SAC 를 쓰는 진짜 이유 |
| **evaluation 방식** | mean action 이 샘플링보다 좋음 | 배포는 $\tanh(\mu_\phi(s))$ |
| **reward scale** {1,3,10,30,100} | 작으면 uniform, 크면 조기 deterministic → local minima | ⭐ *"the only hyperparameter that requires tuning"* |
| **target smoothing $\tau$** {1e-4 … 1e-1} | 적정 범위가 **넓다** | 모든 task 에 `0.005` 하나. **튜닝 대상 아님** |

> [!note] reward scale 과 action 차원의 관계 (Appendix D)
> | env | action dim | reward scale |
> |---|---|---|
> | Hopper / Walker2d / HalfCheetah / Ant | 3 / 6 / 6 / 8 | **5** |
> | Humanoid-v1 | 17 | **20** |
> | Humanoid (rllab) | 21 | 10 |
>
> entropy 는 차원에 대한 **합**이라 $D$ 에 비례해 커진다 → $\alpha$ 를 줄여야 = reward scale 을 키워야 한다.
> ⭐ **이 관찰이 [[SAC v2 (Haarnoja 2018)]] 의 $\bar{\mathcal{H}}=-\dim(\mathcal{A})$ 를 그대로 예고한다.**

### Appendix D — 기본 하이퍼파라미터

```
optimizer              Adam
learning rate          3e-4
discount γ             0.99
replay buffer size     1e6
hidden layers          2 × 256
batch size             256
nonlinearity           ReLU
target smoothing τ     0.005
target update interval 1
gradient steps         1
```

---

## 7. 한계와 후속 연구

| 한계 | 해결한 논문 |
|---|---|
| $\alpha$(=reward scale)를 손으로 튜닝해야 함 | ⭐ [[SAC v2 (Haarnoja 2018)]] — constrained optimization 으로 자동화 |
| $V$ 네트워크가 따로 필요 (파라미터 3벌) | [[SAC v2 (Haarnoja 2018)]] — $V$ 삭제, target 을 $Q$ 에 |
| 병렬화 미지원 (Spinning Up 구현 기준) | 분산 구현체들 |
| **fully observable MDP 가정** | [[Asymmetric Actor-Critic (Pinto 2017)]] — critic 에 privileged obs |
| 실물 로봇 적용 | [[SAC v2 (Haarnoja 2018)]] §Minitaur, [[TM07 리포트 (2025)]] |

> [!tip] 우리 스택에서의 위치
> ```mermaid
> graph LR
>   DDPG[DDPG 2015] --> TD3[TD3 2018]
>   TD3 -->|twin Q + min| SAC[SAC v1 2018]
>   SQL[Soft Q-Learning 2017] -->|max-entropy| SAC
>   SAC -->|alpha auto-tuning| SACv2[SAC v2 2018b]
>   SACv2 --> TM07[TM07 Asymmetric SAC]
>   AAC[Asymmetric AC 2017] -->|privileged critic| TM07
>   TM07 --> OURS[본 연구: path-conditioned]
> ```

---

## ❓ 질문 로그

전체 목록은 [[질문 로그]].

### Q. §4.1 의 "tabular setting" 이 무슨 뜻이고, 왜 거기서만 유도하나?
**A.** 상태·행동이 유한해서 $Q$ 를 **표 하나**로 정확히 표현할 수 있는 설정. 그래야 soft Bellman operator 가 contraction 임을 보이고 고정점 수렴을 증명할 수 있다.
**§4.2 에서 신경망(function approximation)으로 가는 순간 이 증명은 무효가 된다.** 논문은 그 공백을 §5.2 의 seed 안정성 실험으로 메운다. → §4.1 은 "왜 이 업데이트 규칙이 말이 되는가"의 정당화이지, 실제 알고리즘의 보장이 아니다.

### Q. 식 (4) 의 $\exp(Q)/Z$ 와 KL 이 이해가 안 된다.
**A.** 세 조각으로 나눠 읽는다.
1. $\exp(\frac1\alpha Q(s,\cdot))$ — Q 를 **확률분포 모양**으로 바꾼 것. 좋은 action 에 큰 확률. $\alpha$ 가 작으면 뾰족(=greedy), 크면 평평(=탐험).
2. $Z(s)$ — 정규화 상수. **$a$ 와 무관**.
3. $\arg\min_{\pi'\in\Pi}D_{\mathrm{KL}}$ — 우리 policy 는 Gaussian 족 $\Pi$ 안에 갇혀 있어 목표 분포에 도달 못 한다. **가장 가까운 것으로 투영**(I-projection).

⭐ 핵심: KL 을 펼치면 $\log Z(s_t)$ 가 **$\phi$ 와 무관한 상수**라 $\nabla_\phi$ 에서 사라진다. **계산 불가능한 적분이 공짜로 증발**한다. "KL 이 convenient 하다"는 말의 정체가 이것이다.

### Q. RHS 의 next state 는 buffer 에서, next action 은 현재 policy 에서 온다는 게 무슨 뜻인가?
**A.** $s'$ 는 **환경이 만든 것**이라 재현이 불가능 → buffer 에서 꺼내야 한다.
$a'$ 는 **지금 평가하려는 policy 가 할 행동** → 지금 뽑아야 한다. buffer 의 $a'$ 는 낡은 policy 의 것이라 틀린 값이다.
**이 분리가 off-policy 를 가능하게 하는 메커니즘 그 자체다.** on-policy(SARSA)는 $a'$ 도 데이터에서 가져오기 때문에 낡은 데이터를 못 쓴다.

### Q. 여러 노면 마찰계수를 학습할 때, buffer 의 next state 만으로는 부족하니 next action 도 저장해야 하지 않나?
**A.** ❌ 아니다. 문제의식은 옳지만 처방이 틀렸다.
- $(s,a,r,s')$ 에는 **이미 동역학이 들어 있다.** "이 $\delta$ 를 줬더니 이만큼 돌았다" = $\mu$ 의 증거. $a'$ 는 **policy 가 만든 것**이라 환경 정보가 0이다.
- 진짜 부족한 것은 **관측 가능성**이다. 단일 transition 으로는 $\mu$ 를 구별 못 한다 → **history/frame stacking** (`N=10~20`) 이 답이다.
- ⚠️ 급소: `obs["linear_vels_y"]` 가 **0 하드코딩** → slip 을 못 본다. `env.sim.agents[i].state[6]`($\beta$) 를 직접 읽어야 한다.
- ★ 여기서 설계 결정: **privileged obs 에 $\mu, C_{Sf}, C_{Sr}, m, h$ 추가.** TM07 의 24-dim 은 전부 기하 정보라 동역학 파라미터가 없다 → 우리 차별점. ([[프로젝트 스택]] §10-1)

### Q. sim 에서 critic 에 넘긴 $\mu$ 와 실측 $\mu$ 의 갭은 어떻게 보완하나?
**A.** **보완할 필요가 없다. critic 은 배포되지 않는다.** actor 는 $\mu$ 를 입력으로 받지 않고 이력에서 추론한다.
더 근본적으로 — critic 의 $\mu$ 는 물리량이 아니라 **"에피소드를 구별하는 라벨"** 이다. 구별만 되면 기능이 같으므로 정규화해서 넘긴다.
진짜 갭은 (A) randomization 범위가 실제를 안 덮는 것, (B) 실제 마찰이 단일 스칼라가 아닌 것, (C) **선형 타이어 모델**, (D) actor 의 추론 구조가 시뮬 전용인 것. 실측 $\mu$ 가 정말 중요한 유일한 곳은 `k_fric = μg/v²` clip 이다.
⭐ 원칙: **privileged 정보는 "actor 가 원리적으로 추론 가능한 것"으로 제한한다.**

### Q. reparameterization trick 을 더 자세히.
**A.** $\tilde a_\phi(s,\xi)=\tanh(\mu_\phi(s)+\sigma_\phi(s)\odot\xi)$, $\xi\sim\mathcal{N}(0,I)$.
무작위성을 $\xi$ 로 **바깥으로 빼내서** $\tilde a$ 를 $\phi$ 에 대해 미분 가능하게 만든다.
- 안 하면: score function estimator($\nabla\log\pi\cdot Q$) → **분산 폭발**.
- 하면: critic 을 통과하는 **pathwise gradient** — "action 을 어느 방향으로 옮기면 $Q$ 가 오르는지"를 critic 이 직접 알려준다. DDPG 의 gradient 구조와 같되 **stochastic policy 에서도 작동**한다.
- $\odot$ 는 elementwise → **대각 공분산**. action 차원 간 상관은 모델링하지 않는다.

### Q. pseudocode 의 $r$ 은 어떻게 계산되고 $d$ 는 무엇인가?
**A.** $r$ 은 **환경이 주는 것**이지 알고리즘이 계산하는 게 아니다. (⚠️ f1tenth_gym 은 `reward = self.timestep` 이 전부다 — **우리가 직접 설계해야 한다.**)
$d$ 는 종료 플래그로 $\hat Q=r+\gamma(1-d)V_{\bar\psi}(s')$ 에서 부트스트랩을 끊는다.
⚠️ **time limit 절단은 `d=0`** 으로 둬야 한다. 그렇지 않으면 랩 끝에서 이상하게 감속하는 policy 가 나온다.

---

## 🔗 연결

- **선행**: [[DDPG (Lillicrap 2015)]] · [[TD3 (Fujimoto 2018)]] · [[Soft Q-Learning (Haarnoja 2017)]] · [[PPO (Schulman 2017)]]
- **후속**: ⭐ [[SAC v2 (Haarnoja 2018)]] · [[TM07 리포트 (2025)]]
- **개념**: [[Maximum Entropy RL]] · [[Reparameterization Trick]] · [[Replay Buffer]] · [[Target Network]] · [[Entropy]] · [[Off-policy]] · [[Domain Randomization]] · [[Residual Policy Learning]]
- **대조군**: [[MPCC]] · [[Pure Pursuit]]
- **지도**: [[RL 지도]] · [[프로젝트 스택]]
