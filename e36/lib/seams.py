"""Panel seams: thin slab cutters (boolean DIFFERENCE) that split the body skin
into swappable panels with a real, visible shut-line gap."""
import math
import numpy as np
from . import dims as D, meshkit as mk, materials as M

GAP = 0.0045  # 4.5 mm shut lines


def _ribbon(poly2d, gap):
    """Offset an open 2D polyline to a closed ribbon polygon of width gap."""
    p = np.asarray(poly2d, float)
    # extend ends a bit so ribbons overlap at T-junctions
    d0 = p[1] - p[0]; d0 /= np.linalg.norm(d0)
    d1 = p[-1] - p[-2]; d1 /= np.linalg.norm(d1)
    p = np.vstack([p[0] - d0 * gap * 2, p[1:-1], p[-1] + d1 * gap * 2])
    n = len(p)
    normals = []
    for i in range(n):
        a = p[max(i - 1, 0)]
        b = p[min(i + 1, n - 1)]
        t = b - a; t /= np.linalg.norm(t)
        normals.append(np.array([-t[1], t[0]]))
    normals = np.array(normals)
    left = p + normals * gap / 2
    right = p - normals * gap / 2
    return np.vstack([left, right[::-1]])


def _prism(poly, axis, lo, hi):
    """Extrude a closed 2D polygon along a car-frame axis. Returns verts (car frame), faces."""
    n = len(poly)
    V = []
    for h in (lo, hi):
        for a, b in poly:
            if axis == 'x':      # poly in (s, z)
                V.append((h, a, b))
            elif axis == 'z':    # poly in (x, s)
                V.append((a, b, h))
            else:                # axis 's', poly in (x, z)
                V.append((a, h, b))
    F = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j, n + i))
    return np.array(V), F


def side_seam(poly_sz, x0=0.60, x1=1.0, both=True):
    out = []
    rib = _ribbon(poly_sz, GAP)
    for sgn in ((1, -1) if both else (1,)):
        lo, hi = sorted((x0 * sgn, x1 * sgn))
        out.append(_prism(rib, 'x', lo, hi))
    return out


def plan_seam(poly_xs, z0, z1, mirror=True):
    out = [_prism(_ribbon(poly_xs, GAP), 'z', z0, z1)]
    if mirror:
        out.append(_prism(_ribbon([(-x, s) for x, s in poly_xs], GAP), 'z', z0, z1))
    return out


def face_seam(poly_xz, s0, s1, mirror=True):
    out = [_prism(_ribbon(poly_xz, GAP), 's', s0, s1)]
    if mirror:
        out.append(_prism(_ribbon([(-x, z) for x, z in poly_xz], GAP), 's', s0, s1))
    return out


def arc(cs, cz, r, a0, a1, n=24):
    return [(cs + r * math.cos(a), cz + r * math.sin(a)) for a in np.linspace(a0, a1, n)]


S_DOOR_F = 0.745
S_DOOR_B = -0.33
S_DOOR_R = -1.345
Z_SILL = 0.305
Z_BUMPER_F = 0.458
Z_BUMPER_R = 0.655
Z_HOOD_FRONT = 0.603
S_HOOD_REAR = 0.93
S_TRUNK_FRONT = -1.875
X_NOSE = 0.745


def all_seams():
    cuts = []
    zc = D.arch_z(False)
    # doors
    cuts += side_seam([(S_DOOR_F - 0.012, Z_SILL - 0.02), (S_DOOR_F - 0.004, 0.55),
                       (S_DOOR_F, 0.80), (S_DOOR_F, 1.02)], 0.60)
    cuts += side_seam([(S_DOOR_B, Z_SILL - 0.02), (S_DOOR_B + 0.004, 0.70), (S_DOOR_B + 0.006, 1.02)], 0.62)
    r = D.ARCH_R + 0.035
    zt = zc + math.sqrt(r * r - (S_DOOR_R - D.S_RA) ** 2)
    rear_edge = [(S_DOOR_R, 1.02), (S_DOOR_R, zt + 0.01)] + \
        arc(D.S_RA, zc, r, math.pi / 2 - math.asin((S_DOOR_R - D.S_RA) / r),
            -math.asin((zc - Z_SILL + 0.02) / r), 20)
    cuts += side_seam(rear_edge, 0.62)
    # sill line under the doors and the front fender
    cuts += side_seam([(-1.0, Z_SILL), (D.S_FA - D.ARCH_R + 0.01, Z_SILL)], 0.50)
    # bumpers: horizontal top line + cut through the floor just behind them
    cuts.append(mk_box(0, 1.55, 2.4, Z_BUMPER_F))
    cuts.append(_prism([(-1.0, 0.10), (1.0, 0.10), (1.0, 0.32), (-1.0, 0.32)], 's',
                       D.S_FA + D.ARCH_R - 0.03, D.S_FA + D.ARCH_R - 0.03 + GAP))
    cuts.append(mk_box(0, -2.6, -1.45, Z_BUMPER_R))
    cuts.append(_prism([(-1.0, 0.10), (1.0, 0.10), (1.0, 0.36), (-1.0, 0.36)], 's',
                       D.S_RA - D.ARCH_R + 0.03 - GAP, D.S_RA - D.ARCH_R + 0.03))
    # hood: side lines on top, rear line at the cowl, front line above the lamps
    hood_edge = [(0.625, 0.70), (0.628, S_HOOD_REAR), (0.645, 1.35), (0.672, 1.80), (0.69, 2.05), (0.70, 2.3)]
    cuts += plan_seam(hood_edge, 0.56, 1.0)
    cuts.append(_prism([(-0.63, 0.76), (0.63, 0.76), (0.63, 1.0), (-0.63, 1.0)], 's',
                       S_HOOD_REAR, S_HOOD_REAR + GAP))
    cuts.append(_prism([(-0.76, Z_HOOD_FRONT), (-0.76, Z_HOOD_FRONT + GAP), (0.76, Z_HOOD_FRONT + GAP),
                        (0.76, Z_HOOD_FRONT)], 's', 1.85, 2.4))
    # nose panel vs fender (lamp band corners)
    cuts += face_seam([(X_NOSE, Z_BUMPER_F - 0.01), (X_NOSE - 0.02, Z_HOOD_FRONT + 0.03)], 1.80, 2.4)
    # trunk lid: top side lines, front line, rear face outline down to the bumper
    trunk_edge = [(0.605, -1.70), (0.61, -2.0), (0.605, -2.5)]
    cuts += plan_seam(trunk_edge, 0.80, 1.15)
    cuts.append(_prism([(-0.62, 0.90), (0.62, 0.90), (0.62, 1.15), (-0.62, 1.15)], 's',
                       S_TRUNK_FRONT - GAP, S_TRUNK_FRONT))
    cuts += face_seam([(0.605, 0.99), (0.575, 0.93), (0.548, 0.88), (0.548, Z_BUMPER_R - 0.01)],
                      -2.6, -2.05)
    return cuts


def mk_box(x, s0, s1, z):
    """Horizontal slab at height z spanning s0..s1 across the whole width."""
    return _prism([(-1.2, z), (1.2, z), (1.2, z + GAP), (-1.2, z + GAP)], 's', s0, s1)


def make_cutters(col):
    for i, (V, F) in enumerate(all_seams()):
        mk.make_object(f"_seam{i}", V, F, [M.get("cavity")], None, col=col, uv=False)
