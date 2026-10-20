import math, toy
R, J, M, KK, FZ, MU = toy.R, toy.J, toy.M, toy.KK, toy.FZ, toy.MU
SIG = 0.02

def cfun(v, c0=40.0, vlow=1.0):
    av = abs(v)
    return c0 * 0.5 * (1 + math.cos(math.pi * av / vlow)) if av < vlow else 0.0

def run(tau, T, form, clamp=False, cap=1.0, w0=0.0, v0=0.0, dt=0.005, c0=40.0, vlow=1.0, u0=0.0):
    w, v, u, udot = w0, v0, u0, 0.0
    Fs, Fds, vs = [], [], []
    for _ in range(int(round(T / dt))):
        s = w * R - v
        # ① 이번 step 속도로 u 갱신 (exp 정확해 + 상한), u̇ = 실제 변화량/dt
        a = abs(v) / SIG
        if a > 1e-9:
            e = math.exp(-a * dt); un = u * e + s * (1 - e) / a
        else:
            un = u + s * dt
        un = max(-cap * SIG, min(cap * SIG, un))
        udot = (un - u) / dt; u = un
        # ② force
        Ft = toy.fx_of_kappa(u / SIG)
        c = cfun(v, c0, vlow)
        Fd = c * s if form == "slipvel" else (c * udot if form == "udot" else 0.0)
        F = Ft + Fd
        if clamp:
            lim = MU * toy.g(u / SIG) * FZ
            F = max(-lim, min(lim, F))
        w += dt * (tau - F * R) / J
        v += dt * F / M
        Fs.append(F); Fds.append(F - Ft); vs.append(v)
    return Fs, Fds, vs

print("A) wheelspin 출발 τ 1.0 N·m (μ·Fz 한계 8.5 N), 0.3 s")
for form in ("none", "slipvel", "udot"):
    for clamp in (False, True):
        Fs, Fds, vs = run(1.0, 0.3, form, clamp)
        print(f"   {form:7s} clamp={clamp!s:5s}  최대 F {max(Fs):7.2f} N  최대 감쇠 기여 {max(Fds):7.2f} N  0.1 s 속도 {vs[19]:.3f}  0.3 s 속도 {vs[-1]:.3f}")

print("B) 저속 정상 주행에서의 치우침: v 0.2·0.5·0.8 m/s, 같은 force 를 내는 데 필요한 slip velocity")
for vv in (0.2, 0.5, 0.8):
    # 정상 상태: u = σ·s/|v| (u̇=0) → (나) 감쇠 0. (가) 는 c·s 추가. F_target 3 N 을 내는 s 를 이분법으로
    def F_of(s, form):
        kp = s / vv
        Ft = toy.fx_of_kappa(kp)
        return Ft + (cfun(vv) * s if form == "slipvel" else 0.0)
    for form in ("udot", "slipvel"):
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if F_of(mid, form) < 3.0: lo = mid
            else: hi = mid
        print(f"   v={vv}  {form:7s} 3 N 에 필요한 slip velocity {lo*1000:7.3f} mm/s  (c(v) = {cfun(vv):.1f} N·s/m)")

print("C) 감쇠비 (relaxation 자체 감쇠만, longitudinal ω_n·lateral ω_n)")
wn_x = math.sqrt(170 * KK / SIG); wn_y = math.sqrt(41.5 * (1 / M) / SIG)
print(f"   ω_n longitudinal {wn_x:.0f} rad/s ({wn_x/2/math.pi:.1f} Hz), lateral {wn_y:.0f} rad/s ({wn_y/2/math.pi:.1f} Hz)")
for vv in (0.0, 0.5, 1.0, 2.0, 3.0):
    print(f"   v={vv:.1f} m/s  ζ_long = {vv/(2*SIG*wn_x):.2f}   ζ_lat = {vv/(2*SIG*wn_y):.2f}")
