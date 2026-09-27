"""Window regions on the greenhouse, glass meshes and greenhouse hole cutting."""
import math
import numpy as np
from . import body, dims as D
from .seams import S_DOOR_B

T_LO, T_HI = 0.075, 0.905       # side glass span as fraction of belt->rail height
S_FRONT_GLASS = 0.55           # front edge of front door glass (mirror sail ahead)
S_REAR_MAIN = (-0.955, -0.405)  # rear door drop glass
S_VENT_FRONT = -0.985           # rear fixed quarter light front edge


def c_pillar(t):
    """s of the rear edge of the side glass (Hofmeister kink at the bottom)."""
    t = min(max(t, 0.0), 1.0)
    if t >= 0.24:
        return -1.10 - 0.21 * (T_HI - t) / (T_HI - 0.24)
    k = (0.24 - t) / (0.24 - T_LO)
    return -1.31 + 0.065 * k ** 1.6


def regions():
    """name -> (zone, s_lo(v), s_hi(v), v_lo, v_hi, border_m) ; zone 'side' uses v=t, 'top' uses v=u."""
    return {
        "windshield": ("top", lambda v: D.S_ROOF_F + 0.012, lambda v: 0.645, -0.965, 0.965, 0.045),
        "rear_window": ("top", lambda v: -1.725, lambda v: D.S_ROOF_R - 0.012, -0.955, 0.955, 0.04),
        "glass_F": ("side", lambda v: S_DOOR_B + 0.035, lambda v: S_FRONT_GLASS, T_LO, T_HI, 0.02),
        "glass_R": ("side", lambda v: S_REAR_MAIN[0], lambda v: S_REAR_MAIN[1], T_LO, T_HI, 0.02),
        "glass_Q": ("side", lambda v: c_pillar(v), lambda v: S_VENT_FRONT, T_LO, T_HI, 0.03),
    }


def surf(zone, s, v, side=1.0):
    return body.gh_side(s, v, side) if zone == "side" else body.gh_top(s, v)


def normal(zone, s, v, side=1.0):
    e = 1e-3
    p = surf(zone, s, v, side)
    a = surf(zone, s + e, v, side) - p
    b = surf(zone, s, v + e, side) - p
    n = np.cross(a, b)
    n /= np.linalg.norm(n)
    # make it point outward (away from the car centre / upward)
    c = np.array([0.0, p[1], 0.75])
    if np.dot(n, p - c) < 0:
        n = -n
    return n


def glass_mesh(name, side=1.0, offset=0.003, ns=26, nv=12):
    """Grid mesh of a window with a one-quad-wide border ring (frit / seal).

    Returns verts, faces, face_is_border list.
    """
    zone, slo, shi, vlo, vhi, border = regions()[name]
    if zone == "side":
        zb, zre = body.gh_frame(-0.5)[:2]
        bv = border / (zre - zb)
    else:
        bv = border / 0.6
    vs = np.concatenate([[vlo], np.linspace(vlo + bv, vhi - bv, nv), [vhi]])
    V = []
    for v in vs:
        a, b = slo(v), shi(v)
        ss = np.concatenate([[a], np.linspace(a + border, b - border, ns), [b]])
        for s in ss:
            V.append(surf(zone, s, v, side) + normal(zone, s, v, side) * offset)
    V = np.array(V)
    nrow, ncol = len(vs), ns + 2
    F, B = [], []
    for j in range(nrow - 1):
        for i in range(ncol - 1):
            F.append((j * ncol + i, j * ncol + i + 1, (j + 1) * ncol + i + 1, (j + 1) * ncol + i))
            B.append(j == 0 or j == nrow - 2 or i == 0 or i == ncol - 2)
    return V, F, B


def inside_region(name, s, v, margin_s=0.0, margin_v=0.0):
    zone, slo, shi, vlo, vhi, border = regions()[name]
    if not (vlo + margin_v <= v <= vhi - margin_v):
        return False
    return slo(v) + margin_s <= s <= shi(v) - margin_s
