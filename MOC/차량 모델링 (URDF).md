---
tags: [MOC, isaac-sim, urdf, tier2]
작성일: 2026-09-14
상태: CAD 원본 검토 완료 — 물리용 URDF 미작성
---

# 차량 모델링 (URDF)

> [!info] 위치
> [[프로젝트 스택]] §11 Tier 2 · [[ML 서버 · Isaac Sim 환경]] §9 에서 *"수 주 분량의 저작 노동"* 이라 한 작업의 첫 단계.

---

## 1. 헤드리스에서 모델링이 가능한가 — 가능하다

> **Isaac Lab 에서 GUI 는 authoring 도구가 아니라 viewer 다.**

| 작업 | 도구 | GUI |
|---|---|---|
| URDF → USD | `scripts/tools/convert_urdf.py --headless` | ❌ |
| 물리·액추에이터 | Python `ArticulationCfg` | ❌ |
| 트랙 구성 | Python + USD API, `convert_mesh.py` | ❌ |

`convert_urdf.py` 실제 코드에서 확인 — **변환이 끝난 뒤에야** GUI 분기가 나온다:
```python
urdf_converter = UrdfConverter(cfg)          # ← 여기서 변환 완료
local_gui = carb_settings_iface.get("/app/window/enabled")
if local_gui or livestream_gui:              # ← headless 면 통째로 건너뜀
    sim_utils.open_stage(...)                #    그냥 보여주기만
```

> [!tip] 코드로 하는 것이 **오히려 낫다**
> GUI 로 설정하면 값이 USD 바이너리에 묻힌다 → git diff 불가, 실험 재현 불가,
> **domain randomization 불가**. 우리는 $\mu, C_{Sf}, C_{Sr}, m, h$ 를 에피소드마다
> 랜덤화해야 하므로 **애초에 코드가 아니면 안 된다.**

**확인 방법 3단계** (전부 headless):

| 확인 대상 | 방법 |
|---|---|
| 구조 (link/joint/mass) | `usdcat` 텍스트 덤프, 또는 `pxr.Usd` 로 순회 출력 |
| 모양 | `--headless --enable_cameras` 로 스크린샷 1장 → `scp` |
| 움직임 | `--headless --enable_cameras --video` → mp4 → `scp` |

⭐ `--headless`(창 안 띄움)와 `--enable_cameras`(그래도 렌더는 함)는 **독립 플래그**다.

> [!note] 관절 축·부호는 그림보다 숫자로 검증하는 게 정확하다
> ```python
> robot.set_joint_position_target(torch.tensor([[0.2, 0.2]]), joint_ids=steer_ids)
> for _ in range(150): sim.step(); robot.update(dt)
> print("yaw 변화:", ..., "횡방향 이동:", robot.data.root_pos_w[:,1])
> # yaw 증가 = 좌회전 (REP-103 정상) / 감소 = axis 부호 반대
> ```
> §8-5-1 에서 정상상태 조향각을 수치로 풀어 시뮬레이터의 거짓을 잡아낸 것과 같은 방식이다.

> [!warning] 로컬 PC 로 우회할 수도 없다
> VivoBook 의 MX250 은 Pascal 세대라 **RT 코어가 없다.** Isaac Sim 은 RTX(Turing+) 요구.
> **헤드리스는 우회로가 아니라 유일한 선택지다.**

---

## 2. ❌ 기존 자산 1 — `f1tenth_gym_ros/config/ego_racecar.xacro`

파일 2번째 줄: `<!-- A simple model of the racecar for rviz -->`

| 필요 | 상태 |
|---|---|
| `<inertial>` | ❌ 없음 |
| `<collision>` | ❌ 없음 (visual 만) |
| 조향 관절 | ⚠️ `base_to_front_*_hinge` 가 **`type="fixed"`** |
| 구동 관절 | ⚠️ 뒷바퀴 **`type="fixed"`** |
| `<axis>` | ❌ 없음 |

**RViz 그림용이다.** 살릴 것은 치수뿐: `wheelbase 0.3302`, `width 0.2032`, `wheel_radius 0.0508`, `laser x=0.275`.

---

## 3. ❌ 기존 자산 2 — `f1tenth_URDF/robot.urdf` (Onshape CAD export)

`.part` 파일의 `documentId`/`partId` → **Onshape 자동 export, 손 안 댐** (`robot name="ubuntu"`).
27 link / 26 joint / 36 STL / **129,952 삼각형** / 6.5 MB.

### ✅ 자산 — 순기구학으로 뽑은 실측 치수

```
wheel_fl [-0.0959, -0.1127, 0.0290]    wheel_rl [ 0.2385, -0.1071, 0.0276]
wheel_fr [-0.0962,  0.1128, 0.0264]    wheel_rr [ 0.2385,  0.1067, 0.0339]

추정 wheelbase = 0.3344 m      추정 track = 0.2255 m
```

| | CAD | `dynamics.yaml` | `vehicle_config.yaml` |
|---|---|---|---|
| wheelbase | **0.3344** | 0.3302 (`lf+lr`) | 0.33 |

> [!question] ⭐ 미해결 — 이 CAD 가 실제로 타는 차의 것인가?
> `0.3344 m` 는 **1/10 F1TENTH 치수**다. 로드맵의 플랫폼은 **1/8 Serpent** 이고, 1/8이면 **0.42~0.45 m** 여야 한다.
> - 실제 차의 CAD → `0.3344` 가 공칭값보다 정확. **§12-1 system identification 의 첫 실측 데이터**
> - 일반 F1TENTH CAD → 치수마저 남의 차 것
>
> **이 답에 따라 $\kappa = \tan\delta/L$ 이하 모든 기구학이 갈린다.**

서스펜션 기하(킹핀 경사 등)는 나중에 롤 센터·캠버 게인 계산에 쓸 수 있다 — 진짜 자산.

### ❌ 치명적 결함

**① 질량이 없다** — 27 link 전부 `mass = 1e-9`, `ixx = iyy = izz = 1e-9` (계산값이 아니라 exporter 기본값).
총 질량 **0.0000 kg** (vs `m = 3.47`).
→ 중력이 주는 힘 `1e-8 N` 대 정상 스케일의 접촉·구속력. 비율 `10⁸` → **솔버 즉시 발산.**

**② `<collision>` 이 하나도 없다** — 27 link → 0개.
→ 접촉 없음 = **타이어 힘 없음** = 바닥을 뚫고 떨어짐.
⭐ 그리고 이건 급소다: Tier 2 로 가는 이유가 **PhysX 접촉 마찰의 $\mu N$ 포화**(§8-5-1)인데,
**접촉이 없으면 Tier 2 의 존재 이유가 사라진다.**

**③ 서스펜션이 서스펜션으로 동작하지 않는다 — 구조적 문제**

```
link_chassis
├─[revolute] under_fl → link_under_arm_fl
│  └─[revolute] nuckle1_fl → link_nuckle_1_fl
│     ├─[revolute] nuckle2_fl → link_nuckle_2_fl
│     │  └─[continuous] wheel_fl → link_wheel_fl
│     └─[revolute] upper2_fl → link_upper_arm_fl    ← 끝. 아무데도 안 붙음
├─[revolute] spring_rl → link_rear_sus_spring_1
│  └─[prismatic] spring_rod_rl → link_rear_sus_rod_1   ← 끝. 아무데도 안 붙음
```

| 부품 | 실제 CAD | 이 URDF |
|---|---|---|
| `link_upper_arm_*` ×4 | 너클 ↔ **섀시** 양단 연결 | 너클에만 붙은 **자유 요동 팔** |
| `spring_*`+`sus_rod_*` ×4 | 섀시 ↔ 로워암 사이 힘 발생 | 섀시에 매달린 **진자. 스프링 힘 0** |

> [!danger] ⭐ exporter 실수가 아니라 **URDF 의 근본 한계**
> 더블 위시본은 **닫힌 기구학 루프**다: `섀시 → 어퍼암 → 너클 → 로워암 → 섀시`.
> **URDF 는 트리만 표현한다.** 그래서 exporter 가 고리를 끊었다.
> → 아무리 고쳐도 **이 URDF 로 더블 위시본은 만들 수 없다.**

**26 DOF 중 쓸모 있는 것은 6개**(휠 4 + 조향 2). **8 DOF 는 흔들리기만** 한다.

**④ 관절 한계가 전부 exporter 기본값**
```
revolute : lower=-3.14159 upper=3.14159 effort=10 velocity=10   → 조향이 ±180° 돈다 (실제 ∓0.4189)
prismatic: lower=-1       upper=1                               → wheelbase 0.33 m 차에서 ±1 m 스트로크
```

**⑤ 좌표계가 REP-103 과 반대**
```
front x = -0.096   rear x = +0.239      (REP-103: +x = 전방)
left  y = -0.113   right y = +0.113     (REP-103: +y = 좌측)
```
z축 기준 **180° 회전**. 안 고치면 **경로를 거꾸로 따라간다.**

### ⚠️ 그 외

| 항목 | 상태 | 영향 |
|---|---|---|
| 휠 4개가 **비평면** | z = 0.0290 / 0.0264 / 0.0276 / 0.0339 (7.5 mm 편차) | 차가 비뚤게 앉음 |
| 메시 규모 | 129,952 삼각형 | collision 으로 쓰면 convex decomposition → 느리고 불안정 |
| `package://assets/...` | `assets` 는 유효한 ROS 패키지 아님 | importer 가 메시를 못 찾음 |
| DOF 26 | 필요한 건 6 | 1024 env 병렬에서 **4.3× 연산 낭비** |

---

## 4. ★ 결정 — 물리용 URDF 를 새로 쓴다

```
치수·기하    ✅ 자산. 보존
시각 메시    ✅ <visual> 재사용 가능
물리 모델    ❌ 사용 불가. 고치는 게 아니라 새로 써야 함
```

**"고쳐 쓰기" 가 안 되는 이유**: ①②④⑤ 를 전부 고쳐도 **③(닫힌 루프)이 남는다.**
서스펜션 구조를 바꿔야 하고, 그러면 남는 게 치수뿐이다.

```
f1tenth_URDF/robot.urdf     ← CAD 원본. 치수·시각화 참조용 보존
assets/*.stl                 ← <visual> 재사용

racecar_physics.urdf (신규)  ← 7 link, 6 DOF
```

```
base_link (섀시)                      mass 3.47, inertia 계산, collision box
├── steer_left   [revolute, z, ±0.4189]
│   └── wheel_fl [continuous, y]      collision cylinder r=0.0508
├── steer_right  [revolute, z, ±0.4189]
│   └── wheel_fr [continuous, y]
├── wheel_rl     [continuous, y]      구동륜
├── wheel_rr     [continuous, y]      구동륜
└── laser        [fixed, x=0.27]
```

| 설계 결정 | 근거 |
|---|---|
| **서스펜션 생략** | 관심사는 §8-5-1 의 **타이어 포화**지 승차감이 아니다. 강체여도 **횡하중 이동은 접촉 법선력 재분배로 그대로 발생**한다 |
| **collision 은 primitive** | box + cylinder. 130k 삼각형 메시 대신 → 빠르고 안정적 |
| **visual 은 STL 재사용** | 영상 녹화 시 보기 좋음. 물리 비용 0 |
| 필요해지면 | 휠당 prismatic strut 추가 (4 DOF). **트리라서 URDF 로 표현 가능** |

**검증 절차**
```bash
sudo apt install liburdfdom-tools
check_urdf racecar_physics.urdf                    # 구조 파싱
./isaaclab.sh -p scripts/tools/convert_urdf.py in.urdf out.usd --headless \
  --joint-target-type none                          # 게인은 USD 에 굳히지 말 것
# → USD 덤프로 joint/mass 확인 → 평지 스폰 → 조향 +0.2 숫자 검증 → 스크린샷
```

---

## 🔗 연결

- [[ML 서버 · Isaac Sim 환경]] · [[프로젝트 스택]] §8-5-1 · §11 · §12-1 · §12-4
- [[Domain Randomization]] · [[질문 로그]]
