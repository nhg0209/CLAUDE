---
tags: [moc, interface, sim2real, residual, 규약]
작성일: 2026-09-23
상태: 🔒 확정분 / ⏳ 미확정분 혼재 — **학습 시작 전에 전부 🔒 여야 한다**
repo: nhg0209/rl-racing
---

# 공유 인터페이스 (sim ↔ real)

> [!danger] 이 문서가 존재하는 이유
> 학습 때 쓴 코드와 실차에서 쓴 코드가 **한 글자라도 다르면 그 차이가 그대로 reality gap** 이다.
> 그리고 **학습을 끝낸 뒤에 발견하면 재학습**이다.
> 여기 적힌 것이 유일한 진실이고, sim 과 real 은 **같은 파일을 import** 한다.

> [!info] 위치
> [[Residual Policy Learning]] 의 구현 규약. [[프로젝트 스택]] §10 · §13(#16~#19) 의 귀결.
> 트랙·좌표 쪽은 [[트랙 생성 · Frenet 변환]] · [[Frenet Frame]].

---

## 0. 코드가 어디에 사는가

| | 무엇 | repo | 시점 |
|---|---|---|---|
| **A** 학습 전용 | Isaac Lab env, reward, randomization, curriculum, SAC 루프, 트랙 생성, Frenet projector | `rl-racing` | 지금 |
| **B** sim·real 공유 | **π_base**, action 변환, **obs 조립**, 정규화 상수, residual bound | `rl-racing/common/` | **지금 고정** |
| **C** 실차 전용 | ROS 2 노드, ONNX/TensorRT, action low-pass, policy fallback | `unicorn-racing-stack` | **M6** |

```
rl-racing  ──import──▶  (없음)              학습이 ROS 에 의존하지 않는다
스택       ──import──▶  rl_racing.common    M6 에서만. pip install -e
```

의존은 **실차 → 학습** 한 방향뿐이다.

---

## 1. 🔒 차량 상수 — 단일 출처

| 기호 | 값 | 출처 | 비고 |
|---|---|---|---|
| $L$ wheelbase | **0.33 m** | `vehicle_config.yaml: wheelbase` | ⚠️ URDF 는 $l_f+l_r = 0.3302$. **0.33 으로 통일**하고 URDF 를 맞춘다 |
| $\delta_{\max}$ | **0.4189 rad** (24°) | URDF / `racecar_cfg.py` | |
| $\kappa_{\max}$ | **1.349 1/m** | $\tan(\delta_{\max})/L$ | residual bound 의 기준 |
| $v_{\max}$ | **10.078 m/s** | `speed_max 46500 / speed_to_erpm_gain 4614` | ERPM 2배 상향 반영값 |
| $v_{\min}$ | 0.0 | | 후진 없음 |
| 속도 상한 랜덤화 | $U(4.5,\;10.5)$ | 결정: domain randomization | critic privileged obs 에 포함 |

> [!warning] wheelbase 0.33 vs 0.3302
> 스택은 0.33, 우리 URDF 는 $l_f + l_r = 0.15875 + 0.17145 = 0.3302$ 다.
> 0.2 mm 지만 **두 벌의 값이 존재하는 것 자체가 위험**하다.
> $\delta = \arctan(L\kappa)$ 가 sim 과 real 에서 달라진다.
> → `rl_racing/common/vehicle.py` 하나에서 읽고, URDF 생성기도 거기서 읽게 한다.

---

## 2. 🔒 π_base — 순수 Pure Pursuit + 마찰원 속도

### 2-1. 횡방향

$$L_d = \mathrm{clip}\big(m_{l1}\,v + q_{l1},\; t_{\min},\; t_{\max}\big), \qquad
\delta = \arctan\!\frac{2L\sin\eta}{L_d}, \qquad
\kappa_{\text{base}} = \frac{\tan\delta}{L}$$

$\eta$ 는 차량 헤딩과 lookahead 점 방향의 사잇각. **스택과 같은 정의를 쓴다**:

```
eta = arcsin( (−sin ψ, cos ψ) · L1벡터 / |L1벡터| )       Controller.py:391
```

| 파라미터 | 값 | 출처 |
|---|---|---|
| $m_{l1}$ | 0.47 | `controller.yaml` |
| $q_{l1}$ | −0.2 | `controller.yaml` |
| $t_{\min}$ | 0.7 m | `controller.yaml: t_clip_min` |
| $t_{\max}$ | 8.0 m | `controller.yaml: t_clip_max` |

```
v [m/s]   L_d [m]
 1.0       0.70   ← 하한이 걸린다 (v < 1.91 m/s 에서 항상)
 3.0       1.21
 5.0       2.15
 8.0       3.56
10.08      4.54
→ 상한 8.0 은 v = 17.4 m/s 부터 걸리므로 **우리 차에서는 절대 걸리지 않는다**
```

**끄는 것** (= 순수 PP 로 만드는 부분): future position 예측, curvature 단축
($-c\,\bar\kappa v^2$), lat_err 하한 확장, heading PID, steer scaling 3종.

> [!note] lookahead 점을 어떻게 찾는가 — 정의를 맞춰야 한다
> 스택 `waypoint_at_distance_before_car` 는 **경로 호길이 기준**이다.
> 우리도 `FrenetTrack` 에서 $s + L_d$ 로 뽑는다 (유클리드 거리 기준이 아니다).
> 두 정의는 곡률 구간에서 최대 수 cm 다르다. **실측해서 문서에 남길 것.** ⏳

### 2-2. 종방향

$$v_{\text{ref}} = \mathrm{clip}\!\left(\sqrt{\frac{a_{\text{lat,max}}}{|\kappa_{\text{eff}}|}},\; v_{\min},\; v_{\text{cap}}\right),
\qquad a_{x,\text{base}} = k_p\,(v_{\text{ref}} - v)$$

| 파라미터 | 값 | 근거 |
|---|---|---|
| $a_{\text{lat,max}}$ | **3.5 m/s²** | $\mu = 3.5/9.81 = 0.357$. 커리큘럼 주 구간($\mu \ge 0.42$)에서 base 가 실현 가능, 꼬리에서만 residual 이 감속을 배운다 |
| $v_{\text{cap}}$ | 에피소드의 랜덤화된 속도 상한 | |
| $k_p$ | ⏳ **미정** — $\mu{=}1.0$ 에서 튜닝 후 **고정** | μ 별로 바꾸면 "PP 가 μ 에서 무너진다"가 게인 탓이 된다 |
| $\kappa_{\text{eff}}$ | ⏳ **미정** — preview 앞 4 m 구간의 $\max|\kappa|$ 로 시작 | 스택은 `mean(|kappa[i+10:i+20]|)`. 제동거리를 반영하려면 창을 속도에 따라 늘려야 할 수도 |

```
|kappa|   R [m]    v_ref [m/s]
 0.05     20.0       8.37
 0.20      5.0       4.18
 0.50      2.0       2.65
 0.761     1.31      2.14      ← ifac_0824_mapping_3 최소 곡률반경
 → 0        ∞       10.08 로 clip
```

---

## 3. 🔒 Action 규약

$$\kappa = \kappa_{\text{base}} + \Delta\kappa_\theta, \qquad
a_x = a_{x,\text{base}} + \Delta a_{x,\theta}, \qquad
\delta = \arctan(L\,\kappa)$$

| | 단위 | 범위 |
|---|---|---|
| policy 출력 | — | $\tanh \Rightarrow [-1, 1]^2$ |
| $\Delta\kappa_\theta$ | 1/m | $\pm 0.40$ = $\kappa_{\max}$ 의 30% ⏳ 조정 대상 |
| $\Delta a_{x,\theta}$ | m/s² | $\pm 3.0$ ⏳ 조정 대상 |
| 최종 $\delta$ | rad | $\pm 0.4189$ 로 clip |

> [!important] bound 운용
> **넓게 시작 → 로그 보고 조인다.** `|Δ|/bound` 히스토그램과 **"bound 에 붙어있는 비율"** 을 필수 로깅.
> 상한에 계속 붙어 있으면 넓히고, 20% 이내만 쓰면 조인다. → [[Residual Policy Learning]] 구현 ②

> [!warning] ⏳ action low-pass 를 어디에 거는가 — **미정, 학습 전 확정 필수**
> `policy 출력`에 거는 것과 `base + residual` 합에 거는 것은 **다른 시스템**이다.
> 실차에서만 걸고 sim 에서 안 걸면 전이가 깨진다. 제어 주기 측정 후 결정.

---

## 4. ⏳ Observation 규약 — **미확정. 최우선 과제**

> [!danger] 여기가 가장 위험하다
> 순서 하나, 정규화 상수 하나가 어긋나면 실차 policy 는 **다른 함수**를 계산한다.
> 코드가 아니라 **선언적 스펙**(이름·순서·차원·정규화)을 먼저 고정하고, sim/real 이 그걸 읽게 한다.

### 확정된 것 🔒

| 항목 | 값 |
|---|---|
| 경로 표현 | [[Frenet Frame]] — $(s, d, e_\psi)$, **$d>0$ = 왼쪽** |
| preview | 40점 × 0.5 m, **차량 좌표계** (x 전방 +, y 좌측 +) |
| preview 내용 | $x, y, \Delta\psi, \kappa, d_{\text{left}}, d_{\text{right}}$ |
| `a_base` 포함 | $(\kappa_{\text{base}},\, a_{x,\text{base}})$ 2차원 — 무엇을 보정하는지 알아야 한다 |
| 비대칭 | actor 에 $\mu$ 없음 / critic 에 $\mu$, $v_{\text{cap}}$, 실제 벽거리 포함 |

### 미확정 ⏳

- ego dynamics history 길이 (노트 권고 10~20 step) 와 **간격** ← 제어 주기 측정에 의존
- LiDAR 포함 여부와 다운샘플 수 (solo 주행에는 불필요할 수 있다)
- 정규화 상수 (running mean/std vs 고정 스케일) — **실차에서 재현 가능해야 하므로 고정 스케일 권장**
- preview 40×6 = 240 차원을 그대로 넣을지 압축할지

---

## 5. 🔒 비교군 실행 — `Controller.py` 를 스택 수정 없이

```
ROS 의존:  visualization_msgs 단 하나, 1곳 (346~364행)
rclpy:     0회
publish:   predict_pub=None 이면 호출되지 않음
```

```
① sys.modules 에 visualization_msgs.msg 스텁 주입 (더미 Marker/MarkerArray)
② 에피소드마다 내부 상태 리셋
     del filtered_heading_error / heading_error_integral / prev_heading_error
     _speed_cmd_prev = None
```

> [!warning] `hasattr` 지연 초기화 패턴에 의존한다
> 회귀 테스트로 고정: **리셋 후 같은 입력 → 항상 같은 (δ, speed)**.
> 정식 `reset()` 을 스택에 넣는 편이 낫고 (실차에서도 state 전환 시 적분기 잔존은 버그),
> 그때 GitHub App 설치가 필요하다. → M6 전까지는 우회로 간다.

---

## 6. 실험 3종

| | 대상 | 목적 |
|---|---|---|
| ① | `Controller.py` 단독 (보정 8겹 전부) | **실전 기준선** |
| ② | 순수 PP 단독 (π_base) | base 가 어디서 무너지는가 |
| ③ | 순수 PP + residual | 우리 방법 |

$\mu \in \{1.0,\,0.7,\,0.5,\,0.42,\,0.35,\,0.25\}$ × 3랩. 기록: 완주 여부, 랩타임, $\max|d|$,
벽 접촉 수, 최대 슬립비, **residual 크기 분포**.

②가 빠지면 ③의 승리가 residual 덕인지 PP 가 원래 나았던 건지 갈리지 않는다.

---

## 🔗 연결

- [[Residual Policy Learning]] — 개념과 실패 모드
- [[트랙 생성 · Frenet 변환]] · [[Frenet Frame]] — 경로 쪽 규약
- [[프로젝트 스택]] §10(목표 아키텍처) · §13 #16~#19(이 문서를 낳은 결정)
- [[ML 서버 · Isaac Sim 환경]] — 학습 환경
