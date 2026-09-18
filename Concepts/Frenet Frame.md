---
tags: [concept, frenet, reference-path, reward, tier2]
작성일: 2026-09-18
출처: 직접 구현·실측 (tools/frenet_gpu.py, tools/test_frenet_gpu.py), unicorn 스택 frenet_converter.py
---

# Frenet Frame

> [!abstract] 한 줄
> **경로를 축으로 삼는 좌표계.** 세계좌표 $(x,y)$ 대신 "경로를 따라 얼마나 갔나 $s$,
> 경로에서 얼마나 벗어났나 $d$" 로 상태를 쓴다.
> RL 에서 이게 중요한 이유는 **progress reward 가 $\Delta s$ 하나로 정의되고,
> 벽 여유가 $d_{\text{left}} - d$ 로 바로 나온다**는 것이다.

> [!info] 위치
> [[프로젝트 스택]] §10-1 관측 공간의 전제. [[TM07 리포트 (2025)]] 의 critic 관측
> $(e_{\text{lat}}, e_\psi, \kappa)$ 가 전부 이 좌표계의 성분이다.
> 구현은 `tools/frenet_gpu.py` — [[트랙 생성 · Frenet 변환]] 에 실측값이 있다.

---

## 1. 정의

reference curve $\mathbf{c}(s)$ 를 **호길이(arc length)** $s$ 로 매개화한다.
$s$ 가 호길이라는 것이 핵심이다 — $|\mathbf{c}'(s)| = 1$ 이라서 $s$ 가 곧 "달린 거리"다.

$$\mathbf{t}(s) = \begin{pmatrix}\cos\psi(s)\\ \sin\psi(s)\end{pmatrix}, \qquad
\mathbf{n}(s) = \begin{pmatrix}-\sin\psi(s)\\ \cos\psi(s)\end{pmatrix}, \qquad
\kappa(s) = \frac{d\psi}{ds}$$

임의의 점은
$$\mathbf{p} = \mathbf{c}(s) + d\,\mathbf{n}(s)$$

- $d > 0$ = 경로의 **왼쪽** (REP-103 의 $z$ 축 회전 방향과 일치)
- $e_\psi = \text{wrap}(\psi_{\text{car}} - \psi(s))$ — 경로 접선과 차체 방향의 차이

> [!note] 왜 $\kappa$ 가 관측에 들어가는가
> $\kappa$ 는 **$\psi$ 의 $s$ 미분**이다. 즉 "앞으로 경로가 얼마나 휘는가"를 위치가 아니라
> **미분 형태**로 준 것이라, 차량이 어디에 있든 같은 의미를 갖는다.
> preview 로 $\kappa(s+\Delta)$ 를 여러 개 주는 것은 경로의 테일러 전개를 주는 셈이다.

## 2. 순변환은 최적화 문제다

$(s,d) \to \mathbf{p}$ 는 대입이지만, 역방향 $\mathbf{p} \to (s,d)$ 는
$$s^* = \arg\min_s \|\mathbf{p} - \mathbf{c}(s)\|$$
라는 **최소화 문제**다. 그래서 세 가지가 조용히 깨진다.

### 2-1. 좌표가 접힌다 (focal point)

$|d| \ge 1/|\kappa|$ 이면 $\mathbf{p}$ 가 곡률 중심을 지나쳐 **여러 $s$ 가 같은 점을 가리킨다.**
안쪽(곡률 중심 쪽) 경계만 위험하고 바깥쪽은 절대 안전하다.

```
판정:   |kappa| × (안쪽 반폭)  <  1
실측:   ifac_0824_mapping_3   0.3078   (R 2.213 m, 안쪽 반폭 0.681 m)
        ifac_roboracer        0.3803   (R 1.871 m, 안쪽 반폭 0.711 m)
```

> [!warning] 최소 곡률반경과 최대 반폭을 곱하면 안 된다
> `1/kappa_max × hw_max` = 1.21 로 1 을 넘지만 **그 둘은 같은 지점이 아니다.**
> 좁은 헤어핀은 반폭이 0.68 m 였다. 접힘은 **점별로** 판정해야 한다.

### 2-2. 전역 최근접점이 엉뚱한 구간을 잡을 수 있다

트랙이 자기 자신에 가까이 지나가면(헤어핀 전후, 8자) 벽에 붙은 차가
**경로상 한참 떨어진 구간**에 더 가까울 수 있다.

점별 안전조건: 오프셋 $|t| \le hw_i$ 인 질의점에 대해
$\text{dist}(\mathbf{p}, i) = |t|$, $\text{dist}(\mathbf{p}, j) \ge D_{ij} - |t|$ 이므로
$$D_{ij} > 2\,hw_i \quad \forall j \text{ (경로상 먼 구간)}$$

```
실측 위반:  ifac_0824_mapping_3  81 / 422     최악 D_far 3.098 vs 2·hw 4.140
           ifac_roboracer      218 / 414     최악 D_far 3.092 vs 2·hw 4.643
```

**그런데 벽에서 5 cm 까지 밀어붙인 4096 점으로 실제 전역 argmin 을 돌렸더니 전부 맞았다**
(최대 $|\Delta s|$ 0.024 m). 위 조건이 pessimistic 하기 때문이다 —
$\text{dist} \ge D - |t|$ 는 두 구간이 정반대로 정렬된 최악만 가정한다.

> [!tip] 그래도 증분(windowed) 탐색을 쓰는 이유는 정확성이 아니라 다른 둘이다
> ① **맵 의존성 제거** — 8자 트랙이 오면 위 조건이 실제로 깨진다
> ② **연산량 17배** — 후보 25 개 vs 422 개. 매 step × 256 env 에서는 이게 더 크다

### 2-3. polyline 이산화 — waypoint 가 아니라 **선분**에 투영한다

가장 가까운 waypoint 를 고르면 오차가 $ds/2$ = **5 cm** 까지 난다 (반폭의 2.5%).
window 안 모든 선분에 $u \in [0,1]$ 로 clamp 투영하고 argmin 을 취하면 진짜 최근접점이 나온다.

볼록한 코너 바깥쪽에서는 선분 $j$ 의 수선발과 선분 $j{+}1$ 의 끝점이 **거리가 같다**(무승부).
어느 쪽을 골라도 $d$ 는 $10^{-7}$ m 수준으로 같고 $s$ 만 최대 ~8 mm 갈린다.
$\Delta s$ 의 합은 telescoping 이라 **한 랩 누적 오차가 0** 이다 (실측 0.0000 m).

## 3. $s$ 는 원 위의 좌표다

폐루프에서 $s$ 는 $[0, L)$ 의 **순환** 좌표다. 뺄셈을 그냥 하면 랩 경계에서 $-L$ 이 튄다.

$$\Delta s = \left(\left(s_{\text{new}} - s_{\text{old}} + \tfrac{L}{2}\right) \bmod L\right) - \tfrac{L}{2}$$

> [!warning] 랩 카운트를 $s$ 의 wrap 감지로 세면 안 된다
> $s \approx 0$ 에서 스폰하면 투영 결과가 $L - \epsilon$ 로 나올 수 있고,
> 첫 step 에 **허수 랩이 하나** 잡힌다. 누적 거리 $\sum \Delta s$ 를 $L$ 로 나누는 쪽이
> 경계에 둔감하다. (실제로 이 버그를 검증 5번에서 랩 카운트 2 로 잡았다)

## 4. 속도 변환에는 $1 - d\kappa$ 가 붙는다

$$\dot s = \frac{v_x \cos e_\psi - v_y \sin e_\psi}{1 - d\,\kappa}, \qquad
\dot d = v_x \sin e_\psi + v_y \cos e_\psi$$

분모가 0 이 되는 조건 $d = 1/\kappa$ 이 §2-1 의 접힘과 **같은 조건**이다.
바깥쪽($d\kappa < 0$)에서는 분모가 1 보다 커진다 — 같은 속도로 달려도 **$s$ 진행이 느리다.**
이것이 "아웃코스를 크게 돌면 거리가 길다"의 수식 표현이다.

> [!note] 우리 progress reward 는 이 식을 쓰지 않는다
> $\Delta s$ 를 **투영으로 직접** 얻으므로 이 인자가 자동으로 반영된다.
> 이 식이 필요한 경우는 순간 속도를 Frenet 성분으로 관측에 넣을 때다.

## 5. Frenet 이 감추는 것

> [!warning] $(s,d)$ 는 **localization 에 전적으로 의존**한다
> 세계좌표 기준 $s$ 를 알아야 관측이 성립한다. [[프로젝트 스택]] §결정로그 2 에서
> trajectory-conditioned 방식이 떠안는 새 실패 모드가 정확히 이것이다.
> 순수 E2E(LiDAR only)는 이 의존이 없다. 대신 미학습 트랙에서 무너진다.

- **$d$ 는 벽까지 거리가 아니다.** 경로까지 거리다. 벽 여유는 $d_{\text{left}} - d$ 로
  따로 계산해야 하고, 그 $d_{\text{left}}$ 는 planner 가 준 값이라 실제 벽과 다를 수 있다.
- **$s$ 는 진행을 재지만 시간을 재지 않는다.** progress reward 는 "빠름"이 아니라
  "많이 감"을 보상한다. 랩타임 최소화와 같아지는 것은 **에피소드 길이가 고정**일 때만이다.

---

## 🔗 연결

- [[트랙 생성 · Frenet 변환]] — 구현·실측·사용법
- [[프로젝트 스택]] §9-3 (스택의 `frenet_conversion`), §10-1 (관측), §10-4 (보상)
- [[기호 사전]] — $s, d, e_\psi, \kappa$
- [[TM07 리포트 (2025)]] — critic 관측이 이 좌표계의 성분
- [[Reward Shaping]] · [[Potential-based Shaping]] — progress reward 가 왜 potential 형태인가
