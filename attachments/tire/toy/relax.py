import math, toy
R, J, M, KK = toy.R, toy.J, toy.M, toy.KK
FZ, MU = toy.FZ, toy.MU

def damp_coef(v, c0, vlow):
    av = abs(v)
    return c0 * 0.5 * (1 + math.cos(math.pi * av / vlow)) if av < vlow else 0.0

def run(tau, w0, v0, T, sigma=0.02, order="symplectic", update="euler", damp="none", c0=40.0, vlow=1.0,
        dt=0.005, kcap=None):
    w, v, u = w0, v0, 0.0
    # 시작 상태가 정상 상태라면 u 를 그 값으로(출발 시 0)
    Fs, us = [], []
    udot = 0.0
    for _ in range(int(round(T / dt))):
        s = w * R - v
        if order == "explicit":  # u 를 먼저(옛 속도로) 갱신 → 그 다음 힘
            udot = s - abs(v) * u / sigma
            u = u + dt * udot
        kp = u / sigma
        if kcap is not None:
            kp = max(-kcap, min(kcap, kp))
        F = toy.fx_of_kappa(kp)
        if damp == "slipvel":
            F += damp_coef(v, c0, vlow) * s
        elif damp == "udot":
            F += damp_coef(v, c0, vlow) * (s - abs(v) * u / sigma)
        w += dt * (tau - F * R) / J
        v += dt * F / M
        if order == "symplectic":  # 새 속도로 u 갱신
            s2 = w * R - v
            a = abs(v) / sigma
            if update == "exp" and a > 1e-9:
                e = math.exp(-a * dt)
                u = u * e + s2 * (1 - e) / a
            else:
                u = u + dt * (s2 - a * u)
        Fs.append(F); us.append(u)
    return Fs, v, w * R

def tail(Fs, n=20): return max(abs(x) for x in Fs[-n:])
def maxabs(Fs): return max(abs(x) for x in Fs)

print("1) 갱신 순서 — 정지 유지(τ 0, 바퀴만 0.05 m/s), 감쇠 없음, 0.3 s 뒤 |F|")
for order in ("explicit", "symplectic"):
    Fs, v, wr = run(0.0, 0.05 / R, 0.0, 0.3, order=order)
    print(f"   {order:10s} 마지막 |F| = {tail(Fs):.3e} N   최대 |F| = {maxabs(Fs):.2f}")

print("2) 고속 — 5 m/s 순항, 바퀴 slip velocity 0.1 m/s 에서 시작, τ 0, 0.2 s")
for sigma in (0.02, 0.01):
    for update in ("euler", "exp"):
        Fs, v, wr = run(0.0, (5.0 + 0.1) / R, 5.0, 0.2, sigma=sigma, update=update)
        print(f"   σ={sigma*100:.0f} cm  {update:5s}  최대 |F| = {maxabs(Fs):9.3e} N   마지막 |F| = {tail(Fs):.3e}   dt·|v|/σ = {0.005*5/sigma:.2f}")

print("3) 감쇠항 형태 — 출발(τ 0.4) 0.4 s, 정지 유지 0.3 s, exp 갱신, σ 2 cm, c0 40 N·s/m, v_low 1 m/s")
ref_F = 0.4 * R / J / KK
for damp in ("none", "slipvel", "udot"):
    Fs, v, wr = run(0.4, 0.0, 0.0, 0.4, update="exp", damp=damp)
    # 출발 중 0.1~0.3 s 구간 평균 힘 (정상 상태는 τ·r/J / k = %.3f N)
    mid = Fs[20:60]
    Fs2, _, _ = run(0.0, 0.05 / R, 0.0, 0.3, update="exp", damp=damp)
    print(f"   {damp:8s} 출발: 최대 {max(Fs):.2f} N, 0.1~0.3 s 평균 {sum(mid)/len(mid):.3f} N (정상 상태 {ref_F:.3f}), 0.4 s 속도 {v:.4f} m/s"
          f" | 정지 유지 마지막 |F| {tail(Fs2):.3e} N")
