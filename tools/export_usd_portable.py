#!/usr/bin/env python3
"""USD 를 다른 PC 에서 열 수 있는 단일 파일로 만든다.

  cd /workspace/IsaacLab
  ./isaaclab.sh -p /workspace/tools/export_usd_portable.py /workspace/assets/racecar.usd

★ 왜 필요한가 ───────────────────────────────────────────────────────────
Isaac Lab 의 URDF importer 는 다중 파일 USD 를 만든다:

    racecar.usd                        1,456 B   ← 참조 스텁
    configuration/racecar_base.usd     2,937 B
    configuration/racecar_physics.usd  3,524 B
    configuration/racecar_robot.usd    1,728 B
    configuration/racecar_sensor.usd     647 B

그리고 참조가 **절대경로**다:
    @/workspace/assets/configuration/racecar_base.usd@
로컬 PC 에는 /workspace 가 없으므로 그냥 복사하면 참조가 전부 깨진다.

Flatten 은 composition 을 전부 풀어 **하나의 레이어**로 합친다. 그러면 어디서든 열린다.

산출물
  *_flat.usda   ASCII. 사람이 읽고 git diff 가 된다. 크지만 확실하다
  *_flat.usdc   Crate 바이너리. 작고 빠르다
  *.usdz        zip 패키지 (선택). 일부 뷰어가 바로 연다
"""

import argparse
import os
import sys

_NEED_APP = False
try:
    from pxr import Usd, UsdUtils  # noqa: F401
except ModuleNotFoundError:
    _NEED_APP = True

if _NEED_APP:
    try:
        from isaaclab.app import AppLauncher
    except ModuleNotFoundError:
        sys.exit("pxr 도 isaaclab 도 없다. `pip install usd-core` 하거나 "
                 "`./isaaclab.sh -p` 로 실행하라.")
    _p = argparse.ArgumentParser(add_help=False)
    AppLauncher.add_app_launcher_args(_p)
    _known, _rest = _p.parse_known_args()
    _known.headless = True
    _app = AppLauncher(_known)
    _sim_app = _app.app
    sys.argv = [sys.argv[0]] + _rest
    from pxr import Usd, UsdUtils  # noqa: F811
else:
    _sim_app = None


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    ap = argparse.ArgumentParser(description="USD 를 단일 파일로 평탄화")
    ap.add_argument("usd", nargs="?", default="/workspace/assets/racecar.usd")
    ap.add_argument("--usdz", action="store_true", help=".usdz 패키지도 만든다")
    ap.add_argument("--no-ascii", action="store_true", help=".usda 를 건너뛴다")
    a = ap.parse_args()

    src = os.path.abspath(a.usd)
    stem = src.rsplit(".", 1)[0]
    print(f"입력: {src}  ({human(os.path.getsize(src))})")

    stage = Usd.Stage.Open(src, Usd.Stage.LoadAll)
    if stage is None:
        sys.exit(f"열 수 없음: {src}")

    print("\n합성된 레이어 (이게 전부 하나로 합쳐진다):")
    for lyr in stage.GetUsedLayers():
        i = lyr.identifier
        if i.startswith("anon:"):
            continue
        sz = human(os.path.getsize(i)) if os.path.exists(i) else "-"
        print(f"  {os.path.basename(i):<34} {sz:>10}   {i}")

    flat = stage.Flatten()          # composition 을 전부 풀어 단일 레이어로
    outs = []

    if not a.no_ascii:
        p = stem + "_flat.usda"
        flat.Export(p)
        outs.append(p)

    p = stem + "_flat.usdc"
    flat.Export(p)
    outs.append(p)

    if a.usdz:
        try:
            p = stem + ".usdz"
            UsdUtils.CreateNewUsdzPackage(src, p)
            outs.append(p)
        except Exception as e:                                        # noqa: BLE001
            print(f"  ⚠️ usdz 생성 실패: {type(e).__name__}: {e}")

    print("\n산출물:")
    for p in outs:
        print(f"  ✅ {human(os.path.getsize(p)):>10}  {p}")

    # 검증: 평탄화된 파일에 외부 참조가 남아 있으면 안 된다
    print("\n검증 — 외부 참조가 남아 있는가:")
    chk = Usd.Stage.Open(outs[-1] if a.no_ascii else stem + "_flat.usda", Usd.Stage.LoadAll)
    ext = [l.identifier for l in chk.GetUsedLayers()
           if not l.identifier.startswith("anon:")
           and os.path.abspath(l.identifier) != os.path.abspath(
               outs[-1] if a.no_ascii else stem + "_flat.usda")]
    if ext:
        print("  ⚠️ 남아 있다:")
        for e in ext:
            print(f"     {e}")
    else:
        print("  ✅ 없음 — 다른 PC 로 복사해도 그대로 열린다")

    n_prims = len(list(chk.Traverse(Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate))))
    print(f"  prim {n_prims}개 (원본과 같아야 한다)")

    print("\n로컬 PC 에서 가져가기:")
    for pth in outs:
        if pth.startswith("/workspace/"):
            print(f"  scp <이름>@192.168.50.112:~/rl-racing/{pth[len('/workspace/'):]} .")
        else:
            print(f"  scp <이름>@192.168.50.112:{pth} .")
    print("\n  열어보기:")
    print("    · Blender      : File > Import > Universal Scene Description (네이티브 지원)")
    print("    · Isaac Sim    : 다른 PC 에서도 그대로 열린다")
    print("    · 기하만 볼 때 : usd_to_glb.py 로 만든 .glb 가 더 간편하다")
    return 0


if __name__ == "__main__":
    rc = main()
    if _sim_app is not None:
        _sim_app.close()
    sys.exit(rc)
