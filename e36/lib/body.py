"""Procedural E36 body surfaces: lower body shell and greenhouse.

Both surfaces are generated as clean quad grids ("box" topology: floor strip,
two side columns, top strip, plus Coons-patch end caps) so they shade well and
can later be cut into panels with thin boolean slab cutters.
Everything here returns plain numpy geometry in the car frame (x, s, z).
"""
import math
import numpy as np
from . import dims as D
from .curves import smoothstep, lerp

K_STRIP = 8   # segments across floor / top strip


# ------------------------------------------------------------------ lower body
def side_rows(s):
    """Half cross-section of the body side at station s: list of (z, inset)."""
    zb, zd = D.Z_BOTTOM(s), D.Z_DECK(s)
    zc = min(D.Z_CREASE(s), zd - 0.06)
    zr = min(D.Z_RUB, zc - 0.09)
    zs = zb + 0.10
    a = zc - 0.015
    return [
        (zb, 0.080), (zb + 0.012, 0.045), (zb + 0.045, 0.020),
        (zs, 0.011), (lerp(zs, zr, 0.55), 0.004), (zr, 0.0),
        (lerp(zr, a, 0.5), 0.004), (a, 0.0095), (zc, 0.0075),
        (zc + 0.013, 0.0115), (lerp(zc, zd, 0.55), 0.021), (zd - 0.012, 0.040), (zd, 0.057),
    ]


N_ROWS = len(side_rows(0.0))


def ring_nominal(s):
    """Closed ring (list of (x, z)) at station s, plus per-vertex kind tags.

    Order: floor left->right, right side up, top strip right->left, left side down.
    kind: 0 floor, 1 side, 2 top
    """
    rows = side_rows(s)
    w = float(D.W_PLAN(s))
    side = [(w - ins, z) for z, ins in rows]
    xb, zb = side[0]
    xt, zt = side[-1]
    crown = float(D.Z_CROWN(s))
    pts, kind, u = [], [], []
    for i in range(K_STRIP + 1):                      # floor incl. corners
        uu = -1 + 2 * i / K_STRIP
        pts.append((xb * uu, zb)); kind.append(0 if 0 < i < K_STRIP else 1); u.append(uu)
    for j in range(1, N_ROWS):                        # right side
        pts.append(side[j]); kind.append(1); u.append(1.0)
    for i in range(K_STRIP - 1, 0, -1):               # top strip (interior)
        uu = -1 + 2 * i / K_STRIP
        pts.append((xt * uu, zt + crown * (1 - uu * uu))); kind.append(2); u.append(uu)
    for j in range(N_ROWS - 1, 0, -1):                # left side
        x, z = side[j]
        pts.append((-x, z)); kind.append(1); u.append(-1.0)
    return np.array(pts), np.array(kind), np.array(u)


def lower_body(raw=False, with_kind=False):
    """Build the lower body shell. Returns verts (N,3 in x,s,z), faces, face_tags.

    face tag: 0 paint, 1 underside.
    """
    # stations of the constant-section middle part
    mid = np.arange(-1.93, 1.735, 0.05)
    rings = []
    ring_kind = None

    def end_ring(front, t):
        if front:
            B, rho, phim = D.FRONT_BULGE, D.FRONT_RHO, math.radians(D.FRONT_PHI)
            S_end, sign = D.S_FRONT_Z, 1.0
        else:
            B, rho, phim = D.REAR_BULGE, D.REAR_RHO, math.radians(D.REAR_PHI)
            S_end, sign = D.S_REAR_Z, -1.0
        phi = t * phim

        def s_c(z):
            return S_end(z) - sign * (B + rho * math.sin(phim))

        s_nom = float(s_c(0.5)) + sign * rho * math.sin(phi)
        pts, kind, u = ring_nominal(s_nom)
        out = np.zeros((len(pts), 3))
        xs_nom = pts[:, 0].copy()
        side_x = np.abs(xs_nom[K_STRIP])  # right-bottom corner
        for k, ((x, z), kd, uu) in enumerate(zip(pts, kind, u)):
            base_s = float(s_c(z)) + sign * rho * math.sin(phi)
            if kd == 1:
                xn = math.copysign(abs(x) - rho * (1 - math.cos(phi)), x)
                out[k] = (xn, base_s, z)
            else:
                # strip vertex: scale x with the side, add plan bulge
                zz = z
                ref = abs(pts[K_STRIP][0]) if kd == 0 else abs(pts[K_STRIP + N_ROWS - 1][0])
                scale = (ref - rho * (1 - math.cos(phi))) / ref
                bulge = B * (1 - uu * uu) * float(smoothstep(0.0, 1.0, t))
                out[k] = (x * scale, base_s + sign * bulge, zz)
        return out, kind

    n_end = 9
    rear_rings = [end_ring(False, 1 - i / (n_end - 1)) for i in range(n_end)]
    front_rings = [end_ring(True, i / (n_end - 1)) for i in range(n_end)]
    mid_rings = []
    for s in mid:
        pts, kind, _ = ring_nominal(s)
        mid_rings.append((np.column_stack([pts[:, 0], np.full(len(pts), s), pts[:, 1]]), kind))
    all_rings = rear_rings + mid_rings + front_rings
    ring_kind = all_rings[0][1]
    nr = len(ring_kind)
    verts = [r[0] for r in all_rings]
    V = np.vstack(verts)
    faces, tags = [], []
    for a in range(len(all_rings) - 1):
        o0, o1 = a * nr, (a + 1) * nr
        for k in range(nr):
            k2 = (k + 1) % nr
            faces.append((o0 + k, o0 + k2, o1 + k2, o1 + k))
            tags.append(1 if (ring_kind[k] == 0 or ring_kind[k2] == 0) and k < K_STRIP else 0)
    # caps (Coons patches spanning the end rings)
    K, R = K_STRIP, N_ROWS

    def rid(kind, a):
        if kind == 'b':
            return a
        if kind == 'r':
            return K + a
        if kind == 't':
            if a == K:
                return K + R - 1
            if a == 0:
                return 2 * K + R - 1
            return K + R + (K - 1 - a)
        if kind == 'l':
            return 0 if a == 0 else 2 * K + R - 1 + (R - 1 - a)

    V = list(V)
    for ri, flip in ((0, True), (len(all_rings) - 1, False)):
        off = ri * nr
        P = lambda kind, a: np.asarray(V[off + rid(kind, a)])
        idx = np.zeros((K + 1, R), int)
        for i in range(K + 1):
            idx[i, 0] = off + rid('b', i)
            idx[i, R - 1] = off + rid('t', i)
        for j in range(R):
            idx[0, j] = off + rid('l', j)
            idx[K, j] = off + rid('r', j)
        zl = np.array([P('l', j)[2] for j in range(R)])
        v = (zl - zl[0]) / (zl[-1] - zl[0])
        c00, c10, c01, c11 = P('b', 0), P('b', K), P('t', 0), P('t', K)
        for i in range(1, K):
            uu = i / K
            for j in range(1, R - 1):
                vv = v[j]
                p = ((1 - vv) * P('b', i) + vv * P('t', i) + (1 - uu) * P('l', j) + uu * P('r', j)
                     - ((1 - uu) * (1 - vv) * c00 + uu * (1 - vv) * c10
                        + (1 - uu) * vv * c01 + uu * vv * c11))
                idx[i, j] = len(V)
                V.append(p)
        for i in range(K):
            for j in range(R - 1):
                f = (idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1])
                faces.append(f if flip else f[::-1])
                tags.append(0)
    V = np.array(V)
    nring = len(all_rings) * nr
    kind = np.concatenate([np.tile(ring_kind, len(all_rings)), np.full(len(V) - nring, 3)])
    if with_kind:
        return V, faces, tags, kind
    return V, faces, tags


# ------------------------------------------------------------------ greenhouse
N_GH_ROWS = 13
GH_T = np.array([-0.1, 0.0, 0.035, 0.07, 0.16, 0.30, 0.45, 0.60, 0.74, 0.86, 0.93, 0.975, 1.0])


def gh_frame(s):
    zb = float(D.Z_DECK(s)) - 0.002
    zt = float(D.Z_TOP(s))
    crown = float(D.ROOF_CROWN(s))
    zre = max(zt - crown, zb + 0.004)
    return zb, zre, zt, float(D.X_BELT(s)), float(D.X_ROOF(s))


def gh_wrap(s, x):
    x_ref = 0.72
    return -float(D.WRAP_F(s)) * (x / x_ref) ** 2 * (s > 0.0) + \
        float(D.WRAP_R(s)) * (x / x_ref) ** 2 * (s < -1.0)


def gh_side(s, t, side=1.0):
    """Point on greenhouse side at nominal station s, height fraction t (0 belt, 1 roof edge)."""
    zb, zre, zt, xb, xr = gh_frame(s)
    if t < 0:      # rubber flange that covers the cut edge of the body at the belt
        w = 0.05 * float(np.clip((s + 1.45) / 0.15, 0.0, 1.0))
        x = (xb + w) * side
        return np.array([x, s + gh_wrap(s, x), zb - 0.006])
    z = lerp(zb, zre, t)
    # glass is slightly bowed outward; the rail rounds over at the top
    x = lerp(xb, xr, t) + 0.012 * math.sin(math.pi * min(t / 0.95, 1.0))
    x *= side
    return np.array([x, s + gh_wrap(s, x), z])


def gh_top(s, u):
    """Point on greenhouse top strip, u in [-1, 1] across."""
    zb, zre, zt, xb, xr = gh_frame(s)
    crown = zt - zre
    x = xr * u
    z = zt - crown * u * u
    return np.array([x, s + gh_wrap(s, x), z])


def gh_stations():
    base = np.linspace(D.GH_S0, D.GH_S1, 30)
    extra = [D.S_ROOF_F, D.S_ROOF_R, -0.33, D.S_RW, D.S_COWL,
             -0.295 + 0.012, -1.10, 0.55 - 0.012, -0.955 + 0.012, -0.405 - 0.012, -0.985 - 0.012]
    return np.unique(np.round(np.concatenate([base, extra]), 5))


def greenhouse():
    """Open greenhouse surface (bottom is buried in the deck).

    Returns verts, faces, per-face (s_center, zone, t_center/u_center) info.
    zone: 1 = side right(+x), -1 = side left, 2 = top
    """
    st = gh_stations()
    K = 10
    ring_n = N_GH_ROWS * 2 + (K - 1)
    V, F, info = [], [], []
    for s in st:
        for j in range(N_GH_ROWS):                      # left side bottom->top
            V.append(gh_side(s, GH_T[j], 1.0))
        for i in range(1, K):                          # top strip +x -> -x
            V.append(gh_top(s, 1 - 2 * i / K))
        for j in range(N_GH_ROWS - 1, -1, -1):        # right side top->bottom
            V.append(gh_side(s, GH_T[j], -1.0))
    for a in range(len(st) - 1):
        o0, o1 = a * ring_n, (a + 1) * ring_n
        sc = 0.5 * (st[a] + st[a + 1])
        for k in range(ring_n - 1):
            F.append((o0 + k, o1 + k, o1 + k + 1, o0 + k + 1))
            if k < N_GH_ROWS - 1:
                info.append((sc, 1, 0.5 * (GH_T[k] + GH_T[k + 1]), st[a], st[a + 1]))
            elif k >= N_GH_ROWS - 1 + K:
                jj = ring_n - 1 - k
                info.append((sc, -1, 0.5 * (GH_T[jj] + GH_T[jj - 1]), st[a], st[a + 1]))
            else:
                i = k - (N_GH_ROWS - 1)
                info.append((sc, 2, 1 - 2 * (i + 0.5) / K, st[a], st[a + 1]))
    return np.array(V), F, info
