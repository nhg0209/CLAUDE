---
tags: [moc, interface, sim2real, residual, 규약]
작성일: 2026-09-23
상태: 🔒 확정분 / ⏳ 미확정분 혼재 — **학습 시작 전에 전부 🔒 여야 한다**
갱신: 2026-09-23 (비교군 어댑터 실측 반영)
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

> [!note] 🔒 lookahead 점 정의 — 실측 완료 (2026-09-23)
> 스택 `waypoint_at_distance_before_car` 는 **docstring 이 말하는 "frenet distance" 가 아니다.**
> 코드는 폴리라인 **현 길이의 누적합 + `searchsorted`** 이고 **보간이 없다.**
> `cum[i-1] < d` 이므로 **항상 요청보다 짧은 점**을 돌려준다.
>
> ```
>  v[m/s]  L_d[m]   실제 호길이   부족분[m]   두 점 거리[m]   delta 차이 최대
>    2.00   0.740      0.700      0.0405        0.090        2.45° (조향의 10.2%)
>    3.00   1.210      1.199      0.0108        0.063        1.08°
>    5.00   2.150      2.099      0.0514        0.099        0.56°
>    8.00   3.560      3.498      0.0623        0.108        0.31°
>   10.08   4.538      4.497      0.0406        0.088        0.21°
> ```
>
> **순수 PP 는 보간 방식을 쓴다** — 우리 방법의 부품이지 스택 재현이 아니다.
> 단 ①(Controller.py)과 ②(순수 PP)를 비교할 때 **저속에서 조향의 10%** 가 이 정의 차이로
> 남는다는 것을 리포트에 명시한다.

### 2-2. 종방향 — **오프라인 속도 프로파일** (2026-09-23 실측으로 수정)

> [!danger] 런타임 규칙 $v_{\text{ref}} = \sqrt{a_{\text{lat,max}}/|\kappa_{\text{eff}}|}$ 는 폐기했다
> $\kappa_{\text{eff}}$ 를 "앞 창 안의 최대 $|\kappa|$" 로 잡으면 **코너가 창에 들어오는 순간
> $v_{\text{ref}}$ 가 한 격자(10 cm)에서 뚝 떨어진다** = 계단 함수.
> 실측: 요구 감속이 **79~156 m/s²**. 창 크기를 1~12 m 어떻게 잡아도 못 고친다.

대신 **backward/forward pass** 로 트랙마다 한 번 계산해 `.npz` 에 넣는다.

```
v_allow[i] = min( sqrt(a_lat / |kappa_i|), v_max )
반복 (폐루프라 2바퀴 이상):
  backward  v[i] = min(v[i], sqrt(v[i+1]² + 2·a_lon·ds))     앞 코너를 위해 미리 감속
  forward   v[i] = min(v[i], sqrt(v[i-1]² + 2·a_lon·ds))     가속도 한계
```

| 파라미터 | 값 | 근거 |
|---|---|---|
| $a_{\text{lat}}$ | **3.5 m/s²** | $\mu = 0.357$ 상당. 커리큘럼 주 구간에서 실현 가능 |
| $a_{\text{lon}}$ | **3.5 m/s²** | 같은 값 하나로 통일. 실측 최대 가속은 $\mu{=}1.0$ 에서 4.88 이라 여유 있다 |
| $k_p$ | ⏳ 미정 — $\mu{=}1.0$ 에서 튜닝 후 **고정** | μ 별로 바꾸면 "PP 가 μ 에서 무너진다"가 게인 탓이 된다 |

$$a_{x,\text{base}} = k_p\,\big(v_{\text{profile}}(s) - v\big)$$

```
                 v_ref 최소  v_ref 최대  IQP 대비  요구 감속  요구 가속
ifac_0824_…_3       2.144      8.144     0.746      3.50      3.50
ifac_roboracer      2.058      8.091     0.820      3.50      3.50
```

**요구 감속·가속이 정확히 $a_{\text{lon}}$ 으로 묶인다 — 구성상 보장된다.**
런타임 비용 0(조회), sim/real 동일, 파라미터 2개.

> [!warning] IQP 속도 프로파일과 무엇이 다른가 — 스스로 속이지 말 것
> 형태는 비슷해졌다. 남은 차이는 **입력의 출처**다.
> IQP 는 `ggv.csv`(19행 전부 5.0/4.5, 미측정, **스택 스스로도 지키지 못해** slew limiter 를
> 덧댔다)를 쓴다. 우리는 **우리가 고른 숫자 두 개**를 쓰고 그 값을 문서에 적는다.
> 그리고 residual 이 이 프로파일을 **넘어설 수 있다** — 상한이 아니다.
> 이 구분이 얇다는 것을 인정하고, 리포트에 그대로 쓴다.

> [!note] ⏳ 속도 상한 랜덤화와의 상호작용
> 에피소드마다 $v_{\text{cap}} \sim U(4.5, 10.5)$ 로 바뀐다. 프로파일을 $v_{\text{cap}}$ 로
> 그냥 clip 하면 가속 구간에서 자기일관성이 약간 깨진다.
> 에피소드 시작 때 그 cap 으로 pass 를 다시 돌리는 편이 깨끗하다 (O(N), 422점).

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

## 5. 🔒 비교군 실행 — `Controller.py` 를 스택 수정 없이 (검증 완료)

`tools/test_controller_adapter.py` 로 실제 동작을 확인했다.

### 막는 것은 두 개다 (ROS import 하나가 아니었다)

```
① visualization_msgs         → sys.modules 에 더미 주입 (Marker/MarkerArray, predict_pub=None)
② converter (FrenetConverter) → **생성자 필수 인자**. get_frenet(x,y) 만 쓰인다 (632행)
                                 → FrenetTrack.locate 로 어댑터 10줄
```

### 리셋해야 하는 상태 — solo 주행에서 출력에 영향을 주는 것만 7개

```
del  filtered_heading_error      EMA 필터        (hasattr 지연 초기화)
del  heading_error_integral      PID 적분기       (hasattr, 무한 누적)
del  prev_heading_error          PID D 항        (hasattr)
set  _speed_cmd_prev  = None     slew limiter
set  _aeb_engaged     = False    AEB 래치
set  _aeb_cycles      = 0        AEB 유지 카운터
set  current_steer_command = 0   ★ calc_future_position 이 먹는다 = 조향의 되먹임
```
opponent·START 까지 포함하면 12개 이상 (`_trailing_entry/_handoff`, `i_gap`,
`trailing_command/speed`, `boost_mode`, `cur_state_speed`, `yaw_rate`).

> [!danger] ★ `current_steer_command` 는 내가 앞서 놓친 것이다
> `calc_future_position` 이 **직전 스텝의 조향각**으로 미래 위치를 예측하고,
> 그 미래 위치가 lookahead·횡오차·속도를 전부 결정한다.
> 즉 `Controller.py` 는 **조향이 다음 스텝 관측으로 되먹임되는 닫힌 루프**다.
> "내부 상태 4개" 라고 썼던 것은 틀렸다 — 이건 residual base 로 더더욱 쓸 수 없다는 뜻이다.

### 검증 결과

```
A  import · 생성 · main_loop 1스텝           ✅
B  reset 후 결정성                            max|Δdelta| 0.000e+00, max|Δspeed| 0.000e+00  ✅
   reset 없이 (다른 구간 24스텝으로 오염)       max|Δdelta| 4.6e-3 rad, max|Δspeed| 2.91 m/s  ← 결정로그 #16 의 정량 근거
```

> [!warning] `hasattr` 지연 초기화 패턴에 의존한다
> 스택이 바뀌면 조용히 깨진다. **B 를 회귀 테스트로 상시 실행한다.**
> 정식 `reset()` 을 스택에 넣는 편이 낫다 (실차에서도 state 전환 시 적분기 잔존은 버그).
> 그때 GitHub App 설치가 필요하다. → M6 전까지는 우회로 간다.

### 🔒 보정 레이어 중 **실제로 작동하는 것은 3개뿐**이다 (shipped yaml 기준)

| 레이어 | 판정 | 근거 |
|---|---|---|
| `speed_adjust_lat_err` | ❌ **완전한 no-op** | $\text{curv} = \mathrm{clip}(2(\overline{|\kappa|}/0.8)-2,0,1)$. ifac_0824 는 $\max|\kappa| = 0.761 < 0.8$ 이라 **구조적으로** 0, roboracer 는 0.827 로 넘지만 10점 평균 최대가 0.744 라 역시 0 |
| `acc_scaling` | ❌ 정상주행 no-op | `acc_scaler_for_steer = dec_scaler_for_steer = 1.0`. START 에서만 ×0.7 |
| `speed_steer_scaling` | ✅ $v > 6.5$ | $v{=}8 \to \times 0.786$, $v{=}10.08 \to \times 0.5$ |
| `steer_scaling_for_lat_err` | ✅ 항상 | $2^{\text{lat\_err}}$ — 0.5 m 에서 ×1.41, 1.0 m 에서 ×2.0 |
| `speed_adjust_heading` | ✅ 헤딩오차 10° 초과 | 20°→×0.89, 45°→×0.75, 90°→×0.5 |
| future position 예측 | ✅ 항상 | 단 IMU 분기는 `lambda=gamma=1.0` 이라 **죽은 코드**, 순수 kinematic |
| L1 curvature 단축 | ✅ 항상 | $-c\,\overline{\kappa}\,v^2$ |
| heading PID | ✅ 항상 | KI=0 이라 실질 PD |

> [!tip] 이 표가 ablation 을 대체한다
> "보정 8겹" 이 아니라 **실질 6겹**이고 그중 2개는 죽어 있다.
> 지난 턴에 제안한 L1~L4 사다리를 돌리지 않아도 **어느 레이어가 무엇을 하는지 이미 수치로 안다.**

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
