---
tags: [concept, isaac-sim, urdf, usd, tier2]
작성일: 2026-09-15
출처: OpenUSD pxr/usd/usdPhysics/schema.usda, IsaacLab v2.3.2 urdf_converter_cfg.py (직접 확인)
---

# URDF 와 USD

> [!abstract] 한 줄
> **URDF 는 저작(authoring) 포맷, USD 는 실행(runtime) 포맷.**
> 변환할 때 **각도 단위 · 회전축 표현 · 관성 텐서** 세 곳에서 값의 형태가 바뀐다.

> [!info] 위치
> [[ML 서버 · Isaac Sim 환경]] · [[차량 모델링 (URDF)]] 의 전제 지식.

---

## 1. 다른 세계에서 왔다

```
URDF  │ ROS (2009~)   │ "로봇 한 대를 기술한다"   │ 목적: TF 트리 + RViz 시각화
USD   │ Pixar (2016~) │ "거대한 장면을 합성한다"  │ 목적: 수백 명이 동시 편집하는 영화 파이프라인
```

로봇 시뮬레이터가 USD 로 옮겨간 이유는 렌더링 품질이 아니라 **composition** 이다 —
4096개 환경 병렬이 USD 의 참조/인스턴싱으로 값싸진다.

---

## 2. URDF 의 한계

단위가 **고정**이다: 미터 / 킬로그램 / **라디안**. 선언조차 하지 않는다.

| 표현 불가 | 결과 |
|---|---|
| ⭐ **닫힌 기구학 루프** | 더블 위시본 불가 — [[차량 모델링 (URDF)]] §3 에서 겪은 그것 |
| 재질(마찰)·센서·복수 로봇 | `<gazebo>` 류 벤더 확장으로 땜질 |
| 레이어·버전·부분 수정 | 파일을 통째로 고쳐야 함 |
| 물리 엔진 파라미터 | 솔버 반복수, contact offset, **마찰** — 전부 없음 |

> [!warning] ⭐ URDF 에 마찰이 없다 — 우리에게 결정적
> `<collision>` 은 *"부딪히는 면이 있다"* 만 말하고 **얼마나 미끄러운지는 말하지 않는다.**
> 우리 연구의 핵심 변수 $\mu$ 는 **URDF 에 존재할 수 없다.** USD/PhysX 쪽 물건이다(§5).

---

## 3. USD 핵심 개념

```
Stage  ── 하나의 장면. 여러 Layer 를 합성한 결과
  ├─ Prim ── 노드. 경로로 지정: /World/racecar/base_link
  │    │      Xform, Mesh, Cube, Cylinder, Scope ... (typed schema)
  │    ├─ Property
  │    │    ├─ Attribute    값       xformOp:translate, physics:mass
  │    │    └─ Relationship 참조     physics:body0
  │    └─ applied API schema  ← ⭐ URDF 와 가장 다른 지점
  └─ Layer ── .usda / .usdc 파일. 겹쳐 쓴다
```

### ⭐ API schema — "무엇인가" 와 "무엇을 할 수 있는가" 의 분리

```
URDF:  <link> 태그 하나에 질량·시각·충돌이 고정 구조로 들어있다

USD :  /base_link 는 Xform 이다              ← 무엇인가 (typed schema)
       + RigidBodyAPI                        ← 강체로 동작한다
       + MassAPI                             ← 질량이 명시되어 있다
       + CollisionAPI                        ← 충돌한다
```

**mixin 이다.** 필요한 능력만 골라 붙인다. 그래서
*"충돌하지만 강체는 아닌 것"*(정적 트랙 벽), *"강체지만 충돌 안 하는 것"* 이 자연스럽다.

> 우리 URDF 의 **조향 너클**이 정확히 후자다 — `RigidBodyAPI` + `MassAPI` 는 붙고 `CollisionAPI` 는 안 붙는다.

### Layer 와 composition — 복잡성이 값하는 이유

강도 순서: **L**ocal > **I**nherits > **V**ariants > **R**eferences > **P**ayload > **S**pecializes

```
racecar.usd   (변환 결과 — 건드리지 않는다)
      ↑ reference
scene.usd     (트랙 + 차량 참조 + 조명)
      ↑ override
런타임        (Python 이 mass, friction 을 에피소드마다 덮어쓴다)  ← ⭐ 도메인 랜덤화
```

**원본을 고치지 않고 위에서 덮어쓸 수 있다** — 이것이 랜덤화를 가능하게 하는 구조다.

### 확장자

| | |
|---|---|
| `.usda` | ASCII. 사람이 읽고 `git diff` 가 된다 |
| `.usdc` | Crate 바이너리. 빠르고 작다 |
| `.usd` | 둘 중 아무거나 (내용으로 판별) |
| `.usdz` | 배포용 zip |

```bash
usdcat racecar.usd            # 바이너리 -> ASCII 덤프
usdcat -o out.usda in.usd     # 변환
```

---

## 4. 물리 스키마 (OpenUSD `schema.usda` 직접 확인)

```
UsdPhysics    표준. 엔진 중립. USD 명세의 일부
PhysxSchema   NVIDIA 확장. 솔버 반복수, contact offset, GPU 설정
```

| 스키마 | 주요 속성 | 단위 |
|---|---|---|
| `RigidBodyAPI` | `physics:velocity`, `physics:kinematicEnabled` | — |
| **`MassAPI`** | `physics:mass`, `physics:density`, `physics:centerOfMass`, **`physics:diagonalInertia`**, `physics:principalAxes` | kg, kg/m³, m |
| `CollisionAPI` | `physics:collisionEnabled` | — |
| `MeshCollisionAPI` | `physics:approximation` ∈ `{none, convexHull, convexDecomposition, …}` | — |
| `ArticulationRootAPI` | 관절 트리의 뿌리 | — |
| `Joint`(기본) | `physics:body0/body1`(Relationship), `physics:localPos0/1`, **`physics:localRot0/1`**(quat) | m |
| **`RevoluteJoint`** | `physics:axis` ∈ **`{"X","Y","Z"}`**, `lowerLimit`, `upperLimit` | ⚠️ **도(degrees)** |
| `PrismaticJoint` | 같음 | 거리 |

Stage 메타데이터: `metersPerUnit`, `kilogramsPerUnit`, `upAxis`. Isaac Sim 은 **Z-up, metersPerUnit=1.0**.

---

## 5. ★ 변환에서 값이 조용히 바뀌는 세 곳

### ① 각도: 라디안 → 도

`schema.usda` 원문: `float physics:lowerLimit = -inf ( doc = """Lower limit. Units: degrees. ...""" )`

```
URDF:  <limit lower="-0.4189" upper="0.4189"/>   [rad]
USD :  physics:lowerLimit = -24.0                 [deg]
```
→ `inspect_usd.py` 에서 **±24.0** 을 기대하는 이유.
`±0.4189` 면 단위 변환 누락, `±180` 이면 한계 유실.

### ② 회전축: 임의 벡터 → X/Y/Z 토큰만

`uniform token physics:axis = "X" ( allowedTokens = ["X","Y","Z"] )`

```
URDF:  axis = (0, 1, 0)              임의 단위벡터
         ↓
USD :  physics:axis      = "X"       ← 정규 축으로 고정
       physics:localRot0 = quat(…)   ← 차이를 관절 프레임 회전으로 흡수
       physics:localRot1 = quat(…)
```

> [!warning] 디버깅에 직결
> USD 를 열면 **모든 관절의 `axis` 가 `"X"`** 로 보일 수 있다. 정상이다.
> 실제 회전 방향은 `localRot0/1` 쿼터니언에 있어 **눈으로 읽어 판단할 수 없다.**
> → *"조향 +0.2 rad 주고 yaw 변화를 숫자로 확인"* 이 필요한 이유. USD 로는 부호를 알 수 없다.

### ③ 관성: 3×3 텐서 → 대각 성분 + 주축 쿼터니언

```
URDF:  <inertia ixx iyy izz ixy ixz iyz/>       대칭 3×3 (독립 6성분)
USD :  physics:diagonalInertia = (Ix, Iy, Iz)   고유값
       physics:principalAxes   = quat(…)        고유벡터 = 주축 회전
```

**고유값 분해를 한다.** 우리 URDF 는 비대각 성분이 0 이라 값이 그대로 보존된다:
```
base_link  ixx=0.010918 iyy=0.026052 izz=0.031820, 비대각=0
  -> diagonalInertia = (0.010918, 0.026052, 0.031820),  principalAxes = (1,0,0,0)
```
일반 CAD 모델은 비대각 성분이 있어 회전이 생긴다.

---

## 6. ★ URDF 에 없고 USD/PhysX 에만 있는 것 — 우리 연구의 심장

```
PhysicsMaterialAPI:  staticFriction, dynamicFriction, restitution, density
```

**$\mu$ 가 여기 있다.** Isaac Lab 에서는 `RigidBodyMaterialCfg(static_friction=…, dynamic_friction=…)`
로 다루고, 에피소드마다 덮어써서 도메인 랜덤화한다.

> [!danger] ⭐ §8-5-1 의 포화가 여기서 살아난다
> ```
> f1tenth_gym:  F_y = mu * C_S * (하중항) * alpha    <- alpha 에 선형. 포화 없음
> PhysX      :  |F_tangent| <= mu * F_normal         <- 부등식. 넘으면 미끄러진다
> ```
> **Tier 2 로 오는 이유는 이 부등식 한 줄이다.** 렌더링이 아니다.

PhysX 전용: 솔버 반복수, `contactOffset`/`restOffset`, articulation 설정 — 전부 URDF 밖.

---

## 7. `UrdfConverterCfg` 옵션 (IsaacLab v2.3.2 소스 확인)

| 옵션 | 기본값 | 우리에게 |
|---|---|---|
| ⭐ **`replace_cylinders_with_capsules`** | `False` | 원기둥이 convex hull 로 각지는 문제의 **공식 해법**. capsule 로 매끄럽게 |
| `collider_type` | `"convex_hull"` | mesh 에만 적용. 우리는 primitive 뿐 (검증 필요) |
| `link_density` | `0.0` | inertial 없는 link 의 기본 밀도. **CAD URDF 였다면 여기서 질량 0 → 폭발** |
| `fix_base` | CLI 기본 off | **차량은 절대 고정하면 안 된다** |
| `merge_fixed_joints` | cfg `True` / CLI `False` | 우리 URDF 에 fixed joint 없음 |
| `self_collision` | `False` | 바퀴·너클 자기충돌 금지. 기본값이 맞다 |
| `joint_drive.target_type` | `"position"` → 우리는 **`"none"`** | 게인을 USD 에 굳히지 않는다 |
| ⭐ `joint_drive.drive_type` | `"force"` / `"acceleration"` | ↓ |

> [!tip] ⭐ `drive_type` — 도메인 랜덤화와 직결되는 결정
> ```
> "force"        토크를 준다.        관성이 바뀌면 응답이 바뀐다
> "acceleration" 관성을 정규화한다.  질량/관성 변화에 불변
> ```
> 우리는 $m$ 을 에피소드마다 랜덤화한다.
> **판단: `force` 가 맞다.** 실차에서 무거워지면 조향이 실제로 느려지고, policy 가 그것까지
> 배워야 sim-to-real 이 성립한다. `acceleration` 은 학습을 쉽게 하는 대신
> **실차에 없는 능력을 가정한다.** (M4 에서 재확인)

`NaturalFrequencyGainsCfg` 도 있다: $P = m f^2$, $D = 2 r f m$ — 관성 정규화된 게인 설정.
조향 서보 게인을 정할 때 유용하다.

---

## 8. 한 문장

```
URDF = 저작 포맷. 사람이 쓴다.   기하와 질량만.
USD  = 실행 포맷. 엔진이 읽는다. 물리·재질·합성·랜덤화까지.
```

```
racecar_physics.urdf ── 한 번 쓴다 ──> racecar.usd ── 매 에피소드 덮어쓴다 ──> 학습
  (기하, 질량, 관성)                   (+ mu, 솔버, 접촉)      (도메인 랜덤화)
```

**변환은 일회성이고, 우리가 실제로 다룰 것은 USD 쪽 물리 파라미터다.**

---

## 🔗 연결

- [[차량 모델링 (URDF)]] · [[ML 서버 · Isaac Sim 환경]] · [[프로젝트 스택]] §8-5-1
- [[Domain Randomization]] · [[SAC v2 (Haarnoja 2018)]]
