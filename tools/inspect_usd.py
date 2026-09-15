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
parser.add_argument("--tree", action="store_true", help="모든 prim 의 타입과 applied schema 를 덤프")
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
    # payload 가 있으면 기본 Open 이 안 열 수 있다. 명시적으로 전부 로드한다.
    stage = Usd.Stage.Open(args_cli.usd_path, Usd.Stage.LoadAll)
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
    print("  합성된 레이어 (변환기가 다중 파일 USD 를 만든다):")
    for lyr in stage.GetUsedLayers():
        ident = lyr.identifier
        print(f"    · {ident.split('/')[-1]:<36} {ident}")

    roots, bodies, colliders, joints, drives = [], [], [], [], []
    # ★ 기본 predicate 는 instance proxy 안으로 내려가지 않는다. URDF 변환기는
    #   기하 prim 을 instanceable 로 만들 수 있어서, 그러면 collider 가 안 보인다.
    pred = Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    all_prims = list(stage.Traverse(pred))
    if args_cli.tree:
        print(f"\n{BAR}\n 1b. prim 트리 ({len(all_prims)}개)\n{BAR}")
        for p in all_prims:
            api = [s for s in p.GetAppliedSchemas()]
            inst = " [instance proxy]" if p.IsInstanceProxy() else ""
            print(f"  {str(p.GetPath()):<52}{str(p.GetTypeName()):>16}{inst}")
            if api:
                print(f"        + {', '.join(api)}")
    for p in all_prims:
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
        warn.append("collider 가 하나도 없다 — 접촉이 발생하지 않는다")
        print("  ⚠️ 없음 — 접촉이 발생하지 않는다")
        print("     --tree 로 prim 트리를 덤프해서 기하가 어디 있는지 확인하라.")
        print("     collisions/ 스코프가 instance proxy 안에 있거나, 변환기가")
        print("     CollisionAPI 를 붙이지 않았을 수 있다.")

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
        # ★ 속도/힘 한계 — 스키마 이름을 추측하지 않고 실제 속성을 훑는다.
        #   URDF 의 <limit velocity> 는 rad/s 인데 USD 의 angular 계열은 degree 계열이라
        #   변환기가 단위를 바꿨는지 여기서 실측해야 한다.
        extra = []
        for at in j.GetAttributes():
            n = at.GetName()
            if at.HasAuthoredValue() and any(k in n.lower() for k in
                                             ("maxjointvelocity", "maxforce", "velocity",
                                              "armature", "jointfriction", "maxlinear",
                                              "maxangular")):
                extra.append(f"{n}={at.Get()}")
        if extra:
            print(f"      한계/물성: {'  '.join(extra)}")
    print(f"  → {len(joints)}개")
    print("  ⚠️ 휠 joint 의 최대 속도를 확인하라. URDF 는 196.85 rad/s 를 줬다.")
    print("     USD 쪽에 196.85 가 '도/초' 로 들어갔다면 실제로는 3.4 rad/s = 0.17 m/s 이고")
    print("     차가 사실상 움직이지 않는다. 값이 11279 근처면 도/초로 정상 변환된 것이다.")

    print(f"\n{BAR}\n 6. Drive  (★ target_type='none' 은 API 를 없애지 않고 게인을 0 으로 만든다)\n{BAR}")
    print("  Isaac Lab 의 ImplicitActuator 는 DriveAPI 가 '존재해야' 런타임에 게인을 써넣는다.")
    print("  따라서 API 가 있는 것은 정상이고, 확인할 것은 stiffness/damping 이 0 인지다.\n")
    if not drives:
        warn.append("DriveAPI 가 없다 — ImplicitActuator 가 게인을 써넣을 대상이 없다")
        print("  ⚠️ 없음")
    for p, which in drives:
        for s in which:
            inst = s.split(":", 1)[1] if ":" in s else "angular"
            api = UsdPhysics.DriveAPI(p, inst)
            _st, _dm = authored(api.GetStiffnessAttr()), authored(api.GetDampingAttr())
            st = 0.0 if _st is None else _st
            dm = 0.0 if _dm is None else _dm
            ty = authored(api.GetTypeAttr()) or "(기본)"
            mf = authored(api.GetMaxForceAttr())
            zero = abs(st) < 1e-9 and abs(dm) < 1e-9
            print(f"  {p.GetName():<28} {inst:<8} stiffness={st:<10.4g} damping={dm:<10.4g} "
                  f"type={ty:<13} maxForce={mf}  {'✅ 0' if zero else '⚠️ 게인이 굳었다'}")
            if not zero:
                warn.append(f"{p.GetName()}: drive 게인이 0 이 아니다 (stiffness={st}, damping={dm})")

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
