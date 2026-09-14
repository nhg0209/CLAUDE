#!/usr/bin/env python3
"""
변환된 USD 를 물리 관점에서 검사한다. GUI 없이 구조를 확인하는 수단.

  ./isaaclab.sh -p /workspace/tools/inspect_usd.py /workspace/assets/racecar.usd

확인하는 것:
  1. articulation root 가 하나인가
  2. 각 link 의 mass / CoG / 관성 — URDF 값이 살아남았는가
  3. ★ collider 근사 방식 — PhysX 는 네이티브 원기둥이 없어서 convexHull 로
     바꿔버릴 수 있다. 그러면 바퀴가 다각형이 되어 구를 때 덜컹거린다.
  4. joint 종류 / 축 / 한계 — exporter 가 뭉개지 않았는가
  5. drive 가 붙어버렸는가 (--joint-target-type none 이면 없어야 한다)
"""
import sys
from pxr import Usd, UsdGeom, UsdPhysics, Gf

try:
    from pxr import PhysxSchema
except ImportError:
    PhysxSchema = None


def main(path):
    stage = Usd.Stage.Open(path)
    if stage is None:
        sys.exit(f"열 수 없음: {path}")
    print(f"USD: {path}\nup axis: {UsdGeom.GetStageUpAxis(stage)}   "
          f"metersPerUnit: {UsdGeom.GetStageMetersPerUnit(stage)}")

    roots, bodies, colliders, joints, drives = [], [], [], [], []
    for p in stage.Traverse():
        if p.HasAPI(UsdPhysics.ArticulationRootAPI):
            roots.append(p)
        if p.HasAPI(UsdPhysics.RigidBodyAPI):
            bodies.append(p)
        if p.HasAPI(UsdPhysics.CollisionAPI):
            colliders.append(p)
        if p.IsA(UsdPhysics.Joint):
            joints.append(p)
        if p.HasAPI(UsdPhysics.DriveAPI) or any(
                n.startswith("drive:") for n in p.GetPropertyNames()):
            drives.append(p)

    print(f"\n{'='*78}\n 1. Articulation root\n{'='*78}")
    for r in roots:
        print(f"  {r.GetPath()}")
    print(f"  → {len(roots)}개 " + ("✅" if len(roots) == 1 else "⚠️ 1개여야 한다"))

    print(f"\n{'='*78}\n 2. Rigid body 질량 / CoG\n{'='*78}")
    print(f"  {'prim':<34}{'mass':>10}{'CoG':>30}")
    total = 0.0
    for b in bodies:
        m = None
        if b.HasAPI(UsdPhysics.MassAPI):
            api = UsdPhysics.MassAPI(b)
            a = api.GetMassAttr()
            m = a.Get() if a and a.HasAuthoredValue() else None
            c = api.GetCenterOfMassAttr()
            cog = c.Get() if c and c.HasAuthoredValue() else None
        else:
            cog = None
        if m:
            total += m
        name = str(b.GetPath()).split("/")[-1]
        cs = f"({cog[0]:.4f}, {cog[1]:.4f}, {cog[2]:.4f})" if cog else "-"
        print(f"  {name:<34}{m if m is not None else '(auto)':>10}{cs:>30}")
    print(f"  {'─'*74}\n  {'합계':<34}{total:>10.4f}   ← URDF 목표 3.4700")

    print(f"\n{'='*78}\n 3. ★ Collider 근사 방식 — 바퀴가 원기둥으로 남았는가\n{'='*78}")
    print(f"  {'prim':<38}{'geom':>14}{'approximation':>22}")
    for c in colliders:
        geom = c.GetTypeName()
        appr = "-"
        if c.HasAPI(UsdPhysics.MeshCollisionAPI):
            a = UsdPhysics.MeshCollisionAPI(c).GetApproximationAttr()
            if a:
                appr = str(a.Get())
        name = str(c.GetPath()).split("/")[-1]
        flag = ""
        if "wheel" in str(c.GetPath()).lower():
            flag = "  ← 바퀴" + (" ⚠️ convex 면 덜컹거린다" if "onvex" in appr or geom == "Mesh" else " ✅")
        print(f"  {name:<38}{str(geom):>14}{appr:>22}{flag}")

    print(f"\n{'='*78}\n 4. Joint\n{'='*78}")
    print(f"  {'joint':<30}{'type':<18}{'axis':>6}{'lower':>10}{'upper':>10}")
    for j in joints:
        t = j.GetTypeName()
        ax, lo, up = "-", "-", "-"
        if j.IsA(UsdPhysics.RevoluteJoint):
            rj = UsdPhysics.RevoluteJoint(j)
            ax = str(rj.GetAxisAttr().Get())
            l, u = rj.GetLowerLimitAttr().Get(), rj.GetUpperLimitAttr().Get()
            lo = f"{l:.2f}" if l is not None else "-"
            up = f"{u:.2f}" if u is not None else "-"
        elif j.IsA(UsdPhysics.PrismaticJoint):
            pj = UsdPhysics.PrismaticJoint(j)
            ax = str(pj.GetAxisAttr().Get())
        print(f"  {str(j.GetPath()).split('/')[-1]:<30}{str(t):<18}{ax:>6}{lo:>10}{up:>10}")
    print(f"  → {len(joints)}개")
    print("  ⚠️ revolute 한계는 도(degree) 단위다. ±0.4189 rad = ±24.0° 로 보여야 정상")

    print(f"\n{'='*78}\n 5. Drive (--joint-target-type none 이면 비어야 한다)\n{'='*78}")
    if drives:
        for d in drives:
            print(f"  ⚠️ {d.GetPath()}")
        print("  → drive 가 USD 에 굳었다. ActuatorCfg 로 제어하려면 재변환 권장")
    else:
        print("  ✅ 없음. 액추에이터는 Python ActuatorCfg 에서 정의하면 된다")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/workspace/assets/racecar.usd")
