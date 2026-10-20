import math
M = 3.47 / 4; J = 1.0903e-3; R = 0.0508; FZ = 8.5; MU = 1.0; C = 20 * FZ
PTS = ((0.0, 1.0), (0.15, 1.0), (1.0, 0.8))
KK = R * R / J + 1 / M
def g(k):
    (x0, y0), (x1, y1), (x2, y2) = PTS; k = abs(k)
    if k < x1: return y0 + (y1 - y0) * (k - x0) / (x1 - x0)
    if k < x2: return y1 + (y2 - y1) * (k - x1) / (x2 - x1)
    return y2
def f1(K): K = min(K, 3.0); return K - K*K/3 + K**3/27
def fx_of_kappa(k):
    if k == 0: return 0.0
    m = MU * g(k); return math.copysign(m * FZ * f1(C * abs(k) / (m * FZ)), k)
def F_slip(s, v, eps): return fx_of_kappa(s / (abs(v) + eps))

def run(method, tau=0.4, T=0.4, dt=0.005, eps=0.1, sigma=0.02, vth=2.0, cdamp=50.0, rec_dt=0.0025):
    w = 0.0; v = 0.0; u = 0.0; t = 0.0; out = []; next_rec = 0.0
    n = int(round(T / dt))
    for i in range(n):
        s = w * R - v
        if method == "explicit":
            F = F_slip(s, v, eps)
        elif method == "implicit":
            F0 = F_slip(s, v, eps); h = 1e-6
            D = (F_slip(s + h, v, eps) - F_slip(s - h, v, eps)) / (2 * h)
            ds = dt * (R * tau / J - F0 * KK) / (1 + dt * D * KK)
            F = F0 + D * ds
        elif method == "relax":
            F = fx_of_kappa(u / sigma)
        elif method == "blend":
            wgt = min(abs(v) / vth, 1.0)
            Fd = max(-MU * FZ, min(MU * FZ, cdamp * s))
            F = wgt * F_slip(s, v, eps) + (1 - wgt) * Fd
        w += dt * (tau - F * R) / J
        v += dt * F / M
        if method == "relax":
            s2 = w * R - v
            u += dt * (s2 - abs(v) * u / sigma)
        t += dt
        if t >= next_rec - 1e-12:
            out.append((t, F, v, w * R)); next_rec += rec_dt
    return out

if __name__ == "__main__":
    ref = run("explicit", dt=1e-6, eps=0.05)
    print("ref final", ref[-1])
    for name, kw in [("eps0.1", dict(method="explicit", eps=0.1)), ("eps2.0", dict(method="explicit", eps=2.0)),
                     ("implicit", dict(method="implicit", eps=0.1)), ("dt1.25 eps0.75", dict(method="explicit", dt=0.00125, eps=0.75)),
                     ("relax", dict(method="relax")), ("blend", dict(method="blend"))]:
        o = run(**kw)
        Fs = [x[1] for x in o]
        print(f"{name:16s} final t={o[-1][0]:.3f} F={o[-1][1]:+.3f} v={o[-1][2]:.4f} wr={o[-1][3]:.4f}  Fmin={min(Fs):+.2f} Fmax={max(Fs):+.2f}")
