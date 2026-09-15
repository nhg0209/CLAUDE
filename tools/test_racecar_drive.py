#!/usr/bin/env python3
"""racecar 를 평지에 스폰해 거동을 "숫자로" 검증한다.

  cd /workspace/IsaacLab
  ./isaaclab.sh -p /workspace/tools/test_racecar_drive.py                 # mu=1.0
  ./isaaclab.sh -p /workspace/tools/test_racecar_drive.py --mu 0.3        # 저마찰
  ./isaaclab.sh -p /workspace/tools/test_racecar_drive.py --mu 0.15 --video

★ 왜 숫자로 해야 하나 ────────────────────────────────────────────────────
USD 의 revolute joint 는 축을 X/Y/Z 토큰으로만 쓰고 실제 방향은 localRot 쿼터니언에
들어간다. 즉 **USD 를 읽어서는 "조향 +가 좌회전인지" 알 수 없다.**
굴려보고 yaw 변화를 재는 것이 유일한 확인 방법이다.

검사 항목
  A. 정지 안정성 — 스폰 후 가라앉는 높이, 자세, 잔류 속도
  B. 조향 부호   — +0.2 rad 를 주고 전진했을 때 yaw 가 증가하는가 (REP-103: 좌회전)
  C. 구동 방향   — +휠속도가 +x 전진인가
  D. ★ 마찰 포화 — 같은 토크를 주고 mu 를 바꿨을 때 가속도가 mu 에 막히는가
                   f1tenth_gym 의 선형 타이어에는 없는 현상이다 (프로젝트 스택 §8-5-1)
"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="racecar 거동 숫자 검증")
parser.add_argument("--mu", type=float, default=1.0, help="지면 마찰계수")
parser.add_argument("--steer", type=float, default=0.2, help="조향 시험값 [rad]")
parser.add_argument("--wheel-vel", type=float, default=60.0, help="휠 속도 목표 [rad/s]")
parser.add_argument("--dt", type=float, default=1.0 / 200.0, help="물리 dt")
parser.add_argument("--usd", type=str, default=None, help="USD 경로 (기본: racecar_cfg 의 값)")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import math
import sys

import torch

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation
from isaaclab.sim import SimulationCfg, SimulationContext

sys.path.insert(0, "/workspace/tools")
from racecar_cfg import RACECAR_CFG, WHEEL_RADIUS  # noqa: E402

BAR = "═" * 76
DEV = args_cli.device if getattr(args_cli, "device", None) else "cuda:0"


def yaw_of(q):
    """(w,x,y,z) → yaw [rad]"""
    w, x, y, z = (float(v) for v in q)
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def run():
    sim = SimulationContext(SimulationCfg(dt=args_cli.dt, device=DEV))

    # 지면 — ★ mu 가 여기 들어간다. URDF 에는 존재할 수 없는 값이다.
    ground = sim_utils.GroundPlaneCfg(
        physics_material=sim_utils.RigidBodyMaterialCfg(
            static_friction=args_cli.mu,
            dynamic_friction=args_cli.mu,
            restitution=0.0,
        )
    )
    ground.func("/World/ground", ground)
    light = sim_utils.DomeLightCfg(intensity=2000.0)
    light.func("/World/light", light)

    cfg = RACECAR_CFG.copy()
    cfg.prim_path = "/World/racecar"
    if args_cli.usd:
        cfg.spawn.usd_path = args_cli.usd
    robot = Articulation(cfg)

    sim.reset()
    dt = sim.get_physics_dt()

    steer_ids, steer_names = robot.find_joints("front_.*_hinge_joint")
    wheel_ids, wheel_names = robot.find_joints(".*_wheel_joint")
    print(f"\n{BAR}\n 0. 설정\n{BAR}")
    print(f"  device={DEV}  dt={dt}  mu={args_cli.mu}")
    print(f"  조향 joint {len(steer_ids)}개: {steer_names}")
    print(f"  구동 joint {len(wheel_ids)}개: {wheel_names}   ← 4개여야 한다 (4WD)")
    ok = len(wheel_ids) == 4 and len(steer_ids) == 2
    print("  " + ("✅ 관절 구성 정상" if ok else "❌ 관절 개수가 틀리다"))

    def step(n, steer=None, wvel=None):
        for _ in range(n):
            if steer is not None:
                robot.set_joint_position_target(
                    torch.full((1, len(steer_ids)), steer, device=DEV), joint_ids=steer_ids)
            if wvel is not None:
                robot.set_joint_velocity_target(
                    torch.full((1, len(wheel_ids)), wvel, device=DEV), joint_ids=wheel_ids)
            robot.write_data_to_sim()
            sim.step()
            robot.update(dt)

    # ── A. 정지 안정성 ────────────────────────────────────────────
    print(f"\n{BAR}\n A. 정지 안정성 (1.0초 자유 낙하·정착)\n{BAR}")
    step(int(1.0 / dt), steer=0.0, wvel=0.0)
    p = robot.data.root_pos_w[0]
    q = robot.data.root_quat_w[0]
    v = robot.data.root_lin_vel_w[0]
    roll_pitch = math.degrees(math.asin(max(-1.0, min(1.0, 2 * (float(q[0]) * float(q[2])
                                                                - float(q[3]) * float(q[1]))))))
    print(f"  base_link 높이 z = {float(p[2]):+.5f} m   (스폰 0.005, 바퀴 접지면 z=0)")
    print(f"  잔류 속도       |v| = {float(torch.linalg.norm(v)):.5f} m/s")
    print(f"  pitch           = {roll_pitch:+.3f}°")
    settled = abs(float(p[2])) < 0.02 and float(torch.linalg.norm(v)) < 0.05
    print("  " + ("✅ 안정적으로 접지" if settled else "⚠️ 가라앉거나 튀고 있다 — armature/솔버 확인"))

    # ── B/C. 조향 부호 + 구동 방향 ────────────────────────────────
    print(f"\n{BAR}\n B. 조향 부호 + C. 구동 방향  (steer={args_cli.steer:+.2f} rad, "
          f"wheel={args_cli.wheel_vel:.0f} rad/s, 2.0초)\n{BAR}")
    y0 = yaw_of(robot.data.root_quat_w[0])
    p0 = robot.data.root_pos_w[0].clone()
    step(int(2.0 / dt), steer=args_cli.steer, wvel=args_cli.wheel_vel)
    y1 = yaw_of(robot.data.root_quat_w[0])
    p1 = robot.data.root_pos_w[0]
    dyaw = math.degrees((y1 - y0 + math.pi) % (2 * math.pi) - math.pi)
    dx, dy = float(p1[0] - p0[0]), float(p1[1] - p0[1])
    vb = robot.data.root_lin_vel_b[0]
    print(f"  Δyaw       = {dyaw:+.2f}°")
    print(f"  Δposition  = ({dx:+.3f}, {dy:+.3f}) m")
    print(f"  body 속도  = ({float(vb[0]):+.3f}, {float(vb[1]):+.3f}) m/s   (x=전진, y=좌)")
    print(f"  휠 각속도  = {[round(float(x),1) for x in robot.data.joint_vel[0, wheel_ids]]}")
    print()
    print("  " + ("✅ 조향 +  → yaw 증가 = 좌회전 (REP-103 정상)" if dyaw > 1.0 else
                  "❌ 조향 + 인데 좌회전이 아니다 — axis 부호를 뒤집어야 한다" if dyaw < -1.0 else
                  "⚠️ yaw 변화가 거의 없다 — 안 움직이거나 조향이 안 먹는다"))
    print("  " + ("✅ 구동 +  → +x 전진" if dx > 0.05 else
                  "❌ 구동 + 인데 후진한다 — 휠 axis 부호 확인" if dx < -0.05 else
                  "⚠️ 전진하지 않는다 — 토크 부족 / 접지 실패 / damping 과다"))

    # ── D. ★ 마찰 포화 ───────────────────────────────────────────
    print(f"\n{BAR}\n D. ★ 마찰 포화 — 직진 최대 가속 (mu={args_cli.mu})\n{BAR}")
    robot.write_root_pose_to_sim(torch.tensor([[0., 0., 0.005, 1., 0., 0., 0.]], device=DEV))
    robot.write_root_velocity_to_sim(torch.zeros((1, 6), device=DEV))
    robot.write_joint_state_to_sim(torch.zeros_like(robot.data.joint_pos),
                                   torch.zeros_like(robot.data.joint_vel))
    step(int(0.3 / dt), steer=0.0, wvel=0.0)
    v0 = float(robot.data.root_lin_vel_b[0][0])
    T = 0.5
    step(int(T / dt), steer=0.0, wvel=args_cli.wheel_vel * 2)   # 충분히 큰 목표로 포화시킨다
    v1 = float(robot.data.root_lin_vel_b[0][0])
    a = (v1 - v0) / T
    a_limit = args_cli.mu * 9.81
    wv = [float(x) for x in robot.data.joint_vel[0, wheel_ids]]
    v_wheel = sum(wv) / len(wv) * WHEEL_RADIUS
    slip = (v_wheel - v1) / max(abs(v_wheel), 1e-6)
    print(f"  차체 가속도     a = {a:+.3f} m/s²")
    print(f"  마찰 한계       μg = {a_limit:.3f} m/s²")
    print(f"  비율            a/μg = {a/a_limit if a_limit else 0:.2f}")
    print(f"  휠 원주속도     {v_wheel:.3f} m/s  vs  차체 {v1:.3f} m/s")
    print(f"  종방향 슬립비   {slip:+.3f}   (양수 = 휠이 앞서 돈다 = 휠스핀)")
    print()
    if a <= a_limit * 1.15:
        print("  ✅ 가속도가 μg 를 넘지 않는다 — PhysX 의 |F_t| ≤ μF_n 이 작동한다")
        print("     f1tenth_gym 의 선형 타이어 모델에는 이 한계가 없다 (프로젝트 스택 §8-5-1)")
    else:
        print("  ⚠️ 가속도가 μg 를 넘었다 — 예상 밖이다. dt/솔버 반복수를 확인하라")
    print(f"\n  ★ --mu 를 1.0 / 0.5 / 0.25 로 바꿔 돌려보라.")
    print(f"     a 가 μ 에 비례해 줄어들면 포화가 실증된 것이다.")

    print(f"\n{BAR}")
    return 0


if __name__ == "__main__":
    code = run()
    simulation_app.close()
    sys.exit(code)
