# Procedural low-poly wheel (tyre + 5 double-spoke rim + disc + caliper). Axis = X, outer face towards -X.
# Every face is oriented explicitly (no normal recalculation), so it renders correctly with back-face culling.
import numpy as np
S = 28
def build(R=0.36, W=0.30):
    V, F, M = [], [], []
    def orient(f, hint):
        p = np.array([V[i] for i in f]); c = p.mean(0)
        n = np.cross(p[1] - p[0], p[2] - p[0])
        if len(f) == 4: n += np.cross(p[2] - p[0], p[3] - p[0])
        h = hint(c) if callable(hint) else np.asarray(hint, float)
        return f if np.dot(n, h) >= 0 else f[::-1]
    def add(f, mat, hint):
        F.append(orient(f, hint)); M.append(mat)
    def ring(x, r, n=S, a0=0.0):
        i0 = len(V)
        for i in range(n):
            a = a0 + 2 * np.pi * i / n
            V.append((x, r * np.cos(a), r * np.sin(a)))
        return list(range(i0, i0 + n))
    def bridge(a, b, mat, hint):
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            add([a[i], a[j], b[j], b[i]], mat, hint)
    def fan(a, x, mat, hint):
        c = len(V); V.append((x, 0, 0))
        for i in range(len(a)):
            add([a[i], a[(i + 1) % len(a)], c], mat, hint)
    radial_out = lambda c: np.array([0, c[1], c[2]])
    radial_in = lambda c: -radial_out(c)
    h = W / 2; rr = R * 0.73
    tube = lambda c: c - np.concatenate([[0], radial_out(c)[1:] / (np.linalg.norm(c[1:]) + 1e-9) * R * 0.8])
    prof = [(-h + 0.005, rr + 0.004, 'sidewall'), (-h, R * 0.86, 'sidewall'), (-h + 0.02, R * 0.97, 'tire'),
            (-h + 0.05, R, 'tire'), (h - 0.05, R, 'tire'), (h - 0.02, R * 0.97, 'sidewall'), (h, R * 0.86, 'sidewall'), (h - 0.005, rr + 0.004, 'black')]
    rings = [ring(x, r) for x, r, _ in prof]
    for i in range(len(rings) - 1):
        bridge(rings[i], rings[i + 1], prof[i][2], tube)
    fan(rings[-1], h - 0.005, 'black', (1, 0, 0))              # inner closing disc
    lip1 = ring(-h + 0.012, rr - 0.012); bar = ring(-h + 0.05, rr - 0.018)
    bridge(rings[0], lip1, 'lip', lambda c: np.array([-1, 0, 0]) + 0.3 * radial_out(c))
    bridge(lip1, bar, 'hub', lambda c: radial_in(c) + np.array([-0.2, 0, 0]))
    back = ring(0.0, rr - 0.018)
    bridge(bar, back, 'hub', radial_in); fan(back, 0.0, 'disc', (-1, 0, 0))
    d0 = ring(-h + 0.07, R * 0.52, 16); fan(d0, -h + 0.07, 'disc', (-1, 0, 0))    # brake disc
    hb0 = ring(-h + 0.045, R * 0.16, 10, np.pi / 10); hb1 = ring(-h + 0.022, R * 0.15, 10, np.pi / 10)
    bridge(hb0, hb1, 'rim', radial_out); fan(hb1, -h + 0.018, 'hub', (-1, 0, 0))
    for s in range(10):                                        # 5 double spokes
        a = 2 * np.pi * (s // 2) / 5 + (0.16 if s % 2 else -0.16)
        pa = np.array([0, -np.sin(a), np.cos(a)]); da = np.array([0, np.cos(a), np.sin(a)])
        i0 = len(V)
        for r, wdt, x in ((R * 0.13, 0.022, -h + 0.03), (rr - 0.02, 0.016, -h + 0.02)):
            for side in (-1, 1):
                for dx in (0.0, 0.028):
                    p = da * r + pa * wdt * side; p[0] = x + dx; V.append(tuple(p))
        q = lambda *k: [i0 + j for j in k]
        add(q(0, 2, 6, 4), 'rim', (-1, 0, 0)); add(q(0, 4, 5, 1), 'rim', -pa); add(q(2, 3, 7, 6), 'rim', pa)
    cx0, cx1 = -h + 0.075, -h + 0.13; ang = np.radians(120)    # caliper
    i0 = len(V)
    for a in (ang - 0.35, ang + 0.35):
        for r in (R * 0.36, R * 0.56):
            for x in (cx0, cx1):
                V.append((x, r * np.cos(a), r * np.sin(a)))
    ctr = np.mean(V[i0:], axis=0)
    for f in ((0, 2, 6, 4), (0, 4, 5, 1), (2, 3, 7, 6), (0, 1, 3, 2), (4, 6, 7, 5)):
        add([i0 + j for j in f], 'caliper', lambda c, ctr=ctr: c - ctr)
    return np.array(V, float), F, M
