# RL 기반 E2E 자율주행 레이싱 — 학습 로드맵 & 자료 정리

> 목표: **RL 사전지식 0** 상태에서 출발해, TM07 리포트
> *"Reinforcement Learning End-to-End Autonomous Racing Architecture with Asymmetric SAC and Sim-to-Real Pipeline"*
> 수준의 스택을 **직접 재현하고 개선**할 수 있는 지점까지 최단 경로로 도달한다.
>
> 용어는 **원문(영문) 그대로** 쓰고, 설명만 한국어로 한다. (`policy`를 "정책"으로 번역하면
> 논문·코드·문서를 볼 때 오히려 매칭이 안 되기 때문)

---

## 0. 이 문서 사용법

| 표기 | 뜻 |
|---|---|
| ★ | **필수**. 건너뛰면 뒤 단계가 막힘 |
| ○ | 권장. 시간 되면 |
| △ | 참고용. 필요할 때 찾아보기 |

- **Stage 1~3** 은 "이해" 단계 (약 2~3주, 하루 3~4시간 기준)
- **Stage 4~7** 은 "우리 프로젝트에 바로 꽂는" 단계 — 여기서부터는 코드를 쓰면서 읽는다
- 각 Stage 끝의 **통과 기준(Exit Criteria)** 을 스스로 말로 설명할 수 있으면 다음으로 넘어간다
- Stage 1~2 는 자료를 "다 보는" 게 목적이 아니다. **하나만 골라 끝까지** 보고 나머지는 막힐 때 교차 참조용

---

## 1. 먼저: TM07 리포트 해부 — 어떤 RL 개념이 어디에 쓰였나

리포트를 다시 읽기 전에, 각 문장이 RL의 **어느 주제**에 해당하는지 지도를 먼저 갖는 게 훨씬 빠르다.

| TM07 리포트 문장 / 구성요소 | 대응 RL 개념 | 학습 위치 |
|---|---|---|
| "Model-Free" | model-based vs **model-free** RL | Stage 1 |
| "Soft Actor-Critic (SAC)" | maximum entropy RL, off-policy actor-critic | Stage 2·3 |
| Actor `π`: LiDAR 270 + `s_ego = [v_x, δ_{t-1}, I_overtake]`, history `N=4` | **POMDP**, frame stacking, observation space 설계 | Stage 2·4 |
| Critic `Q`: 24-dim **Privileged Observation Space** (track coord, `e_lat`, `e_psi`, curvature, wall distance, opponent 상대좌표) | **Asymmetric Actor-Critic** | Stage 4 |
| "Two-Phase Automatic Curriculum" (EMA lap rate > 60%) | **Curriculum Learning**, automatic curriculum | Stage 5 |
| `R = r_progress + r_safety + r_TTC + r_overtake` | **Reward shaping**, potential-based shaping | Stage 5 |
| `B_steer = -|δ_t - δ_{t-1}|·(λ_H + v_x/V_max·λ_H_speed)` | action smoothness penalty (sim2real 필수 장치) | Stage 5·6 |
| TTC = Gap / (v_ego - v_opp), `1/TTC` penalty | safety reward, predictive braking | Stage 5 |
| Opponent = Pure Pursuit, lookahead 랜덤화 (20/20/60) | **opponent randomization** (= domain randomization의 일종), non-stationarity 회피 | Stage 5·6 |
| Tier 1 f1tenth_gym → Tier 2 Isaac Sim → Tier 3 실차 | **Sim-to-Real**, reality gap | Stage 6 |
| Action Low-Pass Filter `a_t = (1-α)a_{t-1} + α·a_model`, α=1.0(sim) → 0.4~0.6(real) | actuator dynamics 보정, jerk 억제 | Stage 6 |

### 1-1. 리포트에 **없는 것** = 우리가 직접 정해야 하는 것

재현할 때 반드시 막히는 지점들이다. 미리 알고 시작하자.

- **action space 정의 없음**: `[steering δ, velocity v]` 인지 `[δ, throttle]` 인지, 절대값인지 증분(delta)인지 미명시
- **network 구조/크기 없음**: hidden dim, layer 수, LiDAR 270-dim을 1D-CNN으로 처리했는지 MLP인지
- **reward 각 항의 weight 없음**: `λ_H`, `λ_H_speed` 값 미공개 → 우리가 튜닝해야 함
- **α (entropy temperature) 자동 조정 여부 미명시** → 후속 논문(§4-2) 방식(auto-tuning)을 쓰는 게 정석
- **Phase 2 gap "30–50 → 5–50"** 은 오타로 보임 (progressively *closing* 이라면 `5–15` 정도가 자연스러움) → 우리가 커리큘럼 스케줄을 직접 설계
- **차량 스케일 불일치 주의**: 하드웨어는 **1/8 scale Serpent SRX8 R** 인데, f1tenth_gym 기본 차량 모델은 **1/10 F1TENTH** 파라미터다.
  → wheelbase, mass, `I_z`, tire 계수(`C_Sf`, `C_Sr`), `v_max`, steering limit, ESC duty↔속도 매핑을
  **직접 재측정(system identification)** 해서 gym 파라미터를 교체해야 sim2real이 성립한다. 이게 초반 최대 리스크.

---

## 2. Stage 1 — RL 기초 (1~1.5주) ★

### 반드시 손에 익혀야 할 개념 체크리스트

- `MDP (S, A, P, R, γ)` / episode / trajectory / return `G_t`
- `policy π(a|s)` — deterministic vs **stochastic**
- `value function V^π(s)`, `action-value Q^π(s,a)`, `advantage A(s,a)`
- **Bellman equation** / Bellman optimality equation
- Dynamic Programming: policy evaluation, policy improvement, **policy iteration**, value iteration
  → SAC 논문 §4.1 "Soft Policy Iteration"이 바로 이것의 entropy 버전이라 **이걸 모르면 §4를 못 읽는다**
- Monte Carlo vs **TD learning** / TD error `δ = r + γV(s') - V(s)`
- SARSA(on-policy) vs **Q-learning(off-policy)** — off-policy가 왜 replay buffer를 쓸 수 있는지
- exploration vs exploitation, ε-greedy
- discount factor `γ`가 episode 길이와 어떻게 연결되는지 (effective horizon ≈ `1/(1-γ)`)

### 자료 (한국어 우선)

| 자료 | 형태 | 비고 |
|---|---|---|
| ★ [팡요랩 Pang-Yo Lab (YouTube)](https://www.youtube.com/channel/UCwkGvF7xKz2E0Lv-fZ9wv2g) | 강의 영상 | David Silver UCL 강의를 한국어로 풀어줌. **가장 추천하는 1순위** |
| ★ [팡요랩 강화학습 기초 이론 강의 (인프런, 무료)](https://www.inflearn.com/course/%EA%B0%95%ED%99%94%ED%95%99%EC%8A%B5) | 무료 강의 | 위와 동일 내용, 인프런 정리본 |
| ★ [바닥부터 배우는 강화 학습 (노승은, 영진닷컴)](https://product.kyobobook.co.kr/detail/S000000555527) | 책 | 팡요랩 운영자가 쓴 입문서. 영상 + 책 조합이 최고 효율 |
| ○ [with-rl.com — 「바닥부터 배우는 강화 학습」 정리 블로그](https://with-rl.com/%EB%B0%94%EB%8B%A5%EB%B6%80%ED%84%B0-%EB%B0%B0%EC%9A%B0%EB%8A%94-%EA%B0%95%ED%99%94-%ED%95%99%EC%8A%B5-01-%EA%B0%95%ED%99%94-%ED%95%99%EC%8A%B5%EC%9D%B4%EB%9E%80/) | 블로그 | 챕터별 요약, 복습용 |
| ○ [혁펜하임 — "트이는" 강화 학습 (재생목록)](https://www.youtube.com/playlist?list=PL_iJu012NOxehE8fdF9me4TLfbdv3ZW8g) | 강의 영상 | 수식을 직관적으로. 팡요랩이 안 맞으면 이쪽 |
| ○ [모두를 위한 딥러닝 — Deep RL (김성훈, 인프런 무료)](https://www.inflearn.com/course/reinforcement-learning) | 무료 강의 | 코드부터 보고 싶다면 |
| △ [단단한 강화학습 (Sutton & Barto 번역, 제이펍)](https://product.kyobobook.co.kr/detail/S000001942492) | 책 | **교과서**. 처음부터 완독하지 말고 사전처럼 |
| △ [Sutton & Barto, *Reinforcement Learning: An Introduction* 2nd ed. — 원서 무료 PDF](http://incompleteideas.net/book/the-book-2nd.html) | 책(무료) | 위 번역서의 원문 |
| △ [David Silver, UCL RL Course (슬라이드+영상)](https://www.davidsilver.uk/teaching/) | 강의 | 팡요랩의 원본 |
| △ [RLKorea — "우리는 어떻게 강화학습을 공부했는가"](https://github.com/reinforcement-learning-kr/how_to_study_rl/wiki/%EC%9A%B0%EB%A6%AC%EB%8A%94-%EC%96%B4%EB%96%BB%EA%B2%8C-%EA%B0%95%ED%99%94%ED%95%99%EC%8A%B5%EC%9D%84-%EA%B3%B5%EB%B6%80%ED%96%88%EB%8A%94%EA%B0%80) | 한국어 커뮤니티 위키 | 학습 순서 참고 |

### 실습 ★
```bash
pip install gymnasium
```
- `CartPole-v1` 에 tabular Q-learning (state discretize) 직접 구현 — 100줄이면 됨
- `FrozenLake-v1` 로 value iteration / policy iteration 직접 구현

### 통과 기준
- "Q-learning이 왜 **off-policy** 이고, 그래서 왜 **replay buffer**를 쓸 수 있는가"를 그림 없이 설명 가능
- "우리 레이싱 문제의 `S`, `A`, `R`, `γ`, episode termination 조건"을 한 문단으로 쓸 수 있음

---

## 3. Stage 2 — Deep RL & 연속 제어 (1~1.5주) ★

우리 문제는 action이 **연속값** (`steering angle δ`, `velocity v`) 이다.
→ DQN 계열(discrete action)은 쓸 수 없고, **off-policy actor-critic** 계열이 필요하다.
→ 이 계보를 이해하는 게 Stage 2의 전부다.

### 계보 (이 순서로 읽는다)

```
DQN ──(replay buffer, target network)
 │
 └─ REINFORCE / Policy Gradient ──(baseline)── Actor-Critic (A2C)
                                                  │
                                    ┌─────────────┴──────────────┐
                              on-policy                    off-policy
                              TRPO → PPO              DDPG → TD3 → ★SAC
```

| 알고리즘 | 논문 | 왜 봐야 하나 |
|---|---|---|
| DQN | [arXiv:1312.5602](https://arxiv.org/abs/1312.5602) | replay buffer / target network 개념의 원조 |
| DDPG | [arXiv:1509.02971](https://arxiv.org/abs/1509.02971) | 연속 action off-policy의 시작. 불안정한 게 문제 |
| PPO | [arXiv:1707.06347](https://arxiv.org/abs/1707.06347) | 로보틱스 표준 baseline. Isaac Lab 기본값이라 알아둬야 함 |
| TD3 | [arXiv:1802.09477](https://arxiv.org/abs/1802.09477) | **twin Q (clipped double Q)** — SAC가 그대로 가져감 |
| ★ SAC | [arXiv:1801.01290](https://arxiv.org/abs/1801.01290) (첨부 논문) | 우리 알고리즘 |
| ★ SAC v2 | [arXiv:1812.05905](https://arxiv.org/abs/1812.05905) | **automatic entropy tuning**. 실제 구현체는 전부 이걸 따름 |

### 자료

| 자료 | 비고 |
|---|---|
| ★ [OpenAI Spinning Up in Deep RL](https://spinningup.openai.com/en/latest/) | 알고리즘별 **개념 + 수식 + pseudocode + 핵심 논문 리스트**. [SAC 페이지](https://spinningup.openai.com/en/latest/algorithms/sac.html) 는 논문보다 먼저 읽어도 좋다 |
| ★ [CleanRL](https://github.com/vwxyzjn/cleanrl) / [docs](https://docs.cleanrl.dev) | **알고리즘 1개 = 파일 1개**. `sac_continuous_action.py` 300줄이 SAC 전부. 우리가 fork할 베이스 |
| ★ [Stable-Baselines3](https://stable-baselines3.readthedocs.io/) | 검증된 구현. baseline 빠르게 돌릴 때 |
| ○ [RL Baselines3 Zoo](https://github.com/DLR-RM/rl-baselines3-zoo) | 하이퍼파라미터 튜닝된 설정 모음 — 값 잡을 때 참고 |
| ○ [파이썬과 케라스로 배우는 강화학습 (위키북스)](https://wikibook.co.kr/reinforcement-learning/) / [예제 코드 v2](https://github.com/rlcode/reinforcement-learning-kr-v2) | 한국어 코드 입문서 |
| △ [Lilian Weng — Policy Gradient Algorithms](https://lilianweng.github.io/posts/2018-04-08-policy-gradient/) | 계보 한 장 정리(영문). 복습용으로 최고 |

### 실습 ★
```bash
pip install stable-baselines3 gymnasium[classic-control]
# Pendulum-v1 (연속 action) 에 SAC 20분 학습 → 성공하는지 확인
```
그 다음 **CleanRL `sac_continuous_action.py` 를 한 줄씩 읽으면서 주석 달기.**
이 파일을 이해하면 Stage 4(Asymmetric 개조)가 그냥 편집 작업이 된다.

### 통과 기준
- PPO(on-policy)와 SAC(off-policy)의 sample efficiency 차이를 설명 가능
- `replay buffer`, `target network`, `soft update τ` 가 각각 무엇을 안정화하는지 설명 가능

---

## 4. Stage 3 — SAC 논문 정독 (3~4일) ★

첨부하신 **arXiv:1801.01290v2** 를 순서대로 읽는 가이드다.

### 4-1. 읽는 순서와 각 절의 핵심

| 절 | 핵심 | 놓치면 안 되는 것 |
|---|---|---|
| §3.2 Maximum Entropy RL | `J(π) = Σ_t E[r(s_t,a_t) + α·H(π(·|s_t))]` | **왜 entropy를 더하나** → (1) exploration 개선 (2) multi-modal 행동 유지 (3) model error에 robust. 레이싱에서 "코너에서 인/아웃 두 라인 다 살려두는" 효과 |
| §4.1 Soft Policy Iteration | soft policy evaluation ↔ soft policy improvement (KL projection) | Stage 1의 policy iteration의 entropy 버전. **여기가 이해되면 SAC는 끝** |
| §4.2 Soft Actor-Critic | `V_ψ`, `Q_θ` (twin), `π_φ` = squashed Gaussian, target `V̄_ψ` (EMA `τ`) | **reparameterization trick**: `a = tanh(μ_φ(s) + σ_φ(s)·ε)`, `ε~N(0,I)` → gradient가 policy를 통과 |
| Appendix C | tanh squashing 시 log-likelihood 보정항 `log π = log N(u) - Σ log(1 - tanh²(u_i))` | **직접 구현 시 가장 많이 틀리는 곳**. 이거 빠지면 entropy가 틀리고 학습이 안 됨 |
| §5 Experiments | reward scale 민감도, seed 안정성 | reward scale이 사실상 `α`의 역수 역할 → 우리 reward 설계와 직결 |

### 4-2. 반드시 같이 볼 후속 논문 ★

[**arXiv:1812.05905** — *Soft Actor-Critic Algorithms and Applications*](https://arxiv.org/abs/1812.05905)

- 첨부 논문(v2)에는 있는 **별도 value network `V_ψ` 가 제거**됨 → `Q` + target `Q` 만 사용
- **automatic entropy temperature tuning** 도입: `α` 를 고정하지 않고,
  제약 `E[-log π(a|s)] ≥ H̄` (보통 `H̄ = -dim(A)`) 를 만족하도록 dual gradient로 자동 조정
- **SB3 / CleanRL / 대부분의 racing RL 구현은 이 버전이다.** 첨부 논문만 읽고 코드를 보면 구조가 안 맞아 혼란스러움

### 4-3. 실무 하이퍼파라미터 출발점 (racing 기준)

| 항목 | 값 | 메모 |
|---|---|---|
| `learning rate` | `3e-4` | actor/critic/α 동일하게 시작 |
| `γ` (discount) | `0.99` | 제어주기 40Hz면 effective horizon ≈ 2.5s. 코너 예측엔 `0.99~0.995` |
| `τ` (soft update) | `0.005` | |
| `batch size` | `256` (~`512`) | |
| `replay buffer` | `1e6` | obs가 270×4면 메모리 확인 필요 → `float16` 저장 고려 |
| `learning_starts` | `10k` step | 그 전엔 random action |
| `target entropy H̄` | `-dim(A)` = `-2` | auto-tuning 쓸 때 |
| `train_freq / gradient_steps` | `1 / 1` | 실차 대비 wall-clock 우선이면 `64/64` (batched) |
| action space | **`[-1, 1]` 로 정규화 후** `δ`, `v` 로 affine 매핑 | tanh 출력과 맞추기 위해 필수 |
| observation | **running mean/std normalize, 통계는 학습 후 고정 저장** | 실차 배포 시 이 통계 파일이 없으면 policy가 완전히 다르게 동작 |

---

## 5. Stage 4 — Asymmetric Actor-Critic & POMDP (3~5일) ★

TM07의 가장 중요한 설계 결정이다.

### 5-1. 왜 asymmetric인가

- **실차**에는 LiDAR scan + ego state 밖에 없다 → 이건 **POMDP** (partially observable)
- **시뮬레이터**에는 track 절대좌표, `e_lat`, `e_psi`, lookahead curvature, 정확한 wall distance,
  opponent 상대좌표가 **공짜로** 있다 → 이게 **privileged observation** (24-dim)
- **Critic `Q`만 privileged obs를 받는다** → value 추정이 정확해지고 policy gradient의 분산이 줄어 학습이 빨라짐
- **Actor `π`는 배포 가능한 obs만 받는다** → 학습 끝나면 critic은 버리고 actor만 차에 올림
- 핵심: **critic은 배포되지 않으므로, 시뮬에서만 얻을 수 있는 정보를 써도 된다**

### 5-2. 자료

| 자료 | 비고 |
|---|---|
| ★ [Pinto et al., *Asymmetric Actor Critic for Image-Based Robot Learning* (arXiv:1710.06542)](https://arxiv.org/abs/1710.06542) | 원조 논문. 짧고 읽기 쉬움 |
| ○ [*Informed Asymmetric Actor-Critic* (arXiv:2509.26000)](https://arxiv.org/abs/2509.26000) | full-state를 넘어선 privileged signal 설계 최신 논의 |
| ○ [*AACC: Asymmetric Actor-Critic in Contextual RL* (arXiv:2208.02376)](https://arxiv.org/abs/2208.02376) | 이론적 분석 |
| △ teacher-student / policy distillation 대안: [RMA (arXiv:2107.04034)](https://arxiv.org/abs/2107.04034) | privileged teacher → student 증류 방식. asymmetric AC의 경쟁 접근. locomotion에서 표준 |

### 5-3. 구현 노트 (중요)

- **SB3의 기본 `SAC` 는 asymmetric obs를 지원하지 않는다.** actor/critic이 같은 obs를 본다.
- 현실적인 선택지:
  1. ★ **CleanRL `sac_continuous_action.py` 를 fork** → `Actor`는 `obs["policy"]`, `SoftQNetwork`는 `obs["critic"]` 을 받도록 5~10줄 수정. **가장 깔끔**
  2. SB3에서 `Dict` observation space + 커스텀 `features_extractor` 로 actor/critic이 서로 다른 key만 보게 masking (돌아가지만 지저분)
  3. `skrl` / `rsl_rl` — asymmetric을 1급으로 지원 (Isaac Lab 연동 시 유리)
- **replay buffer에는 두 obs를 모두 저장**해야 한다 (`policy_obs`, `critic_obs` 둘 다)

### 5-4. History stacking (`N=4`)

- 단일 LiDAR scan만으로는 **속도/각속도/opponent의 접근율**을 알 수 없다 (POMDP)
- 가장 단순하고 sim2real에 강한 해법: **최근 `N=4` 프레임 stacking** (TM07이 쓴 방법)
- 대안인 **LSTM/GRU (recurrent policy)** 는 표현력은 좋지만 실차 배포 시 hidden state 관리·주기 지터에 취약 → **처음엔 stacking 권장**
- 실차에서도 **정확히 같은 stacking 주기**로 넣어야 한다. 시뮬 40Hz면 실차도 40Hz 고정 (드롭 시 마지막 값 hold + 로깅)

---

## 6. Stage 5 — Reward Design & Curriculum (1~2주, 여기가 진짜 승부처) ★

**"알고리즘은 SAC로 고정, 성능 차이는 99% reward와 curriculum에서 난다."**

### 6-1. Reward shaping 이론

| 자료 | 비고 |
|---|---|
| ★ [Ng, Harada, Russell — *Policy Invariance Under Reward Transformations* (1999)](https://people.eecs.berkeley.edu/~pabbeel/cs287-fa09/readings/NgHaradaRussell-shaping-ICML1999.pdf) | **potential-based reward shaping**. "shaping을 넣어도 optimal policy가 안 바뀌는 조건". progress reward가 왜 안전한지의 근거 |
| ○ [Curriculum Learning for RL: A Framework and Survey (arXiv:2003.04960)](https://arxiv.org/abs/2003.04960) | curriculum 설계 전반 |
| ○ [OpenAI — Automatic Domain Randomization / Rubik's Cube (arXiv:1910.07113)](https://arxiv.org/abs/1910.07113) | **ADR** — 성능 지표로 난이도를 자동 조절. TM07의 "EMA lap rate > 60%" 게이트와 같은 아이디어 |

### 6-2. TM07 reward 재현 설계표

| 항목 | 정의 | 구현 힌트 (unicorn stack 활용) |
|---|---|---|
| `r_progress` | Frenet **`s` 좌표의 증분** (한 step에 트랙을 따라 전진한 거리) | `race_utils/f110_utils/libs/frenet_conversion` 그대로 사용 ★ |
| `r_safety` | wall 근접 penalty + collision 시 큰 음수 + episode termination | `race_utils/raycaster` (range_libc) 로 wall distance ★ |
| `r_TTC` | `TTC = Gap/(v_ego - v_opp)`, `TTC < 5.0s` 일 때 `-k/TTC` | `v_ego - v_opp > 0` 일 때만 유효. 분모 0 방어 필수 |
| `r_overtake` | 추월 성공 시 1회성 bonus | opponent 대비 `s` 순서가 뒤집히는 이벤트로 감지 |
| `B_steer` | `-|δ_t - δ_{t-1}|·(λ_H + (v_x/V_max)·λ_H_speed)` | 고속 직선에서 weaving 제거. **저속 코너에선 민첩성 유지** — 이 speed scaling이 핵심 |

### 6-3. 자주 터지는 실패 모드 (미리 알고 가면 며칠 아낌)

- **reward hacking**: 제자리 회전 / 후진 반복 / 벽 긁으며 progress 쌓기
  → `r_progress` 를 **전진 성분만** (음수 clip), 역주행 termination, 최소 속도 조건 추가
- **sparse reward**: lap 완주에만 보상 → 절대 학습 안 됨. dense progress reward가 필수
- **termination vs truncation 구분 (Gymnasium)**: 타임아웃(truncation)에서 `V(s')` 를 **bootstrap 해야** 하고,
  충돌(termination)에서는 **하면 안 된다**. 이걸 뒤집으면 조용히 성능이 반토막 난다. ★ 가장 흔한 버그
- **reward scale**: SAC는 reward scale에 민감 (`α`와 상호작용). 스텝당 reward가 `O(0.01~1)` 범위에 오도록 조정
- **entropy 붕괴 / 폭주**: `α` auto-tuning 쓰고, `α` 값을 항상 로깅

### 6-4. Two-Phase Curriculum 구현

```
Phase 1 (Solo Time Trial)
  - opponent를 트랙 bounding box 밖 100m로 격리
  - 목표: curvature 기반 속도 조절 + wall avoidance 학습
  - 전이 조건: lap completion rate의 EMA > 60% (window 100 episodes, 최소 2,000 episodes)
Phase 2 (Dynamic Overtaking)
  - opponent를 앞쪽에 spawn, gap을 점진적으로 좁힘 (넓게 시작 → 좁게)
  - opponent = Pure Pursuit, lookahead 프로파일 랜덤화 (aggressive 20% / defensive 20% / nominal 60%)
```
- **전이 조건 로깅을 반드시 남긴다** (언제 Phase 2로 넘어갔는지 모르면 실패 원인 분석 불가)
- opponent 랜덤화 = **특정 상대에 overfit 되는 것 방지**. self-play 대신 이 방식을 쓴 건
  non-stationarity(상대도 같이 변해서 학습이 불안정)를 피하려는 **합리적 선택**이다
- Pure Pursuit opponent는 **`controller/controller/combined` 를 그대로 재사용** ★

---

## 7. Stage 6 — Sim-to-Real (1~2주) ★

### 7-1. Reality gap의 실제 원인 (1/8 RC카 기준 체크리스트)

| 원인 | 대응 |
|---|---|
| tire friction / 노면 변화 | friction coefficient **domain randomization** |
| **actuator latency** (서보 응답 지연, ESC 지연) | latency randomization + 시뮬에 delay buffer 삽입 |
| 제어 주기 지터 (Jetson 부하) | 고정 주기 실행 + 지터 randomization |
| LiDAR noise / dropout / 반사 | scan에 gaussian noise, random dropout, max-range 처리 |
| VESC 속도 추정 오차 (ERPM→m/s) | `v_x` 관측에 noise + bias randomization |
| 배터리 전압 sag (2S×2 LiHV) | 최대 가속/속도 스케일 randomization |
| 질량/무게중심 (1/8 chassis) | mass, CoM, `I_z` randomization |

### 7-2. 자료

| 자료 | 비고 |
|---|---|
| ★ [**Wheeled Lab** — Modern Sim2Real for Low-cost Wheeled Robotics (arXiv:2502.07380)](https://arxiv.org/abs/2502.07380) · [GitHub](https://github.com/UWRobotLearning/WheeledLab) · [사이트](https://uwrobotlearning.github.io/WheeledLab/) | **우리 프로젝트에 가장 가까운 오픈소스**. Isaac Lab 기반 1/10 RC카 zero-shot sim2real (drifting/traversal/visual nav). Tier 2 구축 시 여기 코드를 뼈대로 |
| ★ [RealLab — Wheeled Lab 정책 배포 플랫폼](https://github.com/UWRobotLearning/RealLab) | 실차 배포(ROS) 레퍼런스 |
| ★ [Tobin et al., *Domain Randomization* (arXiv:1703.06907)](https://arxiv.org/abs/1703.06907) | DR 원조 |
| ★ [Peng et al., *Sim-to-Real Transfer with Dynamics Randomization* (arXiv:1710.06537)](https://arxiv.org/abs/1710.06537) | **dynamics randomization** — 우리에게 더 중요 (LiDAR보다 동역학 gap이 큼) |
| ○ [Isaac Lab 공식 문서](https://isaac-sim.github.io/IsaacLab/) | Tier 2. PPO/SAC, GPU 병렬 env, TorchScript export |
| ○ [Isaac Lab 논문 (arXiv:2511.04831)](https://arxiv.org/abs/2511.04831) | 프레임워크 개요 |
| ○ [*Sim-to-Real for Mobile Robots: Isaac Sim → Gazebo → real ROS 2* (arXiv:2501.02902)](https://arxiv.org/abs/2501.02902) | ROS 2 연결 파이프라인 실무 |
| △ [*The Reality Gap in Robotics: Challenges, Solutions, Best Practices* (arXiv:2510.20808)](https://arxiv.org/abs/2510.20808) | 서베이 |

### 7-3. 실차 배포 체크리스트 (Tier 3)

- [ ] policy를 **ONNX → TensorRT** 로 export (Jetson Orin Nano). PyTorch 직접 추론은 지터가 큼
- [ ] **observation 전처리를 시뮬과 비트 단위로 동일하게**: LiDAR 1080→270 downsample 방식, 각도 범위, clip 값, normalize 통계
- [ ] **고정 제어 주기** + 주기 위반 로깅
- [ ] **Action Low-Pass Filter**: `a_t = (1-α)a_{t-1} + α·a_model`, 시뮬 `α=1.0` → 실차 `α=0.4~0.6`
      (서보/모터 보호 + jerk 억제. **시뮬에서도 낮은 α로 한 번 검증**해두면 gap이 줄어든다)
- [ ] **E-stop / watchdog**: 추론 실패, 센서 끊김, 통신 두절 시 즉시 정지 → `controller/estop.py` 재사용
- [ ] **속도 상한 램프업**: 처음엔 `v_max` 를 50%로 clamp하고 단계적으로 올림
- [ ] **fallback controller**: policy 이상 시 `controller/ftg` (Follow-the-Gap)로 전환

---

## 8. Stage 7 — 레이싱 도메인 자료 (병행 참고) ○

| 자료 | 비고 |
|---|---|
| ★ [F1TENTH Learn (공식 강의자료)](https://f1tenth.org/learn.html) | 플랫폼 전반 |
| ★ [f1tenth_gym (공식)](https://github.com/f1tenth/f1tenth_gym) | Tier 1 환경의 upstream. unicorn stack에 fork되어 들어있음 |
| ★ [BDEvan5/f1tenth_drl](https://github.com/BDEvan5/f1tenth_drl) | **TD3 vs SAC** end-to-end 레이싱 비교 실험. 코드 구조 참고 최적 |
| ★ [BDEvan5/f1tenth_benchmarks](https://github.com/BDEvan5/f1tenth_benchmarks) | classic + RL 벤치마크 모음. 우리 baseline 비교표 만들 때 |
| ○ [meraccos/f1tenth_reinforcement_learning](https://github.com/meraccos/f1tenth_reinforcement_learning) + [논문 arXiv:2309.00296](https://arxiv.org/pdf/2309.00296) | *End-to-end Lidar-Driven RL for Autonomous Racing* — 우리 관측 설계와 거의 동일 |
| ○ [luigiberducci/racing-rl](https://github.com/luigiberducci/racing-rl) | observation space 변형 실험 |
| ○ [RoboRacer(F1TENTH) 종합 서베이 (arXiv:2506.15899)](https://arxiv.org/pdf/2506.15899) | **분야 지도 한 방에 파악**. 초반에 훑어보면 좋음 |
| ○ [*Accelerating Real-World Overtaking in F1TENTH Racing with RL* (arXiv:2510.26040)](https://arxiv.org/pdf/2510.26040) | Phase 2(추월)의 최신 레퍼런스 |
| ○ [*Drive Fast, Learn Faster: On-Board RL for High Performance Autonomous Racing* (arXiv:2505.07321)](https://arxiv.org/html/2505.07321v1) | 실차 on-board 학습 |
| △ [GT Sophy — *Outracing champion Gran Turismo drivers with deep RL* (Nature 2022)](https://www.nature.com/articles/s41586-021-04357-7) | reward 설계 / 스포츠맨십 제약의 교과서 |
| △ [*Autonomous Overtaking in GT Sport using Curriculum RL* (arXiv:2103.14666)](https://arxiv.org/abs/2103.14666) | curriculum + 추월. TM07 Phase 2와 직접 대응 |
| △ [ForzaETH Race Stack](https://github.com/ForzaETH/race_stack) | **unicorn-racing-stack의 뿌리**. 모듈 이름이 거의 동일해 원 문서가 도움됨 |
| △ [TUM global_racetrajectory_optimization](https://github.com/TUMFTM/global_racetrajectory_optimization) | `planner/gb_optimizer` 의 upstream. centerline/waypoint 생성용 |

---

## 9. `unicorn-racing-stack` 재사용 판정표 ★

실제로 clone해서 트리를 확인한 결과다. (`git clone --recursive` 필수 — `race_utils/raycaster`,
`race_utils/unicorn_gym`, `state_estimation/kiss_icp_localization` 은 **submodule**)

### 9-1. 그대로 가져가는 것 ★

| 경로 | 원래 역할 | RL 스택에서의 용도 |
|---|---|---|
| `race_utils/unicorn_gym` (→ `f1tenth_gym`, pip `f110_gym`) | SIL 시뮬레이터 | **Tier 1 학습 환경 그 자체.** Gymnasium 래퍼만 새로 씌우면 됨 |
| `race_utils/raycaster` (→ `range_libc`) | 2D ray casting | LiDAR 시뮬 + **privileged obs의 "pixel-level raycasting wall distance"** |
| `race_utils/f110_utils/libs/frenet_conversion` | Cartesian ↔ Frenet `(s, d)` | **`r_progress`, `e_lat`, `e_psi` 계산의 핵심.** 직접 짜지 말 것 |
| `race_utils/f110_utils/nodes/lap_analyser` | lap time / 완주 판정 | **curriculum 전이 게이트(lap completion EMA)** + 평가 지표 |
| `race_utils/f110_msgs` | `WpntArray`, `LapData`, `ObstacleArray` 등 | 메시지 정의 재사용 (평가·로깅·시각화) |
| `controller/controller/combined` (Pure Pursuit/MAP) | 주행 제어 | **Phase 2의 opponent 정책** (lookahead 랜덤화만 추가) |
| `controller/controller/ftg` (Follow-the-Gap) | reactive 주행 | **baseline 비교군 + 실차 fallback** |
| `controller/estop.py` | 비상 정지 | 실차 안전장치 |
| `planner/gb_optimizer` (TUM) | global raceline 최적화 | raceline 추종은 안 하지만 **centerline/waypoint 생성**은 필요 (progress·opponent spawn·평가) |
| `sensor/urg_node`, `sensor/vesc` | Hokuyo LiDAR / VESC 드라이버 | **Tier 3 실차 그대로** |
| `stack_master/` (launch, maps, config) | 런치·맵·차량 파라미터 | 맵 자산 + 런치 골격. **단 `veh_dyn_info`는 1/8 스케일로 재측정 필요** |
| `unicorn.sh`, `environment.yml`, `setup_conda_*.sh` | RoboStack 개발환경 | 개발환경 그대로. **PyTorch만 추가 설치** |
| `state_estimation/` (cartographer, particle_filter, kiss_icp) | SLAM / localization | E2E policy 자체엔 불필요하지만 **맵 제작, lap counting, 평가, 대회 룰 대응**에 필요 |

### 9-2. 버리거나 baseline으로만 남기는 것 ✗

| 경로 | 이유 |
|---|---|
| `planner/spliner`, `planner/spliner_planner`, `planner/sqp_planner`, `planner/lane_change_planner`, `planner/recovery_spliner` | **E2E policy가 planning을 통째로 대체.** 성능 비교용 baseline으로만 보관 |
| `prediction/gp_traj_predictor` | opponent 미래 궤적 예측 → **privileged obs + history stacking이 대체** |
| `perception/` (opponent detection/tracking) | E2E는 raw LiDAR를 직접 먹음 → 불필요. 단 `r_overtake`/`TTC` 계산용 **ground-truth opponent 정보는 시뮬에서 직접** 뽑는다 |
| `state_machine/` | curriculum manager로 대체. 단 **실차 안전 FSM(pit/estop/manual)** 부분은 남길 가치 있음 |

### 9-3. 새로 만들어야 하는 것 (여기가 우리 작업의 실체)

```
rl_racing/
├─ envs/
│   ├─ racing_env.py          # Gymnasium API 래퍼 (f110_gym 위)
│   ├─ observation.py         # actor obs (270 scan ×4 + ego) / critic obs (24-dim privileged)
│   ├─ reward.py              # r_progress + r_safety + r_TTC + r_overtake + B_steer
│   ├─ opponent.py            # Pure Pursuit opponent + lookahead randomization
│   └─ randomization.py       # domain randomization (friction, mass, latency, noise)
├─ curriculum/
│   └─ manager.py             # Phase 1 → Phase 2 state machine, EMA gate
├─ algo/
│   └─ asymmetric_sac.py      # CleanRL sac_continuous_action.py fork
├─ deploy/
│   ├─ export_onnx.py
│   └─ policy_node.py         # ROS 2 node: /scan → policy → /drive (+ low-pass filter α)
└─ configs/
```

---

## 10. 제안 마일스톤 (총 6~9주)

| # | 목표 | 기간 | Exit Criteria |
|---|---|---|---|
| **M0** | 환경 구축 | 1~2일 | `unicorn` 환경에서 sim 런치 성공 + **ROS 없이 순수 python으로 `f110_gym` 한 스텝 실행** 성공 |
| **M1** | Gym wrapper v0 | 3~5일 | `env.reset()/step()` 이 Gymnasium API 준수, random action으로 100 에피소드 무크래시 |
| **M2** | SAC baseline | 2~3일 | **SB3 SAC**로 solo 트랙 1랩 완주하는 policy 확보 (느려도 됨). 이게 되면 파이프라인이 살아있다는 뜻 |
| **M3** | Asymmetric SAC | 1주 | CleanRL fork에 privileged critic 적용, M2 대비 **동일 step 수에서 lap rate 향상** 확인 |
| **M4** | Reward + Curriculum | 1~2주 | `B_steer`·TTC 적용 후 steering 진동 감소(정량 로그), Phase 1→2 자동 전이 로그 확인, 추월 성공률 측정 |
| **M5** | Tier 2 (Isaac Sim/Lab) | 1~2주 | 동일 policy가 Isaac Sim에서 완주. 실패하면 **domain randomization 범위 확대 후 Tier 1 재학습** |
| **M6** | Tier 3 (실차) | 1~2주 | Jetson에서 TensorRT 추론 주기 만족, `α=0.5` 로 저속 완주 → 단계적 속도 상향 |

**리스크 1순위**: 1/8 Serpent 차량 파라미터 미확보. → **M0~M1과 병행해서 실차 system identification**
(스텝 응답으로 steering 지연/게인, 가감속 프로파일, 최대 횡가속도 측정)을 시작하는 걸 강력 권장한다.
이게 늦어지면 M5~M6에서 전부 다시 학습해야 한다.

---

## 11. 용어집 (Glossary)

| 용어 (원문 유지) | 한 줄 설명 |
|---|---|
| **MDP** | `(S, A, P, R, γ)`. RL 문제의 표준 수학적 틀 |
| **POMDP** | 관측이 상태의 일부만 담는 MDP. 우리 실차가 여기 해당 |
| **policy `π(a|s)`** | 상태를 보고 행동을 고르는 함수. 우리가 학습해서 차에 올리는 것 |
| **on-policy / off-policy** | 현재 policy로 모은 데이터만 쓰는가 / 과거 데이터도 재사용하는가. SAC는 off-policy |
| **replay buffer** | 과거 transition `(s,a,r,s')` 저장소. off-policy의 sample efficiency 근원 |
| **target network** | 학습 타깃 계산용 느리게 따라오는 복사본. `τ`로 soft update |
| **actor-critic** | actor = policy, critic = value function. 둘을 같이 학습 |
| **maximum entropy RL** | `reward + α·entropy` 를 최대화. SAC의 정체성 |
| **temperature `α`** | entropy 항의 가중치. 클수록 더 무작위하게 행동 (탐색↑) |
| **reparameterization trick** | `a = tanh(μ + σ·ε)` 로 샘플링해 gradient가 policy를 통과하게 하는 기법 |
| **squashed Gaussian** | Gaussian 샘플에 `tanh`를 씌워 action을 `[-1,1]`로 제한한 policy |
| **twin Q / clipped double Q** | Q network 2개의 최솟값 사용 → overestimation 억제 (TD3에서 유래) |
| **privileged observation** | 시뮬에서만 얻을 수 있는 특권 정보 (절대좌표, 정확한 wall distance 등) |
| **asymmetric actor-critic** | critic만 privileged obs를 받고, actor는 실차 obs만 받는 구조 |
| **frame stacking** | 최근 `N` 프레임을 이어붙여 관측. 속도·변화율 정보를 복원 |
| **curriculum learning** | 쉬운 과제 → 어려운 과제로 점진 전환. TM07의 Phase 1→2 |
| **reward shaping** | 학습을 돕는 보조 보상 설계. potential-based면 optimal policy 불변 |
| **TTC (Time-To-Collision)** | `Gap / (v_ego - v_opp)`. 작을수록 위험 |
| **Frenet frame `(s, d)`** | 트랙 중심선 기준 종방향 진행거리 `s` / 횡방향 오프셋 `d` |
| **`e_lat`, `e_psi`** | 중심선 대비 lateral error / heading error |
| **domain randomization** | 시뮬 파라미터를 무작위화해 실차에 robust한 policy를 얻는 기법 |
| **dynamics randomization** | 그중 특히 질량·마찰·지연 등 **동역학** 파라미터 무작위화 |
| **sim-to-real gap / reality gap** | 시뮬과 실제의 차이. 그대로 옮기면 성능이 무너지는 원인 |
| **zero-shot transfer** | 실차에서 추가 학습 없이 바로 동작시키는 것 |
| **action low-pass filter** | `a_t = (1-α)a_{t-1} + α·a_model`. 고주파 명령 억제, 액추에이터 보호 |
| **EMA (Exponential Moving Average)** | 지수이동평균. curriculum 전이 판정과 target network update 양쪽에 등장 |

---

## 12. "일단 이것부터" — Top 8

이 문서가 길어서 어디부터 볼지 모르겠다면, 순서대로 딱 8개만.

1. [팡요랩 강화학습 기초 이론 (인프런 무료)](https://www.inflearn.com/course/%EA%B0%95%ED%99%94%ED%95%99%EC%8A%B5) — 1~5강까지만 먼저
2. [바닥부터 배우는 강화 학습](https://product.kyobobook.co.kr/detail/S000000555527) — 병행 정독
3. [Spinning Up — SAC 페이지](https://spinningup.openai.com/en/latest/algorithms/sac.html) — 논문보다 먼저
4. [CleanRL `sac_continuous_action.py`](https://github.com/vwxyzjn/cleanrl/blob/master/cleanrl/sac_continuous_action.py) — 한 줄씩 읽기
5. 첨부 논문 [SAC (1801.01290)](https://arxiv.org/abs/1801.01290) §3.2 → §4 → Appendix C
6. [SAC v2 (1812.05905)](https://arxiv.org/abs/1812.05905) — auto entropy tuning
7. [Asymmetric Actor Critic (1710.06542)](https://arxiv.org/abs/1710.06542) — 짧음
8. [Wheeled Lab](https://github.com/UWRobotLearning/WheeledLab) — 우리가 갈 길의 실물 예시

---

## 부록 A. 참고한 출처

- 첨부 문서 ①: Haarnoja et al., *Soft Actor-Critic: Off-Policy Maximum Entropy Deep RL with a Stochastic Actor*, arXiv:1801.01290v2
- 첨부 문서 ②: Choi, Lim, Jung, Kim, Choi (In The END, Soongsil University), *Reinforcement Learning End-to-End Autonomous Racing Architecture with Asymmetric SAC and Sim-to-Real Pipeline* (TM07)
- 코드베이스: [HMCL-UNIST/unicorn-racing-stack](https://github.com/HMCL-UNIST/unicorn-racing-stack) (ROS 2 Jazzy, `main` 브랜치 실제 clone 후 분석)
