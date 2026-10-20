"""parallel(지금 합의한 식) vs series(Kelvin-Voigt carcass 가 contact 와 직렬) 비교."""
import math, toy
R, J, M, KK, FZ, MU = toy.R, toy.J, toy.M, toy.KK, toy.FZ, toy.MU
SIG = 0.02; C = 170.0

def run(tau, T, model, c, w0=0.0, v0=0.0, dt=0.005, cap=1.0):
    w, v, u = w0, v0, 0.0
    Fs, vs = [], []
    for _ in range(int(round(T / dt))):
        s = w * R - v
        beta = abs(v) * c / C if model == "series" else 0.0
        a = abs(v) / SIG / (1 + beta); se = s / (1 + beta)
        if a > 1e-9:
            e = math.exp(-a * dt); un = u * e + se * (1 - e) / a
        else:
            un = u + se * dt
        un = max(-cap * SIG, min(cap * SIG, un))
        udot = (un - u) / dt; u = un
        F = toy.fx_of_kappa(u / SIG) + c * udot
        lim = MU * toy.g(u / SIG) * FZ
        F = max(-lim, min(lim, F))
        w += dt * (tau - F * R) / J; v += dt * F / M
        Fs.append(F); vs.append(v)
    return Fs, vs

def settle_time(Fs, dt=0.005, tol=0.05):
    # |F| 가 tol 아래로 들어와 계속 머무는 첫 시각
    for i in range(len(Fs)):
        if all(abs(x) < tol for x in Fs[i:]):
            return i * dt
    return float("nan")

wn = math.sqrt(C * KK / SIG)
print(f"ω_n = {wn:.1f} rad/s. 감쇠비 ζ_c = c·k/(2ω_n): c 10 → {10*KK/(2*wn):.3f}, c 20 → {20*KK/(2*wn):.3f}, c 40 → {40*KK/(2*wn):.3f}")
print(f"손실계수 η = 2ζ: c 10 → {2*10*KK/(2*wn):.2f}, c 20 → {2*20*KK/(2*wn):.2f}, c 40 → {2*40*KK/(2*wn):.2f}")
print("1) 정지 유지(바퀴만 0.05 m/s) — |F| < 0.05 N 로 가라앉는 시간")
for c in (0.0, 10.0, 20.0, 40.0):
    Fs, _ = run(0.0, 1.0, "parallel", c, w0=0.05 / R)
    print(f"   c={c:4.0f}  {settle_time(Fs)*1000:7.1f} ms")
print("2) 주행 중 transient (slip velocity 0.05 m/s, τ 0) — 최대 |F|, 30 ms 뒤 최대 |F|")
for v0 in (1.5, 3.0):
    for model in ("parallel", "series"):
        for c in (10.0, 40.0):
            Fs, _ = run(0.0, 0.15, model, c, w0=(v0 + 0.05) / R, v0=v0)
            print(f"   v0={v0} {model:8s} c={c:4.0f}  최대 |F| {max(abs(x) for x in Fs):.3f}  30 ms 뒤 {max(abs(x) for x in Fs[6:]):.4f}  (1+|v|c/C = {1+v0*c/C:.2f})")
print("3) 출발 τ 0.4 — 0.3 s 속도 / 최대 F")
for model in ("parallel", "series"):
    for c in (10.0, 40.0):
        Fs, vs = run(0.4, 0.3, model, c)
        print(f"   {model:8s} c={c:4.0f}  최대 F {max(Fs):.2f} N  0.3 s 속도 {vs[-1]:.4f}")
