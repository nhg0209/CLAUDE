#!/usr/bin/env python3
"""Isaac Lab 설치를 "올바른 순서로" 검증한다.

  ./isaaclab.sh -p /workspace/tools/verify_isaaclab.py

★ 왜 이 스크립트가 필요한가 ─────────────────────────────────────────────
`python -c "import isaaclab_assets"` 는 ModuleNotFoundError: No module named 'pxr'
로 실패한다. 이것은 설치 문제가 아니다.

pxr(OpenUSD)는 Isaac Sim 이 번들로 갖고 있고, AppLauncher 가 앱을 띄우면서
sys.path 에 올려준다. 그래서 Isaac Lab 의 모든 스크립트는 이 구조를 갖는다:

    from isaaclab.app import AppLauncher     # 이것만 먼저
    app_launcher = AppLauncher(args_cli)
    simulation_app = app_launcher.app
    \"\"\"Rest everything follows.\"\"\"          # ← 경계
    import isaaclab.sim as sim_utils         # pxr 이 필요한 것들은 여기서부터

⚠️ pip install usd-core 로 pxr 을 채우려 하지 말 것. Isaac Sim 의 번들 USD 와
   충돌해서 전체가 망가진다.
"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Isaac Lab 설치 검증")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True                      # 서버에 디스플레이가 없다
if not getattr(args_cli, "device", None):
    args_cli.device = "cuda:0"                # llvmpipe 로 떨어지는 것을 막는다

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import importlib
import sys

import torch

BAR = "═" * 72


def main() -> int:
    print(f"\n{BAR}\n 1. 런타임\n{BAR}")
    print(f"  python       {sys.version.split()[0]}")
    print(f"  torch        {torch.__version__}")
    print(f"  cuda         {torch.cuda.is_available()}   devices={torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"    [{i}] {torch.cuda.get_device_name(i)}")

    print(f"\n{BAR}\n 2. import (앱 기동 후)\n{BAR}")
    bad = []
    for m in ("pxr", "carb", "omni.kit.app", "isaacsim",
              "isaaclab", "isaaclab.sim", "isaaclab_assets",
              "isaaclab_tasks", "isaaclab_rl", "skrl", "warp"):
        try:
            importlib.import_module(m)
            print(f"  ✅ {m}")
        except Exception as e:                                    # noqa: BLE001
            bad.append(m)
            print(f"  ❌ {m}  ->  {type(e).__name__}: {e}")

    print(f"\n{BAR}\n 3. 실제 물리 스텝 — 여기까지 되면 진짜 동작한다\n{BAR}")
    sim_ok = False
    try:
        import isaaclab.sim as sim_utils
        from isaaclab.sim import SimulationCfg, SimulationContext

        sim = SimulationContext(SimulationCfg(dt=1.0 / 200.0, device=args_cli.device))
        ground = sim_utils.GroundPlaneCfg()
        ground.func("/World/ground", ground)
        light = sim_utils.DomeLightCfg(intensity=2000.0)
        light.func("/World/light", light)
        sim.reset()
        for _ in range(60):
            sim.step()
        print(f"  ✅ GroundPlane 생성 + 60 step 완료  (dt=1/200, device={args_cli.device})")
        print(f"     sim time = {sim.current_time:.4f} s")
        sim_ok = True
    except Exception as e:                                        # noqa: BLE001
        print(f"  ❌ {type(e).__name__}: {e}")

    print(f"\n{BAR}")
    if not bad and sim_ok:
        print("  ★ 전체 통과 — URDF 변환으로 넘어갈 수 있다")
        return 0
    print(f"  실패: {', '.join(bad) if bad else ''}{'' if sim_ok else '  / 물리 스텝'}")
    return 1


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    sys.exit(code)
