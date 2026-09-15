"""racecar ArticulationCfg. ⚠️ AppLauncher 기동 후에만 import 할 것 (pxr 의존).

수치의 출처는 전부 tools/gen_racecar_urdf.py 의 PARAMS 와 변환 후 실측값이다.
"""

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg

USD_PATH = "/workspace/assets/racecar.usd"

# ── 변환 후 USD 에서 실측한 값 ─────────────────────────────────────────
STEER_LIMIT_RAD = 0.4189      # USD 에는 ±24.0 deg 로 들어가 있다
STEER_VEL_RAD_S = 3.2         # USD: physxJoint:maxJointVelocity = 183.35 deg/s
STEER_EFFORT_NM = 5.0         # USD: drive:angular:physics:maxForce = 5.0
WHEEL_EFFORT_NM = 0.629       # 4륜 각각. 합 49.5 N = a_max 의 1.5배
WHEEL_VEL_RAD_S = 196.85      # USD: 11278.67 deg/s
WHEEL_RADIUS = 0.0508
WHEEL_INERTIA = 9.032e-05     # kg m^2. 스핀축(Iyy)

# ★ armature — 솔버가 보는 관절 관성을 인위적으로 키운다.
#   바퀴 관성이 9.03e-5 인데 토크가 0.629 N·m 라 각가속도가 6,965 rad/s^2 이다.
#   dt=1/200 이면 한 스텝에 Δω=34.8 rad/s, dt=1/60 이면 116 rad/s 가 튄다.
#   그대로 두면 접촉이 요동치고 휠스핀·채터링·관통이 난다.
#   실물 관성의 몇 배로 시작해서 "거동이 죽지 않는 최소값"으로 줄여간다.
#   ⚠️ 너무 키우면 휠스핀 자체가 사라져 우리가 보려는 현상이 지워진다.
WHEEL_ARMATURE = 1.0e-3       # ≈ 11 × 실물 관성. M2 튜닝 대상
STEER_ARMATURE = 1.0e-3

RACECAR_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=USD_PATH,
        activate_contact_sensors=True,
        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            disable_gravity=False,
            retain_accelerations=False,
            linear_damping=0.0,
            angular_damping=0.0,
            max_linear_velocity=20.0,
            max_angular_velocity=1000.0,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=False,   # 바퀴·너클이 서로 충돌하면 안 된다
            solver_position_iteration_count=8,
            solver_velocity_iteration_count=2,
        ),
    ),
    # base_link 는 뒤 차축·지면 높이다. z=0 이면 바퀴가 정확히 접지하므로
    # 아주 조금만 띄워서 스폰한다.
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.005),
        rot=(1.0, 0.0, 0.0, 0.0),
        joint_pos={".*": 0.0},
        joint_vel={".*": 0.0},
    ),
    actuators={
        # ★ 4륜 전부. 모터 1개 + 센터 샤프트라 a_x 하나가 균등 분배된다.
        #   stiffness=0, damping>0  =  속도 제어 (velocity target 을 추종)
        "drive": ImplicitActuatorCfg(
            joint_names_expr=[".*_wheel_joint"],
            effort_limit=WHEEL_EFFORT_NM,
            velocity_limit=WHEEL_VEL_RAD_S,
            stiffness=0.0,
            damping=0.02,          # M2 튜닝 대상
            armature=WHEEL_ARMATURE,
        ),
        # 조향은 위치 제어
        "steering": ImplicitActuatorCfg(
            joint_names_expr=["front_.*_hinge_joint"],
            effort_limit=STEER_EFFORT_NM,
            velocity_limit=STEER_VEL_RAD_S,
            stiffness=8.0,         # M2 튜닝 대상
            damping=0.5,
            armature=STEER_ARMATURE,
        ),
    },
)
