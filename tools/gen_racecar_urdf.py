#!/usr/bin/env python3
"""
F1TENTH 1/10 물리용 URDF 생성기.

손으로 쓰지 않는 이유:
  - 합성(composite) 질량 · CoG · yaw inertia 가 dynamics.yaml 의 목표값과
    "정확히" 일치해야 한다. 손으로 맞추면 반드시 틀린다.
  - system identification 이 끝나면 파라미터가 바뀐다 → 재생성이 필요하다.
  - 1/8 로 전환하면 전부 바뀐다.

이 스크립트는 바퀴·너클의 질량과 위치를 먼저 놓고,
**섀시의 질량 · CoG · 관성 텐서를 역산**해서 합성값이 목표와 맞도록 만든다.
마지막에 순방향으로 다시 합성해서 검증 표를 출력한다.

출처:
  stack_master/config/CAR/dynamics.yaml       m, I, lf, lr, h, s_min/max, sv_max, width
  stack_master/config/CAR/static_transforms   base_link -> laser = [0.27, 0, 0.11]
  f1tenth_gym_ros/config/ego_racecar.xacro    wheel_radius, wheel_length
  f1tenth_URDF/robot.urdf (Onshape CAD)       track = 0.2255  (순기구학으로 추출)

좌표계: ROS REP-103.  +x 전방, +y 좌측, +z 상방.
원점:   base_link = 뒤 차축 중심, 지면 높이 (z=0).
        따라서 spawn 을 z=0 으로 하면 바퀴가 지면에 정확히 닿는다.
"""

import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom

# ──────────────────────────────────────────────────────────────────────
# 파라미터 — 여기만 고치면 된다
# ──────────────────────────────────────────────────────────────────────
PARAMS = dict(
    # ── 목표 합성값 (dynamics.yaml) ────────────────────────────────
    m_total   = 3.47,      # kg        전체 질량
    I_zz      = 0.04712,   # kg m^2    CoG 기준 yaw 관성
    lf        = 0.15875,   # m         CoG -> 앞 차축
    lr        = 0.17145,   # m         CoG -> 뒤 차축   (wheelbase = lf + lr = 0.3302)
    h_cog     = 0.074,     # m         CoG 높이

    # ── 기하 ────────────────────────────────────────────────────────
    track        = 0.2255, # m   CAD 순기구학에서 추출 (dynamics.yaml 의 width 0.2032 는
                           #     planner 의 충돌 폭이지 track 이 아니다 — 다른 양)
    wheel_radius = 0.0508,
    wheel_width  = 0.0381,

    # ── 섀시 충돌 박스 (시각화 겸용) ────────────────────────────────
    body_len = 0.50, body_wid = 0.20, body_hgt = 0.10,
    body_x   = 0.165,      # 뒤 차축 기준 박스 중심 x
    body_z   = 0.080,      # 지면 기준 박스 중심 z (지상고 0.03)

    # ── 부품 질량 (합성값을 맞추기 위해 섀시가 자동 조정된다) ────────
    m_wheel = 0.070,       # 1/10 RC 휠+타이어 실측 대역 60~80 g
    m_hinge = 0.050,       # 조향 너클. 너무 가벼우면 PhysX 질량비 문제가 생긴다

    # ── 관절 한계 ───────────────────────────────────────────────────
    steer_limit   = 0.4189,  # rad   dynamics.yaml s_min/s_max
    steer_vel     = 3.2,     # rad/s dynamics.yaml sv_min/sv_max
    steer_effort  = 5.0,     # N m   서보 토크 (추정 — 실측 전까지 여유값)
    v_max_mps     = 10.0,    # m/s   휠 각속도 한계 산출용 (IQP 최대 8.69 위로 여유)
    a_max         = 9.51,    # m/s^2 dynamics.yaml — 휠 토크 한계 산출용

    # ── 섀시 관성 형상비 (Ixx, Iyy 를 정하기 위한 등가 박스의 폭/높이) ─
    #    Izz 는 목표값에서 역산되고, 여기서 a(길이)가 결정된다.
    eq_box_wid = 0.18, eq_box_hgt = 0.10,
)


def solve_chassis(p):
    """바퀴·너클을 고정해 놓고, 합성값이 목표와 맞도록 섀시를 역산한다."""
    wb = p["lf"] + p["lr"]
    r, hy = p["wheel_radius"], p["track"] / 2.0
    mw, mh = p["m_wheel"], p["m_hinge"]

    # base_link(뒤 차축, 지면) 기준 부품 위치
    parts = [  # (mass, x, y, z)
        (mw, 0.0, +hy, r), (mw, 0.0, -hy, r),          # 뒤 바퀴
        (mw,  wb, +hy, r), (mw,  wb, -hy, r),          # 앞 바퀴
        (mh,  wb, +hy, r), (mh,  wb, -hy, r),          # 조향 너클
    ]
    m_parts = sum(m for m, *_ in parts)
    m_c = p["m_total"] - m_parts
    if m_c <= 0:
        raise ValueError("부품 질량 합이 전체 질량을 넘는다")

    # 목표 CoG (base_link 기준)
    cx, cz = p["lr"], p["h_cog"]

    # 섀시 CoG 역산:  Σ m_i x_i = m_total * cx
    x_c = (p["m_total"] * cx - sum(m * x for m, x, _, _ in parts)) / m_c
    z_c = (p["m_total"] * cz - sum(m * z for m, _, _, z in parts)) / m_c

    # 바퀴 자체 관성 (원기둥, 스핀축 = y)
    Iw_spin = 0.5 * mw * r**2
    Iw_tran = (1.0 / 12.0) * mw * (3 * r**2 + p["wheel_width"] ** 2)
    Ih = (1.0 / 12.0) * mh * (0.04**2 + 0.04**2)  # 너클 ≈ 4cm 정육면체

    # 부품들이 CoG 기준 Izz 에 기여하는 양 (평행축 정리)
    Izz_parts = 0.0
    for m, x, y, _ in parts:
        Izz_parts += m * ((x - cx) ** 2 + y**2)
    Izz_parts += 4 * Iw_tran + 2 * Ih  # 각 부품 자체의 izz

    # 섀시가 채워야 할 몫
    Izz_c_about_cog = p["I_zz"] - Izz_parts
    if Izz_c_about_cog <= 0:
        raise ValueError("부품만으로 목표 Izz 를 넘었다. m_wheel/track 을 줄여라")
    # 섀시 자신의 CoG 기준으로 환산
    Izz_c = Izz_c_about_cog - m_c * (x_c - cx) ** 2

    # Ixx, Iyy 는 같은 질량·같은 Izz 를 갖는 등가 박스에서 얻는다
    b, c = p["eq_box_wid"], p["eq_box_hgt"]
    a2 = Izz_c * 12.0 / m_c - b**2          # a^2 + b^2 = 12 Izz / m
    if a2 <= 0:
        raise ValueError("eq_box_wid 가 너무 크다")
    a = a2**0.5
    Ixx_c = (1.0 / 12.0) * m_c * (b**2 + c**2)
    Iyy_c = (1.0 / 12.0) * m_c * (a2 + c**2)

    return dict(m_c=m_c, x_c=x_c, z_c=z_c, Ixx=Ixx_c, Iyy=Iyy_c, Izz=Izz_c,
                eq_len=a, parts=parts, Iw_spin=Iw_spin, Iw_tran=Iw_tran, Ih=Ih, wb=wb)


def verify(p, s):
    """순방향으로 다시 합성해서 목표와 맞는지 확인한다."""
    items = list(s["parts"]) + [(s["m_c"], s["x_c"], 0.0, s["z_c"])]
    M = sum(m for m, *_ in items)
    cx = sum(m * x for m, x, _, _ in items) / M
    cz = sum(m * z for m, _, _, z in items) / M
    Izz = sum(m * ((x - cx) ** 2 + y**2) for m, x, y, _ in items)
    Izz += 4 * s["Iw_tran"] + 2 * s["Ih"] + s["Izz"]
    return M, cx, cz, Izz


def inertial(el, m, xyz, I):
    i = ET.SubElement(el, "inertial")
    ET.SubElement(i, "origin", xyz=xyz, rpy="0 0 0")
    ET.SubElement(i, "mass", value=f"{m:.6f}")
    ET.SubElement(i, "inertia", ixx=f"{I[0]:.8f}", ixy="0", ixz="0",
                  iyy=f"{I[1]:.8f}", iyz="0", izz=f"{I[2]:.8f}")


def build(p, s):
    wb, r, hy = s["wb"], p["wheel_radius"], p["track"] / 2.0
    root = ET.Element("robot", name="racecar")
    root.append(ET.Comment(
        " GENERATED by tools/gen_racecar_urdf.py : do not edit by hand.\n"
        "       Frame: REP-103 (+x forward, +y left). base_link = rear axle center at ground (z=0).\n"
        "       Spawn base_link at z=0 and the wheels sit exactly on the ground.\n"
        "       LiDAR is NOT a link: attach Isaac Lab RayCaster to base_link with\n"
        "       offset=(0.27, 0.0, 0.11)  [stack_master/config/CAR/static_transforms.yaml].\n"
        "       Steering hinges intentionally carry NO collision geometry : a knuckle\n"
        "       must never generate contacts. Mass/inertia only.\n"
        "       Tire friction is NOT in URDF. Set it in Isaac Lab RigidBodyMaterialCfg\n"
        "       that is where the mu domain randomization goes. "))

    # ── base_link ────────────────────────────────────────────────
    bl = ET.SubElement(root, "link", name="base_link")
    inertial(bl, s["m_c"], f"{s['x_c']:.6f} 0 {s['z_c']:.6f}", (s["Ixx"], s["Iyy"], s["Izz"]))
    for tag in ("visual", "collision"):
        e = ET.SubElement(bl, tag)
        ET.SubElement(e, "origin", xyz=f"{p['body_x']} 0 {p['body_z']}", rpy="0 0 0")
        g = ET.SubElement(e, "geometry")
        ET.SubElement(g, "box", size=f"{p['body_len']} {p['body_wid']} {p['body_hgt']}")

    def wheel(name, x, y, parent, jname):
        lk = ET.SubElement(root, "link", name=name)
        # 스핀축 = y  →  Iyy 가 스핀 관성
        inertial(lk, p["m_wheel"], "0 0 0", (s["Iw_tran"], s["Iw_spin"], s["Iw_tran"]))
        for tag in ("visual", "collision"):
            e = ET.SubElement(lk, tag)
            # URDF cylinder 의 축은 z 이므로 x축으로 90도 돌려 y축에 맞춘다
            ET.SubElement(e, "origin", xyz="0 0 0", rpy="1.5707963 0 0")
            g = ET.SubElement(e, "geometry")
            ET.SubElement(g, "cylinder", radius=f"{r}", length=f"{p['wheel_width']}")
        j = ET.SubElement(root, "joint", name=jname, type="continuous")
        ET.SubElement(j, "parent", link=parent)
        ET.SubElement(j, "child", link=name)
        ET.SubElement(j, "origin", xyz=f"{x} {y} {z_of(parent, r)}", rpy="0 0 0")
        ET.SubElement(j, "axis", xyz="0 1 0")
        tq = p["m_total"] * p["a_max"] * r / 2.0          # 뒤 두 바퀴가 나눠 받는다
        ET.SubElement(j, "limit", effort=f"{tq*1.5:.3f}", velocity=f"{p['v_max_mps']/r:.2f}")

    def z_of(parent, r):
        return 0.0 if parent.endswith("hinge") else r

    # ── 조향 너클 (앞) ───────────────────────────────────────────
    for side, sgn in (("left", +1), ("right", -1)):
        hn = f"front_{side}_hinge"
        lk = ET.SubElement(root, "link", name=hn)
        inertial(lk, p["m_hinge"], "0 0 0", (s["Ih"], s["Ih"], s["Ih"]))
        j = ET.SubElement(root, "joint", name=f"{hn}_joint", type="revolute")
        ET.SubElement(j, "parent", link="base_link")
        ET.SubElement(j, "child", link=hn)
        ET.SubElement(j, "origin", xyz=f"{wb} {sgn*hy:.6f} {r}", rpy="0 0 0")
        ET.SubElement(j, "axis", xyz="0 0 1")             # 킹핀 경사 0 (의도적 단순화)
        ET.SubElement(j, "limit",
                      lower=f"{-p['steer_limit']}", upper=f"{p['steer_limit']}",
                      effort=f"{p['steer_effort']}", velocity=f"{p['steer_vel']}")
        wheel(f"front_{side}_wheel", 0.0, 0.0, hn, f"front_{side}_wheel_joint")

    # ── 뒤 구동륜 ────────────────────────────────────────────────
    for side, sgn in (("left", +1), ("right", -1)):
        wheel(f"rear_{side}_wheel", 0.0, sgn * hy, "base_link", f"rear_{side}_wheel_joint")

    return root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="urdf/racecar_physics.urdf")
    a = ap.parse_args()

    p = PARAMS
    s = solve_chassis(p)
    M, cx, cz, Izz = verify(p, s)

    print("=" * 74)
    print("  역산된 섀시 파라미터")
    print("=" * 74)
    print(f"  질량        {s['m_c']:.4f} kg   (부품 합계 {p['m_total']-s['m_c']:.4f} kg)")
    print(f"  CoG         x={s['x_c']:.5f}  z={s['z_c']:.5f}   (base_link = 뒤 차축·지면)")
    print(f"  관성        Ixx={s['Ixx']:.6f}  Iyy={s['Iyy']:.6f}  Izz={s['Izz']:.6f}")
    print(f"  등가 박스   {s['eq_len']:.4f} x {p['eq_box_wid']} x {p['eq_box_hgt']} m")
    print()
    print("=" * 74)
    print("  ★ 순방향 재합성 검증 — 목표와 일치해야 한다")
    print("=" * 74)
    print(f"  {'항목':<16}{'목표':>14}{'합성 결과':>16}{'오차':>14}")
    for nm, tgt, got in (("총 질량 [kg]", p["m_total"], M),
                         ("CoG x [m]",    p["lr"],     cx),
                         ("CoG z [m]",    p["h_cog"],  cz),
                         ("Izz [kg m^2]", p["I_zz"],   Izz)):
        print(f"  {nm:<16}{tgt:>14.6f}{got:>16.6f}{abs(got-tgt):>14.2e}")
    print()
    print(f"  wheelbase   {s['wb']:.4f} m      track {p['track']:.4f} m")
    print(f"  조향 한계    ±{p['steer_limit']} rad (±{p['steer_limit']*57.2958:.1f}°)")
    print(f"  휠 각속도    ±{p['v_max_mps']/p['wheel_radius']:.1f} rad/s "
          f"(= ±{p['v_max_mps']} m/s)")

    xml = minidom.parseString(ET.tostring(build(p, s))).toprettyxml(indent="  ")
    xml = "\n".join(l for l in xml.split("\n") if l.strip())
    with open(a.out, "w") as f:
        f.write(xml + "\n")
    print(f"\n  → {a.out}")


if __name__ == "__main__":
    main()
