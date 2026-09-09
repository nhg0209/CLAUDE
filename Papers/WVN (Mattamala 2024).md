---
tags: [paper]
제목: "Wild Visual Navigation: Fast Traversability Learning via Pre-Trained Models and Online Self-Supervision"
저자: Matias Mattamala, Jonas Frey, Piotr Libera, Nived Chebrolu, Georg Martius, Cesar Cadena, Marco Hutter, Maurice Fallon
연도: 2024
학회: ❓ (arXiv preprint. 선행 학회판은 RSS 2023)
arxiv: 2404.07110
플랫폼: ANYmal C / D (4족보행) + Jetson Orin AGX
지형: 숲·공원 잔디·흙길·자갈길, 실내→실외
이해도: 🔴
상태: 정리 완료
읽은날짜: 2026-09-08
---

# Wild Visual Navigation (WVN)

> [!abstract] 한 줄 요약
> 사람이 몇 분간 로봇을 몰고 다니는 동안, **속도 명령과 실제 속도의 오차(traction)** 를 라벨로 삼아
> 사전학습 시각 feature 위의 작은 MLP를 **현장에서 온라인으로** 학습시켜 dense traversability를 예측한다.

[[논문 목록]]

> [!info] 판본
> 이 PDF는 `arXiv:2404.07110v1` (2024-04-10) 스탬프. **RSS 2023 논문 [10]의 확장판**이다.
> 확장된 부분: multi-camera, STEGO feature/segment 추가, sub-sampling 전략 비교, pixel-wise inference,
> 오픈소스 ROS 구현. **ablation은 이 논문에 없고 [10]에 있다** (§3.5.3 명시).

---

## 1. 문제 정의

### 무엇을 풀려고 하는가

RGB 이미지로부터 **dense traversability score**를 추정한다 (§3.1).
traversability는 affordance [1] — *"어느 영역을 지날 수 있고 그 비용은 얼마인가"* (§1).

### 기존 방법이 어디서 깨지는가

| 접근 | 논문이 지적한 한계 | 위치 |
|---|---|---|
| **기하 기반** (점군·메시·elevation map) | **높은 풀·잔가지·덤불**이 강체 장애물로 잘못 인식된다. "natural growth"를 표현하기에 기하만으로는 불충분 | 초록, §2.1 |
| **Semantic segmentation** | 사전 정의된 class label에 의존. 대량의 관련 학습 데이터를 모으고 라벨링하는 문제가 반복된다 | §1, §2.2 |
| **기존 자기지도** | 과거 배포 데이터로 데이터셋을 만들지만(hindsight [6], MPC 궤적 [7]), **로봇별 데이터셋으로 학습한 뒤 추가 적응 없이 배포**된다 | §1, §2.3 |
| **Anomaly 기반** | (WVN은 traversability 판정에 직접 쓰지 않고 **confidence 지표로만** 사용) | §2.4 |

> [!note] 다리형 로봇이라는 전제
> 새로운 이동 능력을 가진 플랫폼(legged)의 등장이 **traversability 정의 자체의 재고**를 요구한다는 것이
> §1의 출발점이다. 바퀴형이 못 가는 자연 지형을 갈 수 있기 때문.

### 기여 (§1, 5개)

1. **온라인 multi-camera** 자기지도 파이프라인 (원본은 단일 카메라)
2. 사전학습 모델을 feature backbone으로: **DINO-ViT** [11] + (신규) **STEGO** [12]
3. **feature sub-sampling 전략** — 기존 SLIC [13] 외에 추가 전략
4. 실차 실험: 온보드 실행, 카메라 1대 및 다수
5. **오픈소스 ROS 구현** + 여러 환경에서 학습된 baseline 가중치

---

## 2. 핵심 아이디어

![[fig1.jpg]]

**Fig. 1** — 무작위 초기화 상태(a)에서 사람이 로봇을 통과 가능한 곳으로 몰고 다니면(b),
몇 분 뒤 traversable(파랑 ■)과 untraversable(빨강 ■)을 구분하게 되고(c), 자율주행이 가능해진다(d).

두 축이다:

1. **사전학습 자기지도 모델의 고차원 feature를 쓴다.** 이 feature가 semantic을 암묵적으로 담고 있어서
   **학습 과제가 대폭 단순해진다** — 남는 일이 `feature → 스칼라` 회귀뿐이다 (초록, §1, §3.5).
2. **supervision 생성기를 온라인으로 돌린다.** 그래서 학습과 추론이 현장에서 동시에 진행된다 (초록).

---

## 3. ★ Supervision — 무엇이 라벨인가

### 3-1. 라벨 값: traction (§3.3.1)

무엇이 traversable인지는 **플랫폼 능력에 따라 다르다**. 그래서 사람이 라벨을 주지 않고,
**terrain traction** [38] 을 쓴다 — 로봇이 추정한 자기 선속도 $(v_x, v_y)$ 와
**외부(사람 조종자 또는 planner)가 내린 기준 속도 명령** $(\bar v_x, \bar v_y)$ 의 불일치.

$$v_{\text{error}} = \frac{1}{2}\left[(\bar v_x - v_x)^2 + (\bar v_y - v_y)^2\right] \in \mathbb{R} \tag{1}$$

$v_{\text{error}}$ 를 **1-D Kalman filter로 평활**한 뒤 sigmoid로 $[0,1]$ 에 사상:

$$\tau = \text{sigmoid}\left(-k\,(v_{\text{error}} - v_{\text{thr}})\right) \tag{2}$$

| 기호 | 의미 |
|---|---|
| $\tau \in [0,1]$ | traversability score. 0 = untraversable, 1 = fully traversable |
| $k$ | sigmoid의 기울기(steepness) |
| $v_{\text{thr}}$ | $\tau = 0.5$ 가 되는 sigmoid 중점 |

$k$ 와 $v_{\text{thr}}$ 는 **플랫폼의 운동 사양에 맞춰 캘리브레이션**한다 (§3.3.1).

> [!important] 즉 라벨의 물리적 의미
> **"명령한 속도가 실제로 나왔는가."** 안 나왔으면 그 지형은 덜 traversable하다.
> 라벨을 만드는 데 필요한 것은 **속도 명령 + 상태추정 속도**뿐이고, 사람 annotation도 시뮬도 없다.

### 3-2. 라벨을 이미지에 붙이는 법: 두 개의 그래프 (§3.4)

![[fig5.png]]

**Fig. 5** — (a) 두 그래프가 미션 동안 저장하는 정보. **Supervision Graph**(파랑)는 슬라이딩 윈도우로
로봇 footprint만 임시 저장하고, **Mission Graph**(회색)는 온라인 학습에 필요한 데이터를 미션 전체에 걸쳐 보관한다.
footprint patch의 색이 생성된 traversability score. (b) 그래프 간 상호작용 — footprint와 score를
**과거 mission node의 이미지로 재투영**해서 라벨을 갱신한다.

그래프 기반 SLAM의 local/global 그래프 구조에서 착안했다 (§3.4).

| | **Supervision Graph** (§3.4.1) | **Mission Graph** (§3.4.2) |
|---|---|---|
| 저장 내용 | 현재 시각, 로봇 pose, 추정된 $\tau$ | RGB 이미지 $\mathbf{I}$, weak segmentation mask $\mathbf{M}$, per-segment feature $\mathbf{f}_n$ 와 그 라벨 $\tau_n$ |
| 자료구조 | **ring buffer**, 노드 수 $N_{\text{sup}}$ 고정 | 미션 전체 누적 |
| 노드 추가 조건 | 노드 간 거리 $d_{\text{sup}}$ | 마지막 노드로부터 거리 $> d_{\text{mis}}$ (feature 추출 후) |
| 역할 | **footprint track**(발자국 궤적 + $\tau$)을 보관 | 학습 배치의 원천 |

**Supervision generation (§3.4.3)** — 새 mission node가 추가될 때:

1. footprint track과 그에 딸린 $\tau$ 를 **고정 범위 내 모든 mission node의 이미지로 재투영** → 보조 이미지 $\mathbf{S}$
2. weak segmentation mask $\mathbf{M}$ 으로 **segment마다 점수를 평균** → $\tau_n$
3. ⚠️ **재투영된 footprint track과 겹치지 않는 segment는 0(untraversable)으로 설정**

결과물은 mission node마다 $(\mathbf{f}_n,\ \tau_n)$ 쌍.

> [!danger] 3번이 이 방법의 구조적 문제이고, §3.5가 그걸 메우려는 장치다
> 안 밟아본 곳은 전부 0이 된다. 실제로는 **밟을 수 있는데 아직 안 밟았을 뿐**인 곳이 대부분이다.
> 이 편향을 confidence로 눌러주는 것이 아래 §3.5.1~3.5.2.

---

## 4. 방법

### 4-1. 전체 구조 (§3.1)

![[fig2.png]]

**Fig. 2** — 입력은 **단안 RGB 이미지, odometry, proprioception뿐**.
위(파랑) = Feature Extraction & Inference 프로세스, 아래(회색) = Online Learning 프로세스.

**서로 다른 주기로 도는 2-프로세스 시스템**이다.

| 프로세스 | 하는 일 |
|---|---|
| **Feature Extraction & Inference** | 여러 카메라의 이미지 처리 → 시각 feature 추출 → traversability를 픽셀 단위로 추론 |
| **Online Learning** | proprioception으로 $\tau$ 추정 → hindsight로 supervision 생성 → 내부 학습 루프로 모델 갱신 |

전자는 이미지가 들어오는 대로 학습용 feature를 공급하고, 후자는 **고정 주기로 최신 모델을 넘긴다**.

### 4-2. 기호 (Table 1)

| 기호 | 정의 |
|---|---|
| $\mathbf{I}$ | RGB 이미지, 높이 $H$ × 너비 $W$ |
| $\mathbf{F}$ | feature map, 차원 $E \times H \times W$, **$E = 90$ 또는 $384$** |
| $\mathbf{M}$ | weak segmentation mask, $H \times W$ |
| $\mathbf{S}$ | 재투영된 supervision, $H \times W \in [0,1]$ |
| $\tau$ | traversability score $\in [0,1]$ |
| $\mathbf{f}_n$ | segment $n$ 의 embedding, 차원 $E = 90$ 또는 $384$ |
| $\tau_n$ | segment $n$ 의 traversability score |

### 4-3. Feature 추출 · 추론 (§3.2)

![[fig3.png]]

**Fig. 3** — camera scheduler가 카메라 풀에서 하나를 고르고(§3.2.1), feature extractor가 dense feature
$\mathbf{F}$ 를 뽑고(§3.2.2), sub-sample 모듈이 weak segmentation 기반으로 $\{\mathbf{f}_n\}$ 로 줄이고(§3.2.3),
inference 모듈이 traversability를 예측한다(§3.2.4).

**① Multi-camera (§3.2.1)** — 원본 WVN은 단일 카메라라 **카메라 FoV 안의 움직임으로 제한**되는 한계가 있었다.
**weighted round-robin** [36] 기반 camera scheduler로 **한 번에 한 카메라만** 처리한다.
우선순위는 "학습+추론용" 카메라인지 "추론 전용"인지로 정한다.

**② Feature 추출 (§3.2.2)** — 미세조정 CNN 대신 자기지도 사전학습 모델을 쓴다.

| backbone | 차원 $E$ | 비고 |
|---|---|---|
| **DINO-ViT** [11] | **384** | 픽셀 단위 embedding |
| **STEGO** [12] | **90** | DINO-ViT backbone + contrastive 학습 레이어. **segmentation mask도 같이 제공** |

입력 이미지는 **$224 \times 224$ 로 리사이즈**. dense $\mathbf{F}$ 는 **온라인 학습용으로 GPU 메모리에 담기엔 너무 커서** sub-sampling이 필요하다.

**③ Feature sub-sampling (§3.2.3)** — $224 \times 224$ → **약 100개**의 embedding $\{\mathbf{f}_n\}$.
weak segmentation으로 이미지를 segment $\mathbf{M}$ 으로 나누고 **각 segment 내부의 embedding을 평균**한다.

| 전략 | 내용 | 논문이 지적한 성질 |
|---|---|---|
| **SLIC** [13] | 원본 구현. 이미지당 ~100 segment | 계산이 빠르지만 **텍스처 기반이라 semantic으로 묶이지 않는다** |
| **STEGO** | class-free segment. semantic affinity를 암묵적으로 인코딩 | $\mathbf{M}$ 을 직접 정의 |
| **Random** | feature map에서 embedding 100개를 무작위 선택 | segment 없이 **feature 위치만** 있음 |

![[fig4.jpg]]

**Fig. 4** — 세 예시 이미지에 대한 segmentation 비교.
**SLIC**은 과분할하지만 semantic으로 일관되지 않는다 (윗줄: 울타리와 지면이 한 segment로 병합).
**STEGO(원본)** 는 semantic과 맞지만 전체 데이터셋에서 prototype vector를 계산하기 때문에
semantic class 수가 제한되어 **두 class가 한 segment로 병합**된다 (아랫줄: 잔디와 보도).
**STEGO(수정판)** 는 과분할하면서도 배포 전에 prototype vector를 정하지 않고 semantic을 유지한다.

> [!important] STEGO를 그대로 못 쓰는 이유와 수정 (§3.2.3)
> 원본 STEGO는 **오프라인에서 데이터셋 전체에 걸쳐 prototype feature vector를 계산**하고,
> 픽셀을 그 prototype과의 cosine 유사도로 class에 배정한다.
> WVN은 **고정된 class 집합이 없고**, 적절한 prototype은 **배포 환경에 크게 의존**하므로 미리 정할 수 없다.
> → **이미지마다 KNN 클러스터링으로 고정 개수의 prototype feature를 계산**한다.
> 이러면 이미지당 segment 개수가 보장된다. 수정판 전체를 오픈소스로 공개했다.

**④ 추론 (§3.2.4)** — 두 방식

- **Segment-wise**: 원본 [10] 방식. embedding $\mathbf{f}_n$ 마다 $\tau_n$ 을 예측하고 **그 segment의 모든 픽셀에 같은 값**을 준다
- **Pixel-wise**: dense feature $\mathbf{F}$ 에서 직접 예측. MLP forward pass는 배치로 돌리면 지연이 작다

### 4-4. Confidence 추정 — anomaly detection (§3.5.1)

밟아본 segment feature 전체의 분포를 학습한다. encoder-decoder $f^{\theta_r}_{\text{reco}}$ 가
$\mathbf{f}_n$ 을 저차원 latent로 압축했다가 복원하고, 손실은 채널 $E$ 에 대한 MSE:

$$
\mathcal{L}_{\text{reco}}(\mathbf{f}_n) =
\begin{cases}
\dfrac{1}{E}\sum_e \left\lVert f^{\theta_r}_{\text{reco}}(\mathbf{f}_{n,e}) - \mathbf{f}_{n,e}\right\rVert^2 & \text{if traversed} \\[6pt]
0 & \text{otherwise}
\end{cases}
\tag{3}
$$

**밟아본 embedding만 복원하도록 학습**되므로, 밟아본 것과 비슷한 feature는 복원 손실이 작고
나무·하늘처럼 복원해 본 적 없는(anomalous) feature는 손실이 크다.

무한대로 열린 $\mathcal{L}_{\text{reco}}$ 를 $c \in [0,1]$ 로 사상하기 위해,
**배치 내 밟아본 segment들의 복원 손실에 Gaussian을 적합**한다:

$$\mu_{\text{pos}} = \frac{1}{n_{\text{trav}}}\sum_{n \in \mathcal{T}} \mathcal{L}_{\text{reco}}(\mathbf{f}_n) \tag{4}$$

$$\sigma_{\text{pos}} = \sqrt{\frac{1}{n_{\text{trav}}}\sum_{n \in \mathcal{T}}\left(\mathcal{L}_{\text{reco}}(\mathbf{f}_n) - \mu_{\text{pos}}\right)^2} \tag{5}$$

- $\mathcal{T}$ = 밟아본 segment 집합 (로봇 센싱 데이터로 계산된 유효한 $\tau_n$ 이 있는 것)
- $n_{\text{trav}}$ = 밟아본 segment의 총 개수

**손실이 $\mu_{\text{pos}}$ 보다 작으면 confidence를 1로 설정**하고, 그렇지 않으면
정규화되지 않은 Gaussian likelihood로 평가한다:

$$c(\mathcal{L}_{\text{reco}}(\mathbf{f}_n)) = \exp\left(\frac{\left(\mathcal{L}_{\text{reco}}(\mathbf{f}_n) - \mu_{\text{pos}}\right)^2}{2\left(\sigma_{\text{pos}}\,k_\sigma\right)^2}\right) \tag{6}$$

$k_\sigma$ 는 confidence를 조절하는 튜닝 파라미터.

> [!warning] 식 (6)은 논문에 인쇄된 그대로 옮겼다 — 지수에 마이너스가 없다
> PDF 원문(p.7)을 확대해 확인했다. 그런데 같은 절에서 논문은
> $c \in [0,1]$ 이라고 정의하고 이 식을 *"unnormalized Gaussian likelihood"* 라고 부른다.
> **둘 다 지수가 음수여야 성립한다** ($\mathcal{L} > \mu_{\text{pos}}$ 일 때 지금 식은 $c > 1$).
> 논문은 이 불일치를 언급하지 않는다.

### 4-5. Traversability 추정 — confidence-weighted loss (§3.5.2)

$f^{\theta_t}_{\text{trav}}$ 는 단일 채널 출력으로 $\tau$ 를 회귀한다.
안 밟아본 segment는 **보수적으로 $\tau = 0$ 으로 두되, confidence로 그 기여를 스케일**한다.

$$
\mathcal{L}_{\text{trav}}(\mathbf{f}) =
\underbrace{\sum_{n \in \mathcal{T}} \left\lVert f^{\theta_t}_{\text{trav}}(\mathbf{f}_n) - \tau_n \right\rVert^2}_{\text{밟아본(라벨 있는) segment의 기여}}
+ \underbrace{\sum_{n \in \mathcal{T}^C} \left(1 - c(\mathbf{f}_n)\right)\left\lVert f^{\theta_t}_{\text{trav}}(\mathbf{f}_n) - 0 \right\rVert^2}_{\text{안 밟아본 segment의 기여}}
\tag{7, 8}
$$

$\mathcal{T}^C$ 는 안 밟아본 segment 집합. 세 경우로 갈린다 (§3.5.2):

| segment $n$ | 결과 |
|---|---|
| 밟았음 | $\mathcal{L}_{\text{trav}}(\mathbf{f}_n) = \lVert f_{\text{trav}}(\mathbf{f}_n) - \tau_n \rVert^2$ |
| 안 밟았고 **positive와 안 닮음** | $c \to 0$, $\mathcal{L}_{\text{trav}} \to \lVert f_{\text{trav}}(\mathbf{f}_n) - 0 \rVert^2$ |
| 안 밟았고 **positive와 닮음** | $c \to 1$, $\mathcal{L}_{\text{trav}} \to 0$ — **손실에 기여하지 않음** |

논문의 표현: 이 구조가 **"이전에 unknown이던 샘플을 새 데이터로 덮어쓸 수 있게"** 하고,
네트워크가 **과도하게 비관적이 되는 대신 물리적 상호작용으로 측정한 traversability를 학습하도록** 유도한다.

**Traversability threshold $\tau_{\text{thr}}$** — local planner 입력으로 쓰려면 이진 판정이 필요하다.
학습 내내 **ROC를 계산**하되, **confidence < 0.5 인 모든 segment를 negative**,
**밟아본 segment를 positive** 로 놓고, 원하는 **False Positive Ratio (FPR)** 만 정해서 threshold를 결정한다.

### 4-6. 총 손실 (§3.5.3)

두 손실을 가중합해 **함께 학습**한다.

$$\mathcal{L}_{\text{total}}(\mathbf{f}) = w_{\text{trav}}\,\mathcal{L}_{\text{trav}}(\mathbf{f}) + w_{\text{reco}}\,\mathcal{L}_{\text{reco}}(\mathbf{f}) \tag{9}$$

| 항 | 무엇을 학습시키나 | 가중치 |
|---|---|---|
| $\mathcal{L}_{\text{trav}}$ | traversability head — 식 (7,8) | **0.03** |
| $\mathcal{L}_{\text{reco}}$ | encoder-decoder(confidence의 원천) — 식 (3) | **0.5** |

⚠️ **$w_{\text{reco}}$ 가 $w_{\text{trav}}$ 의 약 17배다.** 논문은 값만 제시하고 이 배분의 이유는 설명하지 않는다.

### 4-7. 구현 (§3.5.3)

| 항목 | 값 |
|---|---|
| $f^{\theta_r}_{\text{reco}}$, $f^{\theta_t}_{\text{trav}}$ | **2-layer MLP, [256, 32] dense + ReLU** |
| 가중치 공유 | **두 네트워크가 hidden layer 가중치를 공유** |
| head | reco: $E$개 출력 뉴런 / trav: 1채널 + sigmoid |
| bottleneck | **32채널 hidden layer** |
| optimizer | Adam [39], **고정 lr = 0.001** |
| 배치 | **1 update step당 유효 mission node 8개 무작위 선택**. 유효 = segment 하나 이상이 non-zero $\tau$ |
| 하이퍼파라미터 | $k_\sigma = 2$, $w_{\text{trav}} = 0.03$, $w_{\text{reco}} = 0.5$, **최대 FPR = 0.15** |
| ablation | **이 논문에 없음** — 선행 논문 [10] 참조 |

### 4-8. 폐루프 통합 (§4)

| 단계 | 내용 |
|---|---|
| **Local terrain mapping** (§4.1) | 오픈소스 terrain mapping [40, 41] → 온보드 depth 카메라 + LiDAR로 **robot-centric 2.5D elevation map**. 예측된 traversability 이미지를 **raycasting으로 융합**(지형 가림 고려), 시간 방향은 **exponential averaging** |
| **Local planning** (§4.2) | 투영된 시각 traversability를 **cost map**으로 써서 reactive local planner [42]가 **SE(2) twist** 생성 → 학습 기반 locomotion controller [3]에 입력 |
| **Autonomous path following** (§4.3) | 전방 카메라 FoV 내 local terrain map에서 **가장 먼 traversable 위치**를 찾아 goal을 계속 생성. **global planner도 대규모 표현도 쓰지 않는다** |

---

## 5. 실험 조건 (§5.1)

| 항목 | 내용 |
|---|---|
| 플랫폼 | **ANYbotics ANYmal C, ANYmal D** (4족보행) |
| 온보드 컴퓨트 | **NVIDIA Jetson Orin AGX** 추가 장착 |
| 상태추정 | 제조사 state estimator (SE(3) pose, body velocity) |
| 카메라 (ANYmal C) | Sevensense **Alphasense Core**의 global shutter 광각 1대 |
| 카메라 (ANYmal D) | 내장 **전방 + 후방** 광각 RGB |
| LiDAR·depth | **local terrain mapping 전용** (§4.1). traversability 학습에는 안 씀 |
| 소프트웨어 | 순수 Python, **PyTorch [43] + ROS 1** [14]. 두 프로세스 = 별도 ROS 노드 |
| 프로세스 간 통신 | ROS pub/sub. **모델 가중치는 5초마다 write-read로 공유** (단순화 목적) |
| 오프라인 분석 장비 | Nvidia Quadro T2000 Laptop GPU + Intel i7-10875H |

### 배포 목록

| # | 장소 | 플랫폼 | 학습 시간 | 핵심 |
|---|---|---|---|---|
| §5.2.1 | University Parks, Oxford | C | 3바퀴 원격조종 | 적응 속도 |
| §5.2.2 | Wytham Woods, Oxford | C | 몇 분 | 시각 vs 기하 비교 |
| §5.2.3 | 삼림지 | C | **2분** | 나무 사이 point-to-point 자율주행 |
| §5.2.4 | University Parks 산책로 | C | **2분 미만** | km 단위 경로 추종 (3회) |
| §5.2.5 | MPI Tübingen | D | 7분 세션 | multi-camera, 실내→실외 |

---

## 6. 결과의 해석

### 6-1. 적응 속도 (§5.2.1)

![[fig6.jpg]]

**Fig. 6** — 공원에서 3바퀴 원격조종(위, 경로 ■). 열 (a),(b),(c)는 경로의 서로 다른 지점,
행은 학습 step에 따른 traversability 추정 개선.

| 학습량 | 상태 |
|---|---|
| **9 step (21초)** | 매우 나쁜 segmentation |
| **800 step (2분)** | 흙길을 traversable로, 나무는 untraversable로 정확히 구분 |

논문이 스스로 지적한 실패: (c)의 **step 1186에서 나무 벽의 일부 segment가 잔디 패치와 잘못 묶였다**.
SLIC segmentation의 문제이고 다른 캡처에서는 관찰되지 않았다.

### 6-2. 시각 vs 기하 (§5.2.2) — 이 논문의 핵심 근거

![[fig7.jpg]]

**Fig. 7** — 같은 지형에 대한 세 방법의 traversability map(아랫줄)과 그로부터 만든 SDF(윗줄).
기하 기반은 **높은 풀이 만드는 elevation spike**에 크게 영향받는다.

비교 대상 3가지:
- 기하 **휴리스틱** — 지형의 높이·경사 [44]
- 기하 **학습 모델** — terrain mapping 시스템 [40]의 일부
- **WVN** — 시각 traversability를 terrain map에 raycast

| 항목 | 결과 |
|---|---|
| 나무 판정 | **세 방법 모두 성공** — 기하 방법도 나무는 제대로 untraversable로 판정 |
| **높은 풀** | 기하 방법은 elevation spike를 **untraversable로 오판**. WVN은 아니다 |
| SDF | traversability가 낮은 영역이 전부 장애물이 되므로 차이가 **더 극명** |

### 6-3. 자율주행 (§5.2.3, §5.2.4)

![[fig8.jpg]]

**Fig. 8** — (a) 2분 원격조종(■) 후 삼림지에서 자율주행(■). (b) 자율 운행 중 생성된 SDF 일부.
(c) 후처리로 만든 시험 구역의 2.5D 재구성과 예측 traversability.

- **8개 목표 중 8개 도달.** 조종자가 **일부러 나무 뒤에 목표를 놓아** 시스템을 시험했다
- 학습 중 **기하 정보도, 환경에 대한 추가 가정도 쓰지 않았다**
- ⚠️ 이 실험은 SLIC을 썼기 때문에 **일부 장애물 artifact가 관찰**됐다 (§5.2.5에서 개선)

![[fig9.jpg]]

**Fig. 9** — 공원 산책로. 출발점을 달리한 3회 주행. ■ run 1 (0.55 km), ■ run 2 (0.5 km), ■ run 3 (1.4 km).
교차로에서 minor intervention, ⋆ 표시는 진흙 패치를 길로 오분류해 major intervention이 필요했던 지점.

- 2분 미만 학습 후 **학습을 껐다** — 예측이 시연의 사람 선호를 엄격히 모사하도록
- 수백 미터를 **길 중앙을 유지하며** 잔디·덤불·벤치·보행자를 회피
- **run 2만 $k_\sigma = 3$, FPR $= 0.3$ 으로 완화** → 덜 보수적이 되어 **시각적으로 유사한 진흙 패치로 주행**, 수동 개입 필요
- 논문의 주장: 길 경계가 **기하학적으로 구분 불가능**한 경우가 많았고, 공원의 모든 통행 가능 class
  (포장도로·자갈길·차도·잔디)를 semantic segmentation으로 학습하는 대신 **짧은 시연 하나로 충분**했다

### 6-4. Multi-camera 실내→실외 (§5.2.5)

![[fig10.jpg]]

**Fig. 10** — 좌: 실제 장면과 시각 traversability 예측. 중: local terrain map에 투영된 시각 traversability.
우: elevation map에서 계산한 기하 traversability. (a)~(f)는 시간 순.

7분 원격조종, ANYmal D, **STEGO segment/feature + pixel-wise inference**.

| 지점 | 거리 | 결과 |
|---|---|---|
| (a) 실험실 | ~8 m | 바닥을 traversable로 인식 |
| (b) 복도 | ~40 m | **창문과 닫힌 유리문을 통행 불가로 정확히 분류. 기하 방법은 traversable로 오판** |
| (c) 안뜰 | ~86 m | 포장 보도 traversable |
| (d) 실외 보도 | ~127 m | 〃 |
| (e) 포장 도로 | ~148 m | 〃 |
| (f) 성긴 초지 | ~260 m | 초지를 traversable로. **기하 방법은 나무와 통과 가능한 식생을 구분 못 함** |

전·후방 카메라 통합으로 **Fig. 7에서 보인 FoV 제약을 극복**했고, 동적 환경에서 더 반응적인 거동이 가능하다.

### 6-5. Segment-wise vs Pixel-wise (§5.3.1)

![[fig11.jpg]]

**Fig. 11** — DINO / STEGO feature에 대해 segment-wise와 pixel-wise 추론을 정성 비교.

- 두 방식의 예측은 **대체로 일치**한다. 논문은 이를 feature 자체의 성질로 설명한다 (§5.3.2와 연결)
- **pixel-wise의 이점**: 세밀한 예측, 그리고 **SLIC 같은 weak segmentation이 유발하는 artifact를 무시**한다
  — Fig. 11 (b), (c)의 나무 줄기에서 보인다
- STEGO는 출력에 유의미한 차이를 만들지 않았고 밟은 영역을 일관되게 분할했다.
  다만 (d)행의 식물처럼 **과분할 문제**가 있었는데, 이는 **feature와 segment가 그 물체를 다른 밟은 영역과
  semantic하게 유사하다고 '합의'했음**을 시사한다

> [!warning] 논문의 그림 번호 오기
> §5.3.1 첫 문단은 *"Fig. 12 shows some examples of the traversability predictions…"* 라고 쓰지만,
> 같은 문단 뒤에서 **Fig. 11 (b), (c)** 를 가리키고 Fig. 11의 캡션이 "Inference approaches"다.
> **Fig. 11이 맞다.** Fig. 12는 sub-sampling 결과다.

### 6-6. Feature sub-sampling 비교 (§5.3.2)

![[fig12.jpg]]

**Fig. 12** — §5.2.4의 경로 추종 시퀀스 로그로 sub-sampling 방법 비교.
**STEGO가 예측 충실도와 학습 안정성 양쪽에서 유의미하게 개선**된다.

방법론: §5.2.4 로그로 후처리 재실행, **사례별 5회**, **사전학습 가중치 없이 처음부터** 학습.
학습 손실은 5회 평균에 **$2\sigma$ 신뢰구간** 표기.

| 전략 | 결과 |
|---|---|
| **STEGO** | 가장 큰 이득. 산책로를 traversable로 분할하는 **빠른 적응**, **더 빠른 수렴과 더 낮은 학습 손실** |
| **SLIC** | random과 예측 traversability에 **유의미한 차이 없음**. 신뢰구간이 더 낮아 **학습 안정성만 약간 개선** |
| **Random** | 〃 |

> [!important] 논문이 여기서 끌어낸 해석
> random과 SLIC이 비슷한 이유는 **같은 DINO-ViT feature를 쓰기 때문**이고, 이는
> **표현력 대부분이 이미 feature에 인코딩되어 있으며 샘플링과 평균이 예측에 크게 영향을 주지 않음**을 시사한다.

---

## 7. 한계

논문이 §6에서 **직접 밝힌 것 두 가지**:

1. **traversability score 지표로 traction을 쓰는 것**
2. **local terrain map과의 폐루프 통합을 raycasting으로 하는 것**

두 가지가 "WVN의 주요 미해결 과학·공학 질문"이라고 적혀 있다.

본문에서 관찰된 것:

| 한계 | 위치 |
|---|---|
| SLIC segmentation이 의미가 다른 영역을 묶는다 (나무 벽 + 잔디) | §5.2.1, Fig. 6(c) |
| $k_\sigma$·FPR을 완화하면 **시각적으로 유사한 오분류**(진흙 ↔ 길)가 발생, 수동 개입 필요 | §5.2.4, Fig. 9 ⋆ |
| STEGO도 과분할 문제가 있다 (식물) | §5.3.1, Fig. 11(d) |
| 교차로에서는 사람이 heading을 조정해야 했다 | §5.2.4 |
| ablation이 이 논문에 없다 — 선행 논문 [10] 참조 | §3.5.3 |

---

## 📖 용어

이 논문이 처음 쓰거나 특정한 뜻으로 쓰는 것. 분야 표준 용어는 [[용어 사전]].

| 용어·기호 | 이 논문에서의 뜻 | 비고 |
|---|---|---|
| **traction** | 명령 속도 $(\bar v_x, \bar v_y)$ 와 실제 속도 $(v_x, v_y)$ 의 불일치. [38]에서 가져옴 | 이 논문의 **라벨 그 자체** (§3.3.1) |
| **weak segmentation** | 정확한 semantic 분할이 아니라 sub-sampling을 위한 대략적 분할 ($\mathbf{M}$) | SLIC / STEGO / (random은 segment 없음) |
| **segment embedding** $\mathbf{f}_n$ | segment 내부 픽셀들의 dense feature를 평균한 $E$차원 벡터 | Table 1 · §3.2.3. MLP의 입력 |
| **reconstruction loss** $\mathcal{L}_{\text{reco}}$ | $\mathbf{f}_n$ 을 압축했다 복원했을 때의 채널별 MSE. **밟은 segment에서만 계산** | 식 (3). 값 자체가 아니라 $c$ 의 원천 |
| **Supervision Graph** | 로봇 footprint와 $\tau$ 를 담는 **슬라이딩 윈도우** ring buffer | §3.4.1 |
| **Mission Graph** | 학습에 필요한 데이터를 **미션 전체**에 걸쳐 보관 | §3.4.2 |
| **footprint track** | Supervision Graph가 저장하는, $\tau$ 가 딸린 발자국 궤적 | 이미지로 재투영되어 라벨이 됨 |
| **prototype feature vector** | STEGO가 픽셀을 semantic class에 배정할 때 쓰는 기준 벡터 | 원본은 데이터셋 전체에서 오프라인 계산 → WVN은 **이미지마다 KNN으로** |
| **confidence** $c \in [0,1]$ | 복원 손실을 Gaussian에 대조해 얻는 값. **traversability가 아니라 "이 판단을 믿을 수 있는가"** | §3.5.1 |
| $\mathcal{T}$, $\mathcal{T}^C$ | 밟아본 segment 집합과 그 여집합 | §3.5.2 |
| $k_\sigma$ | confidence 스케일 튜닝 파라미터. 기본 2, 완화 시 3 | §3.5.3, §5.2.4 |
| $E$ | feature 차원. **DINO-ViT = 384, STEGO = 90** | Table 1 |
| $d_{\text{sup}}$, $d_{\text{mis}}$ | Supervision / Mission Graph의 노드 간 거리 임계 | §3.4 |

---

## ❓ 질문

**2026-09-09 세션.** 질문 순서가 아니라 **파이프라인 순서**로 묶었다.
답은 전부 논문 원문 근거이고, 절·식·Figure 번호를 함께 적었다.
논문에 서술이 없는 것은 ❓로 표시했다. 전체 색인은 [[질문 로그]].

---

### A. 라벨은 어디서 오는가 — traction

#### Q. traction과 직접 라벨링의 차이가 "플랫폼마다 따로 라벨링할 필요가 없다"는 점인가? 그래서 여러 플랫폼에 보편적으로 쓸 수 있나?

**A.** §3.3.1의 첫 문장이 전제를 뒤집는다.

> *"Defining which terrain is traversable or not **depends on the capabilities of the specific platform**."*

traction은 플랫폼 의존성을 없애는 장치가 아니라, **플랫폼 의존적인 라벨을 자동으로 얻는** 장치다.

| | 보편적인가 |
|---|---|
| 라벨링 **절차** | ✅ 식 (1)의 입력이 기준 속도 명령 $(\bar v_x, \bar v_y)$ 와 로봇 추정 속도 $(v_x, v_y)$ 둘뿐 |
| 라벨 **값** | ❌ 식 (1)이 재는 것은 "이 로봇이 이 지형에서 명령대로 움직였는가" |
| $k$, $v_{\text{thr}}$ | ❌ §3.3.1: *"These values are **calibrated depending on the motion specifications of each platform**"* |

❓ **다른 형태 플랫폼에서의 실험은 논문에 없다.** §5.1의 실험 플랫폼은 ANYmal C, D 두 4족보행뿐이다.
"여러 플랫폼에 보편적으로 쓸 수 있다"는 주장도 논문에 없다.

§2.3은 **기존 자기지도 방법들도 supervision이 플랫폼 의존적**이라고 적는다:

| 논문 | supervision 신호 |
|---|---|
| Wellhausen [6] | 다리형 로봇의 재투영된 foothold |
| Zürn [27] | 바퀴형 로봇이 지형에서 내는 소리 |
| Gasparino [7] | MPC의 receding-horizon 궤적 |

§2.3 마지막 문장이 밝히는 WVN의 차별점은 보편성이 아니다:

> *"we aim for **concurrent supervision signal generation and learning** achieving **online adaptation in the field**."*

#### Q. 모델을 보편적으로 만드는 게 아니라, 기존에 플랫폼별로 하던 라벨링을 속도 값으로 자동화한 것인가?

**A.** 그렇고, class 단계가 사라진다는 차이가 있다.

§2.2가 서술하는 semantic 방식은 두 단계다:

> *"assigning semantic classes to the representations, **with different navigation costs**"*
> *"rely on pre-trained or fine-tuned semantic segmentation models with **pre-defined class labels**"*

traction은 class를 거치지 않고 연속 스칼라 $\tau \in [0,1]$ 을 직접 얻는다 (§3.3.1).

모델 쪽은 층이 나뉜다. §3.5.3이 학습 대상으로 명시하는 것은 $f^{\theta_r}_{\text{reco}}$ 와 $f^{\theta_t}_{\text{trav}}$ 두 MLP뿐이고,
§3.2.2는 *"in contrast to previous works based on **fine-tuned** Convolutional Neural Networks"* 라고 대비시킨다.
⚠️ 논문이 backbone을 "frozen"이라고 명시하지는 않는다.

---

### B. 라벨이 이미지에 붙는 경로 — 두 그래프

#### Q. traction으로 밟은 영역별 점수를 만들고, 그것을 이미지의 segment에 투영해 학습하는가?

**A.** 그렇다. 네 단계로 나뉜다.

**① $\tau$ 는 지형 분석이 아니라 그 순간의 속도 오차다.** 식 (1)(2). Supervision Graph 노드가 시각·로봇 pose·$\tau$ 를 저장하고, 노드는 $d_{\text{sup}}$ 간격으로 놓인다 (§3.4.1).

**② 투영은 과거 이미지로 간다.** §3.4.1:

> *"projecting the footprint track into the **previous** camera viewpoints"*

§3.4.3:

> *"When a new mission node is added, we update the supervision labels $\tau_n$ by **reprojecting the footprint track and corresponding traversability scores $\tau$ onto all the images of the mission nodes within a fixed range**"*

재투영 결과가 보조 이미지 $\mathbf{S}$ 다.

**③ segment 라벨은 평균이다.** §3.4.3:

> *"assign per-segment traversability supervision values $\tau_n$ by **averaging the score over each segment**"*
> *"Segments that do not overlap with the reprojected footprint track are **set to zero** (i.e untraversable)."*

**④ 학습 입력은 이미지가 아니라 $(\mathbf{f}_n, \tau_n)$ 쌍이다** (§3.4.3 마지막, §3.5).

#### Q. mission node에 들어가는 이미지는 한 장인가? 로봇이 일정 거리를 이동하면 갱신되는가?

**A.** 이미지는 한 장이 맞다. §3.4.2:

> *"**Each mission node contains the RGB image $\mathbf{I}$**, the weak segmentation mask $\mathbf{M}$ and per-segment features $\mathbf{f}_n$ with their corresponding traversability supervision $\tau_n$."*

거리 조건은 **갱신** 조건이 아니라 **생성** 조건이다. §3.4.2:

> *"The mission nodes are **added to the graph after feature extraction** if the **distance with respect to the last added node is larger than $d_{\text{mis}}$**."*

시간이 아니라 이동 거리가 기준이고, 판정 순서는 *feature 추출 → 거리 조건 → 저장* 이다.

**갱신되는 것은 과거 노드들의 라벨이다** (§3.4.3, 위 인용).

| 노드 안의 항목 | 생성 시 | 이후 |
|---|---|---|
| $\mathbf{I}$, $\mathbf{M}$, $\mathbf{f}_n$ | 확정 | 고정 |
| $\tau_n$ | 초기값 | **새 노드가 추가될 때마다 재투영으로 갱신** |

❓ 논문에 수치가 없는 것: $N_{\text{sup}}$, $d_{\text{sup}}$, $d_{\text{mis}}$, 재투영 "fixed range".
❓ multi-camera일 때 어느 카메라의 이미지가 mission node가 되는지도 서술이 없다.
§3.2.1은 scheduler가 한 번에 한 카메라만 처리하고, 카메라마다 **"training and inference"** 또는 **"inference-only"** 우선순위가 있다고만 적는다.

---

### C. Feature와 embedding

#### Q. segment embedding이 무엇인가?

**A.** Table 1의 정의:

| 기호 | 정의 |
|---|---|
| $\mathbf{F}$ | *"Feature map with dim. $E \times H \times W$, $E = 90$ or $384$"* |
| $\mathbf{f}_n$ | *"**Per-segment embedding** of dim. $E = 90$ or $384$"* |

생성 경로 (§3.2.2 → §3.2.3):

1. 입력 이미지를 **$224 \times 224$** 로 리사이즈
2. 사전학습 모델로 **픽셀 단위 dense feature** $\mathbf{F}$ 추출 — DINO-ViT는 384차원, STEGO는 90차원
3. weak segmentation으로 **약 100개 segment**로 분할
4. §3.2.3: *"**average the embeddings within each segment**"*

sub-sampling을 하는 이유는 §3.2.2에 명시돼 있다:

> *"The resulting dense features $\mathbf{F}$ are **too large to be stored in GPU memory for online training**."*

예외 두 가지:
- **Random** 전략은 segment가 없다. §3.2.3: *"we have **no segments but the feature locations only**"*
- **Pixel-wise inference**는 dense $\mathbf{F}$ 를 직접 쓴다 (§3.2.4). 학습은 $\mathbf{f}_n$ 으로 한다 (§3.5)

#### Q. embedding은 거리 값이 아니라 segment별 semantic 정보인가?

**A.** 거리 값이 아니다. 입력은 RGB뿐이다. Fig. 2 캡션:

> *"WVN only requires **monocular RGB images**, odometry, and proprioceptive data as input"*

§5.1:

> *"The **LiDAR and depth cameras** available on the robots were **only used for the local terrain mapping module** (Sec. 4.1)."*

semantic이라는 표현에는 논문이 일관되게 **implicitly**를 붙인다.

> 초록: *"which **implicitly** encode semantic information"*
> §3.2.3 (STEGO): *"**class-free** segments, which implicitly encode **semantic affinity**"*

affinity(유사도)로 작동한 결과가 실험에 나타난다:

- §5.2.4 run 2: *"drove the robot to other **visually similar** areas in the park (**mud patches**) requiring manual intervention"* (Fig. 9의 ⋆)
- §5.3.1: STEGO의 식물 과분할에 대해 *"both the features and the segments **'agreed'** on the object being **semantically similar** to the other traversed areas"*

#### Q. "384채널 → 스칼라"가 무슨 뜻인가?

**A.** 채널은 픽셀 하나가 들고 있는 숫자의 개수다. Table 1의 $\mathbf{F}$ 는 $E \times H \times W$ 로, RGB 이미지가 $3 \times H \times W$ 인 것과 같은 형태이고 채널 수가 $E$ 다.

| | 픽셀당 숫자 |
|---|---|
| RGB 이미지 | 3 |
| $\mathbf{F}$ (DINO-ViT) | **384** |
| $\mathbf{F}$ (STEGO) | **90** |

MLP의 입출력 (§3.5.2, §3.5.3):

$$\mathbf{f}_n\ (E\text{차원}) \;\longrightarrow\; \tau_n\ (\text{스칼라})$$

§3.5.2: *"We train a small network $f^{\theta_t}_{\text{trav}}$ with a **single channel output** to regress on the provided segment traversability score $\tau$."*
§3.5.3: `[256, 32]` 2-layer MLP + trav head 1채널 + sigmoid.

논문이 밝히는 효과:

> 초록: *"implicitly encode semantic information that **massively simplifies the learning task**"*
> §1 기여 2: *"We demonstrate that this **eases the overall traversability prediction training process**"*

§5.2.1의 학습 진행 (Fig. 6):

| 학습량 | 상태 |
|---|---|
| 9 step (21초) | *"very poor segmentation"* |
| 800 step (2분) | 흙길을 traversable로, 나무를 untraversable로 구분 |

---

### D. 추론 방식

#### Q. segment-wise와 pixel-wise를 둘 다 적용했는가?

**A.** 둘 다 적용했고, 적용된 자리가 다르다 (§3.2.4에 두 방식 정의).

| | Segment-wise | Pixel-wise |
|---|---|---|
| 출처 | *"the approach **implemented originally** [10]"* | 이 확장판에서 추가 |
| 입력 | $\{\mathbf{f}_n\}$ | dense $\mathbf{F}$ |
| 출력 | segment의 모든 픽셀에 같은 $\tau_n$ | 픽셀마다 |
| 실차 | §5.2.3 (SLIC 사용 명시) | §5.2.5 — *"perform the inference **pixel-wise**"* |

정면 비교는 **오프라인 후처리**로만 했다. §5.3.1:

> *"We ran WVN **in post-processing**, on the recorded logs from the Sec. 5.2.2 and Sec. 5.2.1 experiments."*

⚠️ **정량 결과가 없다.** Fig. 11 캡션:

> *"We **qualitatively** compared segment-wise and pixel-wise inference"*

결과 (§5.3.1):
- *"We observed **consistencies** between the segment-wise and pixel-wise predictions"*
- pixel-wise의 이점: 세밀한 예측, 그리고 *"disregarding the **artifacts that weak-segmentation methods such as SLIC induce**"* — Fig. 11 (b), (c)의 나무 줄기

§5.2.3이 §5.2.5로 직접 연결된다:

> *"This limitation is **addressed in Sec. 5.2.5**, where we deploy our multiple-camera setup and the **novel segmentation and pixel-wise prediction method**."*

학습은 두 경우 모두 segment 단위다 (§3.5).

⚠️ **상호참조 오기**: §3.2.4 끝은 *"Sec. 5.3.2 provides qualitative examples"* 라고 가리키지만, 두 추론 방식의 비교는 **§5.3.1**이다. §5.3.2는 sub-sampling 비교다.

---

### E. Confidence

#### Q. confidence 추정은 어떤 의미이고 어떻게 사용되는가?

**A.** §3.4.3이 만든 편향을 다루는 장치다.

> §3.4.3: *"Segments that do not overlap with the reprojected footprint track are **set to zero**"*
> §3.5: *"we model the **uncertainty about the unvisited (and hence, unlabeled) areas** by using anomaly detection techniques to bootstrap a confidence estimate."*

계산은 식 (3) → (4)(5) → (6)이고, **사용처는 두 곳**이다.

**(a) 손실 가중** — 식 (7,8)에서 안 밟은 항에 $(1-c)$ 를 곱한다.

**(b) threshold 결정** — §3.5.2:

> *"We compute the ROC throughout training by **classifying all segments with confidence under 0.5 as negative** and traversed segments as positive labels. Then, we decide on the traversability threshold only by setting the desired **False Positive Ratio (FPR)**."*

구조는 §3.5.3:

> *"Both networks **share the weights of the hidden layers**. … The **32-channel hidden layer functions as the bottleneck** of the encoder-decoder structure."*

$k_\sigma$ 는 기본 2 (§3.5.3). §5.2.4 run 2는 3으로 완화했고 FPR도 0.3으로 올렸다:

> *"producing a **less conservative behavior** that drove the robot to other visually similar areas in the park (mud patches) **requiring manual intervention** to correct the heading."*

#### Q. 식 (3)의 reconstruction은 정확히 무엇을 어떻게 복원하는가?

**A.** 이미지가 아니라 **embedding 벡터**를 복원한다. §3.5.1:

> *"An encoder-decoder network $f^{\theta_r}_{\text{reco}}$ is trained to **compress the segment feature $\mathbf{f}_n$ into a low dimensional latent space and reconstruct the original input features $\mathbf{f}_n$**."*

입력과 출력이 같은 대상($E$차원 벡터)이고, 손실은 채널 $E$ 에 대한 MSE다 (식 3).
중간에 통과하는 32채널이 bottleneck이다 (§3.5.3).

식 (3)의 조건절이 anomaly detection을 성립시킨다:

> §3.5.1: *"This ensures that the network **only learns to reconstruct the embeddings that are labeled**, in an anomaly detection fashion. Consequently, the trained network reconstructs **known (positive)** feature embeddings … with **small reconstruction loss**; feature embeddings of **unknown (anomalous)** segments the network was never tasked to reconstruct, **such as trees or sky**, induce a **high reconstruction loss**."*

복원된 벡터 자체는 식 (3)의 손실 계산 외에 쓰이지 않는다. 그 손실이 식 (4)(5)(6)을 거쳐 $c$ 가 된다.

#### Q. 학습된 encoder-decoder를 안 밟은 segment에 적용해서, 밟은 곳과 비슷하게 복원되면 "밟을 수 있다"고 판단하는 구조인가?

**A.** confidence는 traversable로 판단하지 않는다. **손실 기여를 제거할 뿐**이다. §3.5.2의 세 경우:

| segment $n$ | 결과 (원문) |
|---|---|
| 밟았음 | $\mathcal{L}_{\text{trav}}(\mathbf{f}_n) = \lVert f^{\theta_t}_{\text{trav}}(\mathbf{f}_n) - \tau_n\rVert^2$ |
| 안 밟았고 **positive와 안 닮음** | *"its confidence will be low $c(\mathbf{f}_n) \to 0$ and $\mathcal{L}_{\text{trav}}(\mathbf{f}_n) \to \lVert f_{\text{trav}}(\mathbf{f}_n) - 0\rVert^2$"* |
| 안 밟았고 **positive와 닮음** | *"its confidence $c(\mathbf{f}_n) \to 1$ and $\mathcal{L}_{\text{trav}}(\mathbf{f}_n) \to 0$, **effectively not contributing to the loss anymore**"* |

§3.5.2가 밝히는 의도:

> *"This **motivates the network to learn the traversability score measured by physically interacting** with the segment as opposed to **being too pessimistic**."*

#### Q. confidence가 낮으면 traversability를 낮게 학습시키고, 높으면 해당 항을 0에 가깝게 해서 조정을 거의 없게 한 것인가?

**A.** 그렇다. 안 밟은 항에 곱해지는 값이 $c$ 가 아니라 $(1-c)$ 다 (식 7,8).
밟은 segment는 $c$ 와 무관하게 $\tau_n$ 으로 학습된다.

기준 분포는 배치마다 다시 계산한다. §3.5.1:

> *"we fit a Gaussian distribution $\mathcal{N}(\mu_{\text{pos}}, \sigma_{\text{pos}})$ over the reconstruction losses **per batch** of the traversed segments"*

식 (9)의 가중치는 $w_{\text{trav}} = 0.03$, $w_{\text{reco}} = 0.5$ 다 (§3.5.3).
❓ 이 배분의 이유는 논문에 설명이 없다.

---

### F. 논문의 위치

#### Q. ablation이 무엇인가? 이 논문에 있는가?

**A.** 논문 내 언급은 §3.5.3의 마지막 한 문장뿐이다.

> *"Please refer to our **previous publication [10]** for **ablation studies of the different parameter and design choices**."*

즉 $k_\sigma$, $w_{\text{trav}}$, $w_{\text{reco}}$, FPR, bottleneck 크기 같은 파라미터·설계 선택의 ablation은 **[10](RSS 2023, `arXiv:2305.08510`)에 있고 이 논문에는 없다.**

이 논문이 수행한 비교는 §5.3의 둘이다:

| 비교 | 위치 | 성격 |
|---|---|---|
| sub-sampling (SLIC / STEGO / Random) | §5.3.2 | **정량** — 5회 반복, 학습 손실 곡선, $2\sigma$ 신뢰구간 |
| 추론 방식 (segment-wise / pixel-wise) | §5.3.1 | **정성** — Fig. 11, 수치 없음 |

❓ confidence 메커니즘 자체(식 7,8에서 $(1-c)$ 를 뺐을 때)의 효과는 이 논문에 수치가 없다.

#### Q. 이 논문의 가장 큰 특징은 온라인 학습이고, sub-sampling과 사전학습 모델은 계산을 쉽게 하기 위한 것인가?

**A.** 논문은 두 축을 나란히 놓는다. 제목:

> *"Fast Traversability Learning via **Pre-Trained Models** and **Online Self-Supervision**"*

초록:

> *"**One of the key ideas** to achieve this is the use of high-dimensional features from pre-trained self-supervised models…
> **Further**, the development of an online scheme for supervision generator enables concurrent training and inference"*

두 요소의 목적은 다르다.

| | 논문이 밝히는 목적 |
|---|---|
| **사전학습 모델** | **학습 과제 단순화** — 초록 *"massively simplifies the learning task"*, §1 기여 2 *"eases the overall traversability prediction training process"* |
| **sub-sampling** | **GPU 메모리** — §3.2.2 *"too large to be stored in GPU memory for online training"* |

§5.3.2에서 STEGO sub-sampling은 메모리 외의 효과도 보였다 — *"faster convergence and lower training loss"*.

그리고 **온라인 자기지도 학습 자체는 [10]에서 이미 한 것**이다. §1:

> *"This article **extends** the system presented by Frey and Mattamala et al. [10], addressing some of the limitations raised in the original formulation and introducing additional features for system integration and field deployment."*

§1이 열거하는 **이 확장판의 기여 5개**:

1. 온라인 **multi-camera** self-supervision 파이프라인
2. 사전학습 backbone에 **STEGO** 추가 (원본은 DINO-ViT)
3. **feature sub-sampling 전략** (원본은 SLIC)
4. 실차 실험 — 온보드 실행, 단일/다중 카메라
5. **오픈소스 ROS 구현** + baseline 가중치
