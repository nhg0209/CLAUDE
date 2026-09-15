#!/usr/bin/env python3
"""변환된 USD 를 물리 관점에서 검사한다. GUI 없이 구조를 확인하는 수단.

  cd /workspace/IsaacLab
  ./isaaclab.sh -p /workspace/tools/inspect_usd.py /workspace/assets/racecar.usd

★ AppLauncher 를 먼저 띄우는 이유 ────────────────────────────────────────
pxr(OpenUSD)은 Isaac Sim 번들이고, AppLauncher 가 앱을 기동하면서 sys.path 에
올려준다. 맨 위에서 `from pxr import ...` 하면 ModuleNotFoundError 가 난다.
Isaac Lab 의 모든 스크립트가 AppLauncher 뒤에 "Rest everything follows" 경계를
두는 이유가 이것이다.  ⚠️ pip install usd-core 로 채우지 말 것 — 번들 USD 와 충돌한다.

검사 항목:
  1. Stage 메타데이터 — upAxis, metersPerUnit, kilogramsPerUnit
  2. Articulation root — 정확히 1개여야 한다
  3. 질량 / CoG / diagonalInertia — URDF 값이 살아남았는가
  4. Collider — PhysX 에 네이티브 원기둥이 없어 convexHull 로 바뀌면 바퀴가 각진다
  5. Joint — 축 토큰, 한계(★ USD 는 도 단위), localRot(임의 축이 여기 흡수된다)
  6. Drive — --joint-target-type none 이면 없어야 한다
"""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="USD 물리 구조 검사")
parser.add_argument("usd_path", nargs="?", default="/workspace/assets/racecar.usd",
                    help="검사할 USD 경로")
parser.add_argument("--expect-mass", type=float, default=3.47, help="기대 총 질량 [kg]")
parser.add_argument("--expect-steer-deg", type=float, default=24.0, help="기대 조향 한계 [deg]")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import sys

from pxr import Usd, UsdGeom, UsdPhysics

BAR = "═" * 78


def fmt3(v, n=5):
    return "-" if v is None else "(" + ", ".join(f"{x:.{n}f}" for x in v) + ")"


def authored(attr):
    """명시적으로 기록된 값만 반환한다. 스키마 기본값은 None."""
    return attr.Get() if attr and attr.HasAuthoredValue() else None


def main() -> int:
    stage = Usd.Stage.Open(args_cli.usd_path)
    if stage is None:
        print(f"❌ 열 수 없음: {args_cli.usd_path}")
        return 1

    warn = []

    print(f"\n{BAR}\n 1. Stage — {args_cli.usd_path}\n{BAR}")
    print(f"  upAxis            {UsdGeom.GetStageUpAxis(stage)}       (Isaac Sim 은 Z)")
    print(f"  metersPerUnit     {UsdGeom.GetStageMetersPerUnit(stage)}")
    try:
        print(f"  kilogramsPerUnit  {UsdPhysics.GetStageKilogramsPerUnit(stage)}")
    except Exception:                                                  # noqa: BLE001
        pass
    print(f"  defaultPrim       {stage.GetDefaultPrim().GetPath() if stage.GetDefaultPrim() else '-'}")

    roots, bodies, colliders, joints, drives = [], [], [], [], []
    for p in stage.Traverse():
        applied = list(p.GetAppliedSchemas())
        if p.HasAPI(UsdPhysics.ArticulationRootAPI):
            roots.append(p)
        if p.HasAPI(UsdPhysics.RigidBodyAPI):
            bodies.append(p)
        if p.HasAPI(UsdPhysics.CollisionAPI):
            colliders.append(p)
        if p.IsA(UsdPhysics.Joint):
            joints.append(p)
        if any(s.startswith("PhysicsDriveAPI") for s in applied):
            drives.append((p, [s for s in applied if s.startswith("PhysicsDriveAPI")]))

    print(f"\n{BAR}\n 2. Articulation root\n{BAR}")
    for r in roots:
        print(f"  {r.GetPath()}")
    if len(roots) != 1:
        warn.append(f"articulation root 가 {len(roots)}개 (1개여야 한다)")
        print(f"  ⚠️ {len(roots)}개 — 1개여야 한다")
    else:
        print("  ✅ 1개")

    print(f"\n{BAR}\n 3. Rigid body — 질량 / CoG / 관성\n{BAR}")
    total = 0.0
    for b in bodies:
        name = b.GetName()
        m = cog = di = pa = None
        if b.HasAPI(UsdPhysics.MassAPI):
            api = UsdPhysics.MassAPI(b)
            m = authored(api.GetMassAttr())
            cog = authored(api.GetCenterOfMassAttr())
            di = authored(api.GetDiagonalInertiaAttr())
            pa = authored(api.GetPrincipalAxesAttr())
        if m:
            total += m
        print(f"  {name}")
        print(f"      mass  {m if m is not None else '(auto — 밀도로 계산됨)'}")
        print(f"      CoG   {fmt3(cog)}")
        print(f"      Idiag {fmt3(di, 8)}")
        if pa is not None:
            print(f"      주축   {pa}   (항등=(1,0,0,0) 이면 URDF 비대각 성분이 0이었다)")
    d = abs(total - args_cli.expect_mass)
    ok = d < 1e-3
    print(f"  {'─'*74}")
    print(f"  총 질량 {total:.4f} kg  /  기대 {args_cli.expect_mass:.4f}  차이 {d:.2e}  "
          f"{'✅' if ok else '❌ URDF inertial 이 유실됐다'}")
    if not ok:
        warn.append(f"총 질량 {total:.4f} != {args_cli.expect_mass}")

    print(f"\n{BAR}\n 4. ★ Collider — 바퀴가 원기둥으로 남았는가\n{BAR}")
    print(f"  {'prim':<30}{'USD type':>14}{'approximation':>20}")
    for c in colliders:
        t = str(c.GetTypeName())
        appr = "-"
        if c.HasAPI(UsdPhysics.MeshCollisionAPI):
            appr = str(authored(UsdPhysics.MeshCollisionAPI(c).GetApproximationAttr()) or "(기본)")
        tag = ""
        if "wheel" in str(c.GetPath()).lower():
            bad = (t == "Mesh") or ("onvex" in appr)
            tag = "  ← 바퀴 " + ("⚠️ 각진다" if bad else "✅")
            if bad:
                warn.append(f"{c.GetName()} collider 가 {t}/{appr} — 굴릴 때 덜컹거린다")
        print(f"  {c.GetName():<30}{t:>14}{appr:>20}{tag}")
    if not colliders:
        warn.append("collider 가 하나도 없다")
        print("  ⚠️ 없음 — 접촉이 발생하지 않는다")

    print(f"\n{BAR}\n 5. Joint  (★ USD 의 revolute 한계는 '도' 단위)\n{BAR}")
    for j in joints:
        jt = str(j.GetTypeName())
        base = UsdPhysics.Joint(j)
        b0 = base.GetBody0Rel().GetTargets()
        b1 = base.GetBody1Rel().GetTargets()
        print(f"  {j.GetName():<28} {jt}")
        print(f"      body0 → {b0[0].name if b0 else '-'}    body1 → {b1[0].name if b1 else '-'}")
        if j.IsA(UsdPhysics.RevoluteJoint):
            rj = UsdPhysics.RevoluteJoint(j)
            ax = rj.GetAxisAttr().Get()
            lo, up = rj.GetLowerLimitAttr().Get(), rj.GetUpperLimitAttr().Get()
            lim = "제한 없음 (continuous)" if lo in (None, float("-inf")) else f"[{lo:.2f}, {up:.2f}] deg"
            print(f"      axis={ax}   limit={lim}")
            if lo not in (None, float("-inf")):
                e = args_cli.expect_steer_deg
                if abs(abs(lo) - e) < 0.5:
                    print(f"      ✅ ±{e}° — 라디안→도 변환 정상")
                elif abs(abs(lo) - 0.4189) < 0.01:
                    warn.append(f"{j.GetName()}: 한계가 라디안 그대로다 (단위 변환 누락)")
                    print("      ❌ 라디안 값이 그대로 들어왔다")
                elif abs(abs(lo) - 180.0) < 1.0:
                    warn.append(f"{j.GetName()}: 한계가 ±180° — URDF limit 유실")
                    print("      ❌ ±180° — 한계가 유실됐다")
        lr0 = authored(base.GetLocalRot0Attr())
        if lr0 is not None:
            print(f"      localRot0={lr0}   ← URDF 의 임의 축이 여기 흡수된다")
    print(f"  → {len(joints)}개")

    print(f"\n{BAR}\n 6. Drive  (--joint-target-type none 이면 비어야 한다)\n{BAR}")
    if drives:
        for p, which in drives:
            print(f"  ⚠️ {p.GetName()}  {which}")
        warn.append("drive 가 USD 에 굳었다 — ActuatorCfg 로 제어하려면 재변환")
    else:
        print("  ✅ 없음. 액추에이터는 Python ActuatorCfg 에서 정의한다")

    print(f"\n{BAR}")
    if warn:
        print("  ⚠️ 확인 필요:")
        for w in warn:
            print(f"     · {w}")
        return 1
    print("  ★ 전체 통과 — ArticulationCfg 작성으로 넘어갈 수 있다")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    sys.exit(code)
