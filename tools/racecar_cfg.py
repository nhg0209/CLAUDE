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
WHEEL_VEL_RAD_S = 600.0       # ★ PhysX joint 안전망 (USD: 34377 deg/s). 행동 제약이 아니다.
                              #   휠스핀 시 휠 원주속도가 차체 속도의 4배 이상이 되므로
                              #   차체 속도로 유도하면 휠스핀이 잘린다.
# 실제 속도 상한은 action mapping 에서 건다 (하드웨어 46500 ERPM / 4614 = 10.08 m/s)
SPEED_CAP_RANGE = (4.5, 10.5)  # m/s. domain randomization. critic 의 privileged obs 에 넣는다
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

def make_racecar_cfg(drive_mode: str = "effort", usd_path: str = USD_PATH) -> ArticulationCfg:
    """racecar ArticulationCfg 를 만든다.

    drive_mode
      "effort"    ★ 최종안. policy 가 토크를 직접 지령한다.
                  action 이 a_x 이고 friction ellipse 가 다루는 것도 힘이며,
                  실차 ESC 도 전류(≈토크) 제어가 기본이다.
                  속도 상한이 바뀌어도 action -> 결과 매핑이 불변이라
                  domain randomization 과 궁합이 좋다.
                  -> env 가 set_joint_effort_target 으로 지령한다.
      "velocity"  검증 스크립트용 편의 모드. 목표 휠속도를 추종하는 서보.
                  tau = damping * (w_target - w) 이므로 속도가 오르면 토크가 줄어
                  레이싱에는 맞지 않는다. 차를 편하게 굴릴 때만 쓴다.
    """
    if drive_mode == "effort":
        drive_kw = dict(stiffness=0.0, damping=0.0)
        # 베어링 저항은 여기가 아니라 PhysX joint friction 으로 넣는 것이 맞다.
        # 지금은 0 이다 (실측 전).
    elif drive_mode == "velocity":
        drive_kw = dict(stiffness=0.0, damping=0.02)
    else:
        raise ValueError(f"drive_mode 는 'effort' 또는 'velocity' 여야 한다: {drive_mode}")

    return ArticulationCfg(
        spawn=sim_utils.UsdFileCfg(
            usd_path=usd_path,
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
            "drive": ImplicitActuatorCfg(
                joint_names_expr=[".*_wheel_joint"],
                effort_limit=WHEEL_EFFORT_NM,
                velocity_limit=WHEEL_VEL_RAD_S,      # 수치 안전망. 행동 제약 아님
                armature=WHEEL_ARMATURE,
                **drive_kw,
            ),
            # 조향은 위치 제어 (실차도 서보가 각도를 받는다)
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


# 검증 스크립트 호환용 기본값 (velocity 서보).
# RL env 는 make_racecar_cfg("effort") 를 써야 한다.
RACECAR_CFG = make_racecar_cfg("velocity")
RACECAR_CFG_EFFORT = make_racecar_cfg("effort")
