#!/usr/bin/env python3
"""GPU 메모리 예산을 "추정이 아니라 측정" 으로 구한다.

  # 1부만 (GPU 불필요) — replay buffer 산수
  python /workspace/tools/measure_gpu_budget.py --calc-only

  # 2부 — 실제 env 를 띄워 PhysX 메모리 측정
  cd /workspace/IsaacLab
  ./isaaclab.sh -p /workspace/tools/measure_gpu_budget.py --num-envs 64
  ./isaaclab.sh -p /workspace/tools/measure_gpu_budget.py --num-envs 256
  ./isaaclab.sh -p /workspace/tools/measure_gpu_budget.py --num-envs 1024

  ⚠️ 실행 전에  gpu take 8g --gpu 0  로 할당을 확보할 것.

왜 env 를 많이 안 쓰는가:
  PPO(on-policy)는 샘플을 한 번 쓰고 버려서 4096 env 가 의미 있지만,
  SAC(off-policy)는 replay buffer 에서 재사용하므로 env 를 늘려도 gradient step 이
  같이 늘지 않으면 버퍼만 빨리 채울 뿐이다. 우리 현실 규모는 32~256 이다.
"""

import argparse
import os
import subprocess
import sys

# ══ 1부: replay buffer 산수 (GPU 불필요) ═══════════════════════════════
OBS_DESIGNS = {
    "경로 조건부 (Phase 1, 우리 설계)": dict(
        actor=dict(**{"경로 preview 20점 x (kappa,d)": 40, "차량상태 v_x,v_y,psi_dot,beta,delta": 5,
                      "e_lat,e_psi": 2, "이전 action": 2, "history N=10 x 9dim": 90}),
        critic_extra=dict(**{"mu,C_Sf,C_Sr,m,h": 5, "실제 slip/하중 등": 5}),
    ),
    "+ LiDAR 다운샘플 (Phase 2)": dict(
        actor=dict(**{"경로 preview": 40, "차량상태": 5, "e_lat,e_psi": 2, "이전 action": 2,
                      "history": 90, "LiDAR 108beam x 4stack": 432}),
        critic_extra=dict(**{"동역학 파라미터": 5, "상대차 실제 상태": 6}),
    ),
    "LiDAR raw (참고 — 하면 안 되는 예)": dict(
        actor=dict(**{"LiDAR 1080beam x 4stack": 4320, "나머지": 139}),
        critic_extra=dict(**{"동역학 파라미터": 5}),
    ),
}
ACT_DIM = 2          # (kappa, a_x)
FLOAT_B = 4


def calc(buf_sizes=(500_000, 1_000_000)):
    print("═" * 78)
    print(" 1. SAC replay buffer 크기 — 관측 설계가 전부를 좌우한다")
    print("═" * 78)
    for name, d in OBS_DESIGNS.items():
        a_dim = sum(d["actor"].values())
        c_dim = a_dim + sum(d["critic_extra"].values())
        # obs + next_obs + priv + next_priv + action + reward + done
        per = (a_dim * 2 + c_dim * 2 + ACT_DIM) * FLOAT_B + 4 + 1
        print(f"\n  ▸ {name}")
        for k, v in d["actor"].items():
            print(f"      actor  {k:<38} {v:>6}")
        for k, v in d["critic_extra"].items():
            print(f"      critic {k:<38} {v:>6}")
        print(f"      {'─'*54}")
        print(f"      actor obs {a_dim}dim / critic obs {c_dim}dim / transition {per/1024:.2f} KB")
        for N in buf_sizes:
            gb = per * N / 1024**3
            mark = "✅" if gb < 4 else ("⚠️" if gb < 10 else "❌")
            print(f"      buffer {N:>9,} → {gb:>6.2f} GB  {mark}")
    print("\n  ⚠️ LiDAR 를 raw 로 넣으면 버퍼만으로 수십 GB 다. 다운샘플이 계산량 문제가")
    print("     아니라 메모리 문제이기도 한 이유다.")
    print("  완화책: buffer 를 5e5 로 줄이거나 skrl 옵션으로 CPU 에 저장한다 (느리지만 동작).")


def nvsmi_self():
    """이 프로세스가 실제로 쓰는 GPU 메모리 [MiB]. 공유 GPU 에서도 정확하다."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_gpu_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10).stdout
        me = os.getpid()
        for line in out.strip().splitlines():
            pid, mem = (x.strip() for x in line.split(","))
            if int(pid) == me:
                return int(mem)
    except Exception:                                                  # noqa: BLE001
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calc-only", action="store_true", help="1부만 (GPU 불필요)")
    ap.add_argument("--num-envs", type=int, default=64)
    ap.add_argument("--spacing", type=float, default=3.0)
    ap.add_argument("--steps", type=int, default=200)
    known, rest = ap.parse_known_args()
    if known.calc_only:
        calc()
        return 0
    return None, known, rest


_r = main()
if _r == 0:
    sys.exit(0)
_, ARGS, REST = _r

# ══ 2부: 실제 측정 ═════════════════════════════════════════════════════
from isaaclab.app import AppLauncher                                   # noqa: E402

_p = argparse.ArgumentParser(add_help=False)
AppLauncher.add_app_launcher_args(_p)
_known, _ = _p.parse_known_args(REST)
_known.headless = True
app_launcher = AppLauncher(_known)
simulation_app = app_launcher.app

"""Rest everything follows."""

import torch                                                           # noqa: E402

import isaaclab.sim as sim_utils                                       # noqa: E402
from isaaclab.assets import AssetBaseCfg                               # noqa: E402
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg       # noqa: E402
from isaaclab.sim import SimulationCfg, SimulationContext              # noqa: E402
from isaaclab.utils import configclass                                 # noqa: E402

sys.path.insert(0, "/workspace/tools")
from racecar_cfg import RACECAR_CFG                                    # noqa: E402

DEV = _known.device if getattr(_known, "device", None) else "cuda:0"
BAR = "═" * 78


@configclass
class SceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg())
    light = AssetBaseCfg(prim_path="/World/light",
                         spawn=sim_utils.DomeLightCfg(intensity=2000.0))
    robot = RACECAR_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")


def snap(tag, base=None):
    self_mib = nvsmi_self()
    free, total = torch.cuda.mem_get_info(0)
    used_dev = (total - free) / 1024**2
    d = f"  (기준 대비 +{self_mib - base:,} MiB)" if (base is not None and self_mib) else ""
    print(f"  {tag:<34} 내 프로세스 {str(self_mib)+' MiB' if self_mib else '(측정불가)':>14}"
          f"   장치 전체 {used_dev:,.0f} MiB{d}")
    return self_mib


calc(buf_sizes=(1_000_000,))
print(f"\n{BAR}\n 2. 실측 — num_envs = {ARGS.num_envs}\n{BAR}")

base = snap("앱 기동 직후 (baseline)")
sim = SimulationContext(SimulationCfg(dt=1.0 / 200.0, device=DEV))
after_sim = snap("SimulationContext 생성", base)

scene = InteractiveScene(SceneCfg(num_envs=ARGS.num_envs, env_spacing=ARGS.spacing))
after_scene = snap("Scene 생성 (env 복제)", base)

sim.reset()
after_reset = snap("sim.reset() — PhysX 버퍼 할당", base)

dt = sim.get_physics_dt()
for _ in range(ARGS.steps):
    scene.write_data_to_sim()
    sim.step()
    scene.update(dt)
after_run = snap(f"{ARGS.steps} step 실행 후", base)

print(f"\n{BAR}\n 3. 판정\n{BAR}")
if base and after_run:
    per_env = (after_run - after_sim) / ARGS.num_envs
    print(f"  baseline(Isaac Sim 자체)     {after_sim:>8,} MiB")
    print(f"  env {ARGS.num_envs}개 추가분           {after_run - after_sim:>8,} MiB")
    print(f"  ★ env 1개당                  {per_env:>8.2f} MiB")
    print()
    print(f"  {'num_envs':>10} {'예상 총량':>14}   비고")
    for n in (32, 64, 128, 256, 512, 1024, 4096):
        est = after_sim + per_env * n
        tag = "◀ 현재 측정" if n == ARGS.num_envs else ""
        print(f"  {n:>10} {est/1024:>11.2f} GiB   {tag}")
    print()
    print("  ⚠️ PhysX 는 버퍼를 사전 할당하므로 완전히 선형은 아니다.")
    print("     2~3 개 num_envs 로 돌려 선형성을 확인하라.")
    print("  ⚠️ 여기에 replay buffer(1부)와 영상 녹화(+2~4 GiB)를 더해야 최종 예산이다.")
else:
    print("  ⚠️ nvidia-smi 로 프로세스별 메모리를 못 읽었다. 장치 전체 값으로 추정하라.")

print(f"\n{BAR}")
simulation_app.close()
