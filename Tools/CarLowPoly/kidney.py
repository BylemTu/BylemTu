# Rebuilds a BMW kidney grille as a clean low-poly piece from the outline of the original (front view).
import numpy as np
def hull(P):
    P = sorted(map(tuple, P))
    def half(pts):
        h = []
        for p in pts:
            while len(h) >= 2 and np.cross(np.subtract(h[-1], h[-2]), np.subtract(p, h[-2])) <= 0: h.pop()
            h.append(p)
        return h
    lo = half(P); up = half(P[::-1])
    return np.array(lo[:-1] + up[:-1])
def resample(poly, n):
    seg = np.linalg.norm(np.roll(poly, -1, 0) - poly, axis=1); c = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, c[-1], n, endpoint=False)
    return np.array([np.interp(t, c, np.append(poly[:, k], poly[0, k])) for k in range(2)]).T
def build(V, n=14, frame=0.016, depth=0.035, slats=6):
    """V: original kidney vertices (GTA frame, front = +Y). returns verts, faces, mats ('Chrome'/'Black'), facing hints"""
    xz = V[:, [0, 2]]
    H = resample(hull(xz), n)
    ctr = H.mean(0)
    yfront = np.array([V[np.linalg.norm(xz - h, axis=1) < 0.03, 1].max() for h in H])
    verts, faces, mats = [], [], []
    def add_ring(pts2, ys):
        i0 = len(verts); verts.extend([(p[0], y, p[1]) for p, y in zip(pts2, ys)]); return list(range(i0, i0 + len(pts2)))
    inset = ctr + (H - ctr) * (1 - frame / np.linalg.norm(H - ctr, axis=1, keepdims=True))
    O = add_ring(H, yfront); Ob = add_ring(H, yfront - 0.03)
    I = add_ring(inset, yfront - 0.004); B = add_ring(inset, yfront - depth)
    def bridge(a, b, m):
        for i in range(len(a)):
            j = (i + 1) % len(a); faces.append([a[i], a[j], b[j], b[i]]); mats.append(m)
    bridge(O, I, 'Chrome'); bridge(Ob, O, 'Chrome'); bridge(I, B, 'Black')
    faces.append(B[::-1]); mats.append('Black')
    # vertical slats
    xs = np.linspace(inset[:, 0].min(), inset[:, 0].max(), slats + 2)[1:-1]
    for x in xs:
        zs = []
        for i in range(n):
            a, b = inset[i], inset[(i + 1) % n]
            if (a[0] - x) * (b[0] - x) < 0:
                t = (x - a[0]) / (b[0] - a[0]); zs.append(a[1] + t * (b[1] - a[1]))
        if len(zs) < 2: continue
        z0, z1 = min(zs) + 0.004, max(zs) - 0.004
        yf = np.interp(x, H[:, 0][np.argsort(H[:, 0])], yfront[np.argsort(H[:, 0])]) - 0.008
        w = 0.004; i0 = len(verts)
        for dx in (-w, w):
            for z in (z0, z1):
                verts.extend([(x + dx, yf, z), (x + dx, yf - depth + 0.01, z)])
        # order: 0 (-w,z0,f) 1 (-w,z0,b) 2 (-w,z1,f) 3 (-w,z1,b) 4 (+w,z0,f) 5 (+w,z0,b) 6 (+w,z1,f) 7 (+w,z1,b)
        for f in ((0, 4, 6, 2), (0, 2, 3, 1), (4, 5, 7, 6)):
            faces.append([i0 + k for k in f]); mats.append('Chrome')
    verts = np.array(verts)
    # orient: faces should point to +Y (towards the viewer in front) or, for walls, towards the kidney axis/outwards
    out = []
    c3 = np.array([ctr[0], yfront.mean(), ctr[1]])
    for f, m in zip(faces, mats):
        P = verts[f]; n = np.cross(P[1] - P[0], P[2] - P[0])
        fc = P.mean(0); ny = n[1]
        hint = np.array([0, 1.0, 0])
        if abs(ny) < 0.3 * np.linalg.norm(n):      # side wall: inner walls face the centre, outer wall faces away
            radial = fc - c3; radial[1] = 0
            is_outer = f[0] in O or f[0] in Ob
            hint = radial if is_outer else -radial
        out.append(f if np.dot(n, hint) >= 0 else f[::-1])
    return verts, out, mats
