#!/usr/bin/env python3
"""USD → GLB (단일 파일 binary glTF). 호스트로 가져가 웹 뷰어로 확인하기 위한 도구.

  # 컨테이너 안 (Isaac Sim 의 pxr 사용)
  cd /workspace/IsaacLab
  ./isaaclab.sh -p /workspace/tools/usd_to_glb.py /workspace/assets/racecar.usd \
      -o /workspace/assets/racecar_collision.glb --only collision

  # 독립 실행 (Isaac Sim 없이)
  pip install usd-core && python usd_to_glb.py in.usd -o out.glb

★ 왜 직접 만들었나 ────────────────────────────────────────────────────────
usd2gltf(PyPI)로 테스트한 결과: UsdGeom.Mesh 는 변환하지만 **Cube/Cylinder 같은
primitive 는 tessellate 하지 않는다.** node 계층만 나오고 meshes 는 빈 배열이다.
우리 racecar.usd 는 primitive(box + cylinder)로 되어 있어 빈 glTF 가 된다.
그래서 primitive 를 직접 삼각형으로 펼친다.

또한 pip 의 usd-core 는 usdcat / usdview CLI 를 포함하지 않는다. Isaac Sim 번들에만 있다.

내보내는 것:
  · Cube, Cylinder, Sphere, Capsule, Cone  → tessellate
  · Mesh                                   → 그대로 (n각형은 fan 삼각분할)
  · world transform 을 정점에 굽는다 (node 변환은 항등) — 뷰어 호환성이 가장 좋다
  · visual / collision 을 색으로 구분
"""

import argparse
import base64
import json
import math
import struct
import sys

# ── Isaac Sim 안에서 돌 때는 AppLauncher 가 필요하다 ─────────────────────
_NEED_APP = False
try:
    from pxr import Gf, Usd, UsdGeom  # noqa: F401
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
    _app_launcher = AppLauncher(_known)
    _sim_app = _app_launcher.app
    sys.argv = [sys.argv[0]] + _rest
    from pxr import Gf, Usd, UsdGeom  # noqa: F811
else:
    _sim_app = None


# ══ tessellation ═══════════════════════════════════════════════════════
def box(hx, hy, hz):
    v = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
         (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
         (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
         (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return v, f


def _axis_map(axis):
    """원기둥 로컬 축(u, v, w) 를 반환한다. w 가 대칭축."""
    return {"X": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
            "Y": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
            "Z": ((1, 0, 0), (0, 1, 0), (0, 0, 1))}.get(axis, ((1, 0, 0), (0, 1, 0), (0, 0, 1)))


def cylinder(radius, height, axis="Z", seg=32):
    u, v, w = _axis_map(axis)
    h = height / 2.0
    V, F = [], []
    for s in (-1, 1):                      # 두 링
        for i in range(seg):
            a = 2 * math.pi * i / seg
            c, sn = radius * math.cos(a), radius * math.sin(a)
            V.append(tuple(c * u[k] + sn * v[k] + s * h * w[k] for k in range(3)))
    bot_c, top_c = len(V), len(V) + 1
    V.append(tuple(-h * w[k] for k in range(3)))
    V.append(tuple(+h * w[k] for k in range(3)))
    for i in range(seg):
        j = (i + 1) % seg
        b0, b1, t0, t1 = i, j, seg + i, seg + j
        F += [(b0, t0, t1), (b0, t1, b1)]          # 측면
        F += [(bot_c, b1, b0), (top_c, t0, t1)]    # 뚜껑
    return V, F


def sphere(radius, seg=24, rings=16):
    V, F = [], []
    for r in range(rings + 1):
        phi = math.pi * r / rings
        for i in range(seg):
            th = 2 * math.pi * i / seg
            V.append((radius * math.sin(phi) * math.cos(th),
                      radius * math.sin(phi) * math.sin(th),
                      radius * math.cos(phi)))
    for r in range(rings):
        for i in range(seg):
            j = (i + 1) % seg
            a, b = r * seg + i, r * seg + j
            c, d = (r + 1) * seg + i, (r + 1) * seg + j
            F += [(a, c, d), (a, d, b)]
    return V, F


def capsule(radius, height, axis="Z", seg=24):
    """원기둥 + 양끝 반구. 근사로 구 2개 + 원기둥으로 합친다."""
    u, v, w = _axis_map(axis)
    h = height / 2.0
    V, F = cylinder(radius, height, axis, seg)
    for s in (-1, 1):
        sv, sf = sphere(radius, seg, seg // 2)
        off = len(V)
        for x, y, z in sv:
            # 구의 로컬 z 를 w 축으로 회전시키고 끝으로 평행이동
            V.append(tuple(x * u[k] + y * v[k] + z * w[k] + s * h * w[k] for k in range(3)))
        F += [(a + off, b + off, c + off) for a, b, c in sf]
    return V, F


def cone(radius, height, axis="Z", seg=32):
    u, v, w = _axis_map(axis)
    h = height / 2.0
    V, F = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        V.append(tuple(radius * math.cos(a) * u[k] + radius * math.sin(a) * v[k] - h * w[k]
                       for k in range(3)))
    apex, base_c = len(V), len(V) + 1
    V.append(tuple(+h * w[k] for k in range(3)))
    V.append(tuple(-h * w[k] for k in range(3)))
    for i in range(seg):
        j = (i + 1) % seg
        F += [(i, apex, j), (base_c, j, i)]
    return V, F


def mesh_prim(prim):
    """UsdGeom.Mesh → (정점, 삼각형). n각형은 fan 으로 분할."""
    m = UsdGeom.Mesh(prim)
    pts = m.GetPointsAttr().Get()
    if not pts:
        return None
    counts = m.GetFaceVertexCountsAttr().Get() or []
    idx = m.GetFaceVertexIndicesAttr().Get() or []
    V = [tuple(p) for p in pts]
    F, o = [], 0
    for c in counts:
        if c >= 3:
            for k in range(1, c - 1):
                F.append((idx[o], idx[o + k], idx[o + k + 1]))
        o += c
    return V, F


def geometry_of(prim):
    t = prim.GetTypeName()
    if t == "Cube":
        s = UsdGeom.Cube(prim).GetSizeAttr().Get() or 2.0
        return box(s / 2, s / 2, s / 2)
    if t == "Cylinder":
        g = UsdGeom.Cylinder(prim)
        return cylinder(g.GetRadiusAttr().Get() or 1.0,
                        g.GetHeightAttr().Get() or 2.0,
                        g.GetAxisAttr().Get() or "Z")
    if t == "Sphere":
        return sphere(UsdGeom.Sphere(prim).GetRadiusAttr().Get() or 1.0)
    if t == "Capsule":
        g = UsdGeom.Capsule(prim)
        return capsule(g.GetRadiusAttr().Get() or 0.5,
                       g.GetHeightAttr().Get() or 1.0,
                       g.GetAxisAttr().Get() or "Z")
    if t == "Cone":
        g = UsdGeom.Cone(prim)
        return cone(g.GetRadiusAttr().Get() or 1.0,
                    g.GetHeightAttr().Get() or 2.0,
                    g.GetAxisAttr().Get() or "Z")
    if t == "Mesh":
        return mesh_prim(prim)
    return None


# ══ GLB 작성 ═══════════════════════════════════════════════════════════
def write_glb(path, parts):
    """parts: [(name, verts_world, tris, material_index)]  materials 는 아래 고정 2개."""
    buf = bytearray()
    accessors, meshes, nodes, bviews = [], [], [], []

    def align4(b):
        while len(b) % 4:
            b.append(0)

    for name, V, F, mat in parts:
        # 정점
        align4(buf)
        v_off = len(buf)
        for x, y, z in V:
            buf += struct.pack("<3f", x, y, z)
        v_len = len(buf) - v_off
        mn = [min(p[i] for p in V) for i in range(3)]
        mx = [max(p[i] for p in V) for i in range(3)]
        bviews.append({"buffer": 0, "byteOffset": v_off, "byteLength": v_len})
        accessors.append({"bufferView": len(bviews) - 1, "componentType": 5126,
                          "count": len(V), "type": "VEC3", "min": mn, "max": mx})
        a_pos = len(accessors) - 1
        # 인덱스
        align4(buf)
        i_off = len(buf)
        for tri in F:
            buf += struct.pack("<3I", *tri)
        i_len = len(buf) - i_off
        bviews.append({"buffer": 0, "byteOffset": i_off, "byteLength": i_len})
        accessors.append({"bufferView": len(bviews) - 1, "componentType": 5125,
                          "count": len(F) * 3, "type": "SCALAR"})
        a_idx = len(accessors) - 1

        meshes.append({"name": name,
                       "primitives": [{"attributes": {"POSITION": a_pos},
                                       "indices": a_idx, "material": mat}]})
        nodes.append({"name": name, "mesh": len(meshes) - 1})

    align4(buf)
    gltf = {
        "asset": {"version": "2.0", "generator": "tools/usd_to_glb.py"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "accessors": accessors,
        "bufferViews": bviews,
        "buffers": [{"byteLength": len(buf)}],
        "materials": [
            {"name": "visual", "pbrMetallicRoughness": {
                "baseColorFactor": [0.25, 0.55, 0.95, 1.0], "metallicFactor": 0.1,
                "roughnessFactor": 0.6}},
            {"name": "collision", "pbrMetallicRoughness": {
                "baseColorFactor": [0.95, 0.45, 0.15, 0.55], "metallicFactor": 0.0,
                "roughnessFactor": 0.9}, "alphaMode": "BLEND", "doubleSided": True},
        ],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    total = 12 + 8 + len(js) + 8 + len(buf)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(buf), 0x004E4942)); f.write(bytes(buf))
    return total


# ══ main ═══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="USD → GLB (primitive tessellate 포함)")
    ap.add_argument("usd", help="입력 USD")
    ap.add_argument("-o", "--out", default=None, help="출력 .glb (기본: 입력명.glb)")
    ap.add_argument("--only", choices=["visual", "collision", "both"], default="both",
                    help="내보낼 기하 (기본 both). collision 은 반투명 주황")
    ap.add_argument("--seg", type=int, default=32, help="원기둥 분할 수")
    a = ap.parse_args()
    out = a.out or a.usd.rsplit(".", 1)[0] + ".glb"

    stage = Usd.Stage.Open(a.usd)
    if stage is None:
        sys.exit(f"열 수 없음: {a.usd}")

    pred = Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)
    xf = UsdGeom.XformCache(Usd.TimeCode.Default())
    parts, skipped = [], []
    for prim in stage.Traverse(pred):
        g = geometry_of(prim)
        if g is None:
            continue
        V, F = g
        if not V or not F:
            skipped.append(f"{prim.GetPath()} (빈 기하)")
            continue
        path = str(prim.GetPath()).lower()
        is_col = "collision" in path or "collider" in path
        kind = "collision" if is_col else "visual"
        if a.only != "both" and kind != a.only:
            continue
        M = xf.GetLocalToWorldTransform(prim)
        Vw = [tuple(M.Transform(Gf.Vec3d(*v))) for v in V]
        parts.append((str(prim.GetPath()), Vw, F, 1 if is_col else 0))

    if not parts:
        print("⚠️ 내보낼 기하가 없다.")
        print("   --only 를 both 로 바꾸거나, inspect_usd.py --tree 로 prim 을 확인하라.")
        return 1

    size = write_glb(out, parts)
    nv = sum(len(p[1]) for p in parts)
    nt = sum(len(p[2]) for p in parts)
    nc = sum(1 for p in parts if p[3] == 1)
    print(f"✅ {out}")
    print(f"   {len(parts)}개 prim  (visual {len(parts)-nc} / collision {nc})")
    print(f"   정점 {nv:,}  삼각형 {nt:,}  파일 {size:,} bytes")
    for name, V, F, mat in parts:
        print(f"     {'[col]' if mat else '[vis]'} {name}  v={len(V)} t={len(F)}")
    if skipped:
        print("   건너뜀:")
        for s in skipped:
            print(f"     · {s}")
    import os
    host = out[len("/workspace/"):] if out.startswith("/workspace/") else os.path.basename(out)
    print("\n   호스트로 가져가서 보기:")
    print(f"     scp <이름>@192.168.50.112:~/rl-racing/{host} .")
    print("     → https://gltf-viewer.donmccurdy.com/ 에 드래그 (전부 브라우저 안에서 처리된다)")
    print("     → 또는 Windows '3D 보기' 앱이 .glb 를 바로 연다")
    return 0


if __name__ == "__main__":
    rc = main()
    if _sim_app is not None:
        _sim_app.close()
    sys.exit(rc)
