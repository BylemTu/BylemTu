"""Build detail meshes that conform to the body surface (ray-cast onto the
original, uncut lower body). All coordinates in the car frame (x, s, z)."""
import math
import numpy as np
from mathutils import Vector


def bl(p):
    return Vector((p[0], -p[1], p[2]))


def cf(v):
    return np.array([v[0], -v[1], v[2]])


class Surface:
    def __init__(self, bvh):
        self.bvh = bvh

    def cast(self, origin, direction, outward=False):
        """Ray cast; the returned normal faces the ray origin, or along the ray
        when `outward` (casting from inside the body)."""
        loc, nor, idx, dist = self.bvh.ray_cast(bl(origin), bl(direction).normalized())
        if loc is None:
            return None, None
        n = cf(nor)
        if (np.dot(n, direction) > 0) != outward:
            n = -n
        return cf(loc), n

    def front(self, x, z):
        return self.cast((x, 3.0, z), (0, -1, 0))

    def rear(self, x, z):
        return self.cast((x, -3.0, z), (0, 1, 0))

    def side(self, s, z, sign=1.0):
        return self.cast((2.0 * sign, s, z), (-sign, 0, 0))

    def top(self, x, s):
        return self.cast((x, s, 3.0), (0, 0, -1))

    def radial(self, cx, cs, z, theta, front=True):
        """Plan-view radial cast from (cx, cs) at height z. theta=0 -> straight
        forward (front=True) or rearward, theta>0 -> toward +x."""
        d = (math.sin(theta), math.cos(theta) if front else -math.cos(theta), 0.0)
        return self.cast((cx, cs, z), d, outward=True)


def squircle(u, v, n=6.0):
    """Map a point of the square [-1,1]^2 onto a superellipse of exponent n."""
    m = max(abs(u), abs(v))
    if m < 1e-9:
        return 0.0, 0.0
    du, dv = u / m, v / m
    k = (abs(du) ** n + abs(dv) ** n) ** (1.0 / n)
    return m * du / k, m * dv / k


def patch(proj, a0, a1, b0, b1, nu=12, nv=6, n_sq=None, offset=0.004, depth=0.03,
          back=True, mat_fn=None, inset_border=None):
    """Conformal patch over the param rectangle [a0,a1]x[b0,b1].

    proj(a, b) -> (point, normal) on the surface.
    Returns verts, faces, face material ids.
    Front face at +offset along the normal, side walls going back to -depth,
    optional back cap. mat_fn(a, b) -> material id for front faces (wall/back=0).
    """
    us = np.linspace(-1, 1, nu + 1)
    vs = np.linspace(-1, 1, nv + 1)
    V, F, Mt = [], [], []
    grid = np.zeros((nu + 1, nv + 1), int)
    base = {}
    for i, u in enumerate(us):
        for j, v in enumerate(vs):
            uu, vv = squircle(u, v, n_sq) if n_sq else (u, v)
            a = a0 + (a1 - a0) * (uu + 1) / 2
            b = b0 + (b1 - b0) * (vv + 1) / 2
            p, n = proj(a, b)
            if p is None:
                raise RuntimeError(f"projection miss at {a:.3f},{b:.3f}")
            base[(i, j)] = (p, n)
            grid[i, j] = len(V)
            V.append(p + n * offset)
    for i in range(nu):
        for j in range(nv):
            F.append((grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]))
            if mat_fn:
                uu, vv = (us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2
                if n_sq:
                    uu, vv = squircle(uu, vv, n_sq)
                Mt.append(mat_fn(a0 + (a1 - a0) * (uu + 1) / 2, b0 + (b1 - b0) * (vv + 1) / 2))
            else:
                Mt.append(0)
    # boundary loop (counter-clockwise in param space)
    loop = [(i, 0) for i in range(nu)] + [(nu, j) for j in range(nv)] + \
        [(i, nv) for i in range(nu, 0, -1)] + [(0, j) for j in range(nv, 0, -1)]
    if depth:
        back_ids = []
        for key in loop:
            p, n = base[key]
            back_ids.append(len(V))
            V.append(p - n * depth)
        L = len(loop)
        for k in range(L):
            a, b = grid[loop[k]], grid[loop[(k + 1) % L]]
            F.append((b, a, back_ids[k], back_ids[(k + 1) % L]))
            Mt.append(-1)
        if back:
            F.append(tuple(back_ids[::-1]))
            Mt.append(-1)
    return np.array(V), F, Mt


def combine(*meshes):
    V, F, Mt = [], [], []
    for mv, mf, mm in meshes:
        off = len(V)
        V += list(mv)
        F += [tuple(i + off for i in f) for f in mf]
        Mt += list(mm)
    return np.array(V), F, Mt


def remap(Mt, wall):
    return [wall if m == -1 else m for m in Mt]


def lathe_at(profile, center, axis, segments=32, cap=False, up=(0, 0, 1)):
    """Revolve (r, h) profile around `axis` through `center` (car frame)."""
    axis = np.asarray(axis, float)
    axis /= np.linalg.norm(axis)
    up = np.asarray(up, float)
    e1 = np.cross(axis, up)
    if np.linalg.norm(e1) < 1e-6:
        e1 = np.cross(axis, (1, 0, 0))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    prof = np.asarray(profile, float)
    n = len(prof)
    V, F = [], []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        d = e1 * math.cos(a) + e2 * math.sin(a)
        for r, h in prof:
            V.append(np.asarray(center) + axis * h + d * r)
    for k in range(segments):
        k2 = (k + 1) % segments
        for j in range(n - 1):
            F.append((k * n + j, k * n + j + 1, k2 * n + j + 1, k2 * n + j))
    if cap:
        F.append(tuple(k * n + n - 1 for k in range(segments)))
    return np.array(V), F, [0] * len(F)


def box(center, size, rot_z=0.0, rot_x=0.0):
    """Box in car frame; rotations in radians about z then x (car frame)."""
    c = np.asarray(center, float)
    hx, hs, hz = np.asarray(size, float) / 2
    V = []
    for dx in (-1, 1):
        for ds in (-1, 1):
            for dz in (-1, 1):
                p = np.array([dx * hx, ds * hs, dz * hz])
                ca, sa = math.cos(rot_x), math.sin(rot_x)
                p = np.array([p[0], ca * p[1] - sa * p[2], sa * p[1] + ca * p[2]])
                cz, sz = math.cos(rot_z), math.sin(rot_z)
                p = np.array([cz * p[0] - sz * p[1], sz * p[0] + cz * p[1], p[2]])
                V.append(c + p)
    F = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return np.array(V), F, [0] * 6


def loft(sections, closed_ring=True, cap_start=True, cap_end=True):
    """Loft a list of rings (each (n,3) array)."""
    n = len(sections[0])
    V = np.vstack(sections)
    F = []
    for a in range(len(sections) - 1):
        for k in range(n if closed_ring else n - 1):
            k2 = (k + 1) % n
            F.append((a * n + k, a * n + k2, (a + 1) * n + k2, (a + 1) * n + k))
    if cap_start:
        F.append(tuple(range(n))[::-1])
    if cap_end:
        F.append(tuple((len(sections) - 1) * n + k for k in range(n)))
    return V, F, [0] * len(F)
