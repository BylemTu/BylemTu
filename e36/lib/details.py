"""Bolt-on detail parts of the E36 (pre-facelift, non-M): lamps, kidney grille,
trims, mirrors, handles, plates, emblems, wipers, exhaust and a simple cabin.

Every builder returns a list of Part records; build.py turns them into
Blender objects parented to the right panel with their socket as origin.
"""
import math
from dataclasses import dataclass, field
import numpy as np
from . import body, dims as D, seams as SE
from .conform import patch, combine, remap, lathe_at, box, loft, squircle


@dataclass
class Part:
    name: str
    verts: np.ndarray
    faces: list
    mats: list                 # material names
    face_mat: list
    parent: str = "body"
    origin: tuple = None       # car frame socket, default = bbox centre
    smooth: float = 35.0
    tags: dict = field(default_factory=dict)


def _solve(f, target, lo, hi, it=40):
    """Bisection for monotone f(theta) = target."""
    flo = f(lo) - target
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        fm = f(mid) - target
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ------------------------------------------------------------------ front end
def headlights(S):
    out = []
    for side, sg in (("L", 1.0), ("R", -1.0)):
        proj = lambda a, b, sg=sg: S.front(sg * a, b)
        lens = patch(proj, 0.205, 0.655, 0.470, 0.600, 18, 7, n_sq=12, offset=0.006, depth=0.11)
        bezel = patch(proj, 0.212, 0.648, 0.474, 0.596, 14, 5, n_sq=12, offset=-0.04, depth=0.0)
        parts = [(lens[0], lens[1], remap(lens[2], 1)), (bezel[0], bezel[1], [2] * len(bezel[1]))]
        for xc, R in ((0.312, 0.054), (0.540, 0.057)):
            p, n = proj(xc, 0.535)
            c = p - n * 0.016
            prof = [(0.0, -0.05)] + [(R * k, -0.05 * (1 - k * k)) for k in np.linspace(0.15, 1.0, 7)]
            dish = lathe_at(prof, c, n, 20)
            parts.append((dish[0], dish[1], [3] * len(dish[1])))
            rim = lathe_at([(R, 0.0), (R + 0.004, 0.004), (R + 0.011, 0.002), (R + 0.012, -0.03)], c, n, 20)
            parts.append((rim[0], rim[1], [2] * len(rim[1])))
            cap = lathe_at([(0.0, 0.004), (0.012, 0.002), (0.019, -0.012), (0.017, -0.03)], c, n, 10)
            parts.append((cap[0], cap[1], [3] * len(cap[1])))
            # ribbed inner lens of the round lamp
            ln = lathe_at([(0.0, 0.006), (R * 0.6, 0.004), (R, 0.0)], c + n * 0.001, n, 20)
            parts.append((ln[0], ln[1], [4] * len(ln[1])))
        V, F, Mt = combine(*parts)
        out.append(Part(f"headlight_{side}", V, F, ["glass_lamp", "plastic_black", "plastic_black",
                                                     "reflector", "glass_lamp_inner"], Mt,
                        origin=(sg * 0.43, 2.02, 0.61)))
        ind = patch(proj, 0.661, 0.765, 0.470, 0.600, 6, 7, n_sq=12, offset=0.006, depth=0.05)
        out.append(Part(f"indicator_{side}", ind[0], ind[1], ["lens_orange", "plastic_black"],
                        remap(ind[2], 1), origin=(sg * 0.705, 1.99, 0.61)))
        # side repeater on the fender
        sp = lambda a, b, sg=sg: S.side(a, b, sg)
        rep = patch(sp, 0.88, 0.94, 0.482, 0.500, 5, 2, n_sq=4, offset=0.004, depth=0.01)
        out.append(Part(f"side_repeater_{side}", rep[0], rep[1], ["lens_orange", "plastic_black"],
                        remap(rep[2], 1), parent=f"fender_{side}", origin=(sg * 0.84, 0.91, 0.49)))
    return out


def kidney_grille(S):
    parts = []
    for sg in (1.0, -1.0):
        proj = lambda a, b, sg=sg: S.front(sg * a, b)
        cx, cz, hw, hh = 0.100, 0.532, 0.072, 0.080
        M_ = 56
        outer, inner, o_n, i_n = [], [], [], []
        for k in range(M_):
            t = 2 * math.pi * k / M_
            u, v = math.cos(t), math.sin(t)
            m = max(abs(u), abs(v))
            u, v = squircle(u / m, v / m, 3.2)
            po, no = proj(cx + hw * u, cz + hh * v)
            pi, ni = proj(cx + (hw - 0.011) * u, cz + (hh - 0.011) * v)
            outer.append((po, no))
            inner.append((pi, ni))
        rings = [np.array([p - n * 0.01 for p, n in outer]),
                 np.array([p + n * 0.024 for p, n in outer]),
                 np.array([p + n * 0.030 for p, n in inner]),
                 np.array([p - n * 0.01 for p, n in inner])]
        V, F, _ = loft(rings, True, False, False)
        parts.append((V, F, [0] * len(F)))
        # recessed black back inside the kidney
        back = patch(proj, cx - hw + 0.011, cx + hw - 0.011, cz - hh + 0.011, cz + hh - 0.011, 8, 8,
                     n_sq=3.2, offset=-0.008, depth=0.0)
        parts.append((back[0], back[1], [1] * len(back[1])))
        # vertical slats
        for xs in np.linspace(cx - hw + 0.024, cx + hw - 0.024, 8):
            secs = []
            for zz in np.linspace(cz - hh + 0.012, cz + hh - 0.012, 6):
                p, n = proj(xs, zz)
                side_ = np.cross(n, (0, 0, 1.0))
                side_ /= np.linalg.norm(side_)
                secs.append(np.array([p + n * 0.02 + side_ * 0.0022, p + n * 0.02 - side_ * 0.0022,
                                      p - n * 0.006 - side_ * 0.0022, p - n * 0.006 + side_ * 0.0022]))
            V, F, _ = loft(secs)
            parts.append((V, F, [2] * len(F)))
    V, F, Mt = combine(*parts)
    return [Part("grille_kidney", V, F, ["chrome", "plastic_black", "trim_black_gloss"], Mt,
                 origin=(0.0, 2.08, 0.61))]


def front_panel(S):
    proj = lambda a, b: S.front(a, b)
    p = patch(proj, -0.748, 0.748, SE.Z_BUMPER_F - 0.002, SE.Z_HOOD_FRONT + 0.004, 40, 6,
              offset=-0.02, depth=0.0)
    return [Part("front_panel", p[0], p[1], ["plastic_black"], [0] * len(p[1]), origin=(0, 2.0, 0.6))]


# ------------------------------------------------------------------ rear end
def taillights(S):
    out = []
    cx, cs = 0.40, -1.95
    for side, sg in (("L", 1.0), ("R", -1.0)):
        def proj(th, z, sg=sg):
            p, n = S.radial(sg * cx, cs, z, sg * th, front=False)
            return p, n
        th0 = _solve(lambda t: abs(proj(t, 0.79)[0][0]), 0.556, 0.0, 1.2)
        th1 = _solve(lambda t: proj(t, 0.79)[0][1], -2.105, 0.4, 1.45)
        upper = patch(proj, th0, th1, 0.795, 0.872, 22, 4, n_sq=14, offset=0.007, depth=0.03)
        span = th1 - th0

        def lower_mat(th, z):
            f = (th - th0) / span
            if f > 0.52:
                return 2      # amber indicator
            if f > 0.22:
                return 0      # red
            return 3          # reverse (white)
        lower = patch(proj, th0, th1, 0.714, 0.789, 22, 4, n_sq=14, offset=0.007, depth=0.03,
                      mat_fn=lower_mat)
        V, F, Mt = combine((upper[0], upper[1], remap(upper[2], 1)), (lower[0], lower[1], remap(lower[2], 1)))
        out.append(Part(f"taillight_{side}", V, F, ["lens_red", "plastic_black", "lens_orange", "lens_clear"],
                        Mt, origin=(sg * 0.70, -2.20, 0.83)))
    return out


# ------------------------------------------------------------------ trims
def rub_strips(S):
    out = []
    # bumpers: radial wrap from the centre to the wheel arches
    z0, z1 = 0.385, 0.432
    f = patch(lambda th, z: S.radial(0.0, 1.30, z, th, True), -1.16, 1.16, z0, z1, 70, 3,
              offset=0.013, depth=0.012)
    out.append(Part("bumper_F_strip", f[0], f[1], ["trim_black_gloss"], [0] * len(f[1]), parent="bumper_F",
                    origin=(0, 2.1, 0.43)))
    r = patch(lambda th, z: S.radial(0.0, -1.35, z, th, False), -1.1, 1.1, 0.545, 0.600, 70, 3,
              offset=0.013, depth=0.012)
    out.append(Part("bumper_R_strip", r[0], r[1], ["trim_black_gloss"], [0] * len(r[1]), parent="bumper_R",
                    origin=(0, -2.3, 0.49)))
    # side mouldings on fender / doors
    za, zb_ = 0.432, 0.478
    arch_f = D.S_FA - math.sqrt(D.ARCH_R ** 2 - (0.455 - D.arch_z(True)) ** 2) - 0.004
    arch_r = D.S_RA + math.sqrt((D.ARCH_R + 0.035) ** 2 - (0.455 - D.arch_z(False)) ** 2) - 0.006
    spans = [("fender", SE.S_DOOR_F + 0.006, arch_f), ("door_F", SE.S_DOOR_B + 0.004, SE.S_DOOR_F - 0.004),
             ("door_R", arch_r - 0.001, SE.S_DOOR_B - 0.004)]
    for side, sg in (("L", 1.0), ("R", -1.0)):
        for nm, s0, s1 in spans:
            p = patch(lambda s, z, sg=sg: S.side(s, z, sg), s0, s1, za, zb_, 24, 3, offset=0.009, depth=0.01)
            parent = f"{nm}_{side}" if nm == "fender" else f"{nm}{side}"
            out.append(Part(f"{parent}_strip", p[0], p[1], ["trim_black_gloss"], [0] * len(p[1]), parent=parent,
                            origin=(sg * 0.85, 0.5 * (s0 + s1), 0.455)))
    return out


def front_intake(S):
    proj = lambda a, b: S.front(a, b)
    p = patch(proj, -0.40, 0.40, 0.212, 0.268, 24, 4, n_sq=8, offset=0.003, depth=0.01)
    parts = [(p[0], p[1], [0] * len(p[1]))]
    for zz in (0.232, 0.25):
        b = patch(proj, -0.39, 0.39, zz - 0.004, zz + 0.004, 16, 1, offset=0.008, depth=0.006)
        parts.append((b[0], b[1], [1] * len(b[1])))
    V, F, Mt = combine(*parts)
    return [Part("bumper_F_intake", V, F, ["cavity", "plastic_textured"], Mt, parent="bumper_F",
                 origin=(0, 2.1, 0.28))]


def plate(S, name, proj, x0, x1, z0, z1, parent, origin, depth):
    def mat(a, b):
        return 1 if a < x0 + 0.04 else 0
    p = patch(proj, x0, x1, z0, z1, 20, 3, n_sq=16, offset=depth, depth=depth + 0.004, mat_fn=mat)
    return Part(name, p[0], p[1], ["plate", "emblem_blue", "plastic_black"], remap(p[2], 2), parent=parent,
                origin=origin)


def plates(S):
    return [plate(S, "plate_F", lambda a, b: S.front(a, b), -0.26, 0.26, 0.272, 0.382, "bumper_F",
                  (0, 2.12, 0.40), 0.02),
            plate(S, "plate_R", lambda a, b: S.rear(-a, b), -0.26, 0.26, 0.692, 0.802, "trunk_lid",
                  (0, -2.25, 0.71), 0.006)]


def roundel(center, normal, up, R, name, parent):
    n = np.asarray(normal, float); n /= np.linalg.norm(n)
    e1 = np.cross(up, n); e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    rings = [0.0, 0.62, 0.8, 0.9, 1.0]
    seg = 32
    V, F, Mt = [], [], []
    for ri, r in enumerate(rings):
        h = 0.004 if ri < 3 else (0.006 if ri == 3 else 0.003)
        for k in range(seg):
            a = 2 * math.pi * k / seg
            V.append(center + n * h + (e1 * math.cos(a) + e2 * math.sin(a)) * r * R)
    for ri in range(len(rings) - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            F.append((ri * seg + k, ri * seg + k2, (ri + 1) * seg + k2, (ri + 1) * seg + k))
            if ri == 0:
                quad = int(((k + 0.5) / seg) * 4) % 4
                Mt.append(0 if quad % 2 == 0 else 1)
            elif ri == 1:
                Mt.append(2)
            else:
                Mt.append(3)
    # back rim
    base = len(V)
    for k in range(seg):
        a = 2 * math.pi * k / seg
        V.append(center - n * 0.002 + (e1 * math.cos(a) + e2 * math.sin(a)) * R)
    last = (len(rings) - 1) * seg
    for k in range(seg):
        k2 = (k + 1) % seg
        F.append((last + k, last + k2, base + k2, base + k))
        Mt.append(3)
    return Part(name, np.array(V), F, ["emblem_blue", "emblem_white", "trim_black_gloss", "chrome"], Mt,
                parent=parent, origin=tuple(center), smooth=60)


def emblems(S):
    p, n = S.top(0.0, 1.985)
    hood = roundel(p, n, (0, 1, 0), 0.041, "emblem_hood", "hood")
    p2, n2 = S.rear(0.0, 0.905)
    trunk = roundel(p2, n2, (0, 0, 1), 0.037, "emblem_trunk", "trunk_lid")
    return [hood, trunk]


def handles(S):
    out = []
    for side, sg in (("L", 1.0), ("R", -1.0)):
        for door, s0, s1, z0, z1 in (("F", -0.235, -0.105, 0.678, 0.716), ("R", -1.215, -1.085, 0.705, 0.743)):
            sp = lambda a, b, sg=sg: S.side(a, b, sg)
            h = patch(sp, s0, s1, z0, z1, 10, 3, n_sq=5, offset=0.011, depth=0.006)
            recess = patch(sp, s0 + 0.01, s1 - 0.01, z0 - 0.008, z0 + 0.004, 6, 1, n_sq=4, offset=0.0025,
                           depth=0.0)
            V, F, Mt = combine(h, (recess[0], recess[1], [1] * len(recess[1])))
            out.append(Part(f"handle_{door}{side}", V, F, ["plastic_black", "cavity"], [max(m, 0) for m in Mt],
                            parent=f"door_{door}{side}", origin=(sg * 0.84, 0.5 * (s0 + s1), 0.5 * (z0 + z1))))
    return out


def mirrors():
    out = []
    for side, sg in (("L", 1.0), ("R", -1.0)):
        cx, cz = 0.862, 0.905
        hw, hh = 0.076, 0.050
        secs = []
        for s, k, dz in ((0.628, 0.3, 0.004), (0.622, 0.62, 0.003), (0.611, 0.85, 0.001), (0.595, 0.97, 0.0),
                         (0.575, 1.0, 0.0), (0.560, 1.0, 0.0)):
            ring = []
            for q in range(28):
                t = 2 * math.pi * q / 28
                u, v = math.cos(t), math.sin(t)
                m = max(abs(u), abs(v))
                u, v = squircle(u / m, v / m, 3.0)
                ring.append((sg * (cx + hw * k * u), s, cz + dz + hh * k * v))
            secs.append(np.array(ring))
        V, F, Mt = loft(secs, True, True, False)
        # mirror glass slightly recessed inside the rear opening
        ring = []
        for q in range(28):
            t = 2 * math.pi * q / 28
            u, v = math.cos(t), math.sin(t)
            m = max(abs(u), abs(v))
            u, v = squircle(u / m, v / m, 3.0)
            ring.append((sg * (cx + (hw - 0.006) * u), 0.564, cz + (hh - 0.006) * v))
        gV = np.vstack([np.array(ring), [[sg * cx, 0.564, cz]]])
        gF = [(q, (q + 1) % 28, 28) for q in range(28)]
        rim_V = np.vstack([secs[-1], np.array(ring)])
        rim_F = [(q, (q + 1) % 28, 28 + (q + 1) % 28, 28 + q) for q in range(28)]
        arm = box((sg * 0.775, 0.60, 0.878), (0.07, 0.045, 0.035))
        V, F, Mt = combine((V, F, [0] * len(F)), (gV, gF, [1] * len(gF)), (rim_V, rim_F, [2] * len(rim_F)),
                           (arm[0], arm[1], [2] * 6))
        out.append(Part(f"mirror_{side}", V, F, ["plastic_black", "mirror", "trim_black_gloss"], Mt,
                        parent=f"door_F{side}", origin=(sg * 0.75, 0.60, 0.878), smooth=50))
    return out


def wipers(S):
    out = []
    parts = []
    for u0, u1 in ((-0.86, -0.06), (0.02, 0.80)):
        secs = []
        for u in np.linspace(u0, u1, 10):
            q = body.gh_top(0.60, u)
            c = np.array([q[0], q[1], q[2]]) + np.array([0, 0.004, 0.012])
            secs.append(np.array([c + (0, 0.009, 0.0), c + (0, -0.009, 0.0), c + (0, -0.009, -0.012),
                                  c + (0, 0.009, -0.012)]))
        V, F, _ = loft(secs)
        parts.append((V, F, [0] * len(F)))
        piv = body.gh_top(0.86, u0 if u0 > -0.5 else u1)
    V, F, Mt = combine(*parts)
    out.append(Part("wipers", V, F, ["plastic_black"], Mt, origin=(0, 0.84, 0.93)))
    return out


def exhaust():
    tip = lathe_at([(0.026, 0.0), (0.029, 0.0), (0.029, 0.13), (0.026, 0.13), (0.024, 0.12), (0.024, 0.02)],
                   (-0.46, -2.17, 0.30), (0, -1, -0.08), 16)
    V, F, Mt = tip
    return [Part("exhaust", V, F, ["chrome", "metal_raw"], Mt, origin=(-0.46, -2.17, 0.30))]


def interior():
    """Low-poly cabin so the glass shows something believable."""
    parts = []
    zf = 0.30

    def add(m, mat):
        parts.append((m[0], m[1], [mat] * len(m[1])))
    # tub: floor, door cards, firewall, parcel shelf
    add(box((0, -0.45, zf), (1.48, 2.5, 0.02)), 0)
    for sg in (1, -1):
        add(box((sg * 0.745, -0.45, 0.57), (0.02, 2.45, 0.56)), 0)
        add(box((sg * 0.715, -0.45, 0.66), (0.05, 2.35, 0.03)), 1)            # armrest line
    add(box((0, 0.72, 0.6), (1.5, 0.04, 0.62)), 0)
    add(box((0, -1.68, 0.89), (1.48, 0.42, 0.02)), 0)
    # dashboard
    dash = []
    for s, zt, zb in ((0.78, 0.845, 0.58), (0.62, 0.86, 0.56), (0.46, 0.845, 0.56), (0.36, 0.78, 0.58),
                      (0.32, 0.71, 0.60)):
        dash.append(np.array([(-0.74, s, zb), (0.74, s, zb), (0.74, s, zt), (-0.74, s, zt)]))
    V, F, _ = loft(dash, True, True, True)
    parts.append((V, F, [0] * len(F)))
    add(box((0.37, 0.50, 0.85), (0.36, 0.14, 0.06)), 0)                      # instrument hood
    add(box((0.0, 0.46, 0.66), (0.24, 0.26, 0.26)), 0)                        # centre console
    add(box((0.0, -0.1, 0.38), (0.2, 0.9, 0.14)), 0)                          # tunnel
    # steering wheel (LHD, driver on +x)
    c = np.array([0.37, 0.28, 0.76])
    ax = np.array([0.0, 1.0, -0.55])
    ring = lathe_at([(0.19, -0.012), (0.202, 0.0), (0.19, 0.012), (0.178, 0.0), (0.19, -0.012)], c, ax, 36)
    parts.append((ring[0], ring[1], [0] * len(ring[1])))
    hub = lathe_at([(0.0, 0.03), (0.07, 0.02), (0.08, -0.02), (0.03, -0.06)], c, ax, 16)
    parts.append((hub[0], hub[1], [0] * len(hub[1])))
    for a in (0.0, math.pi, -math.pi / 2):
        e1 = np.cross(ax / np.linalg.norm(ax), (1, 0, 0)); e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax / np.linalg.norm(ax), e1)
        d = e1 * math.sin(a) + e2 * math.cos(a)
        secs = [np.array([c + d * t + (0, 0, 0.01), c + d * t + (0.012, 0, 0), c + d * t - (0, 0, 0.01),
                          c + d * t - (0.012, 0, 0)]) for t in (0.06, 0.18)]
        V, F, _ = loft(secs)
        parts.append((V, F, [0] * len(F)))
    col = lathe_at([(0.03, 0.0), (0.03, 0.3)], c, ax, 10)
    parts.append((col[0], col[1], [0] * len(col[1])))

    # seats
    def seat(x, s, width, back_h, rear=False):
        cz = 0.47 if not rear else 0.46
        add(box((x, s, cz), (width, 0.50, 0.12), rot_x=math.radians(4)), 2)
        for sgn in (1, -1):
            add(box((x + sgn * (width / 2 - 0.03), s, cz + 0.03), (0.06, 0.48, 0.16), rot_x=math.radians(4)), 2)
        bs = s - 0.30
        add(box((x, bs, cz + back_h / 2 + 0.03), (width, 0.12, back_h), rot_x=math.radians(-18)), 2)
        if not rear:
            add(box((x, bs - 0.12, cz + back_h + 0.13), (0.26, 0.09, 0.18), rot_x=math.radians(-12)), 2)
    seat(0.37, -0.10, 0.52, 0.58)
    seat(-0.37, -0.10, 0.52, 0.58)
    seat(0.0, -1.02, 1.36, 0.50, rear=True)
    for x in (-0.42, 0.0, 0.42):
        add(box((x, -1.43, 0.99), (0.24, 0.09, 0.14), rot_x=math.radians(-14)), 2)
    V, F, Mt = combine(*parts)
    return [Part("interior", V, F, ["interior", "plastic_black", "interior_fabric"], Mt, origin=(0, -0.4, 0.5),
                 smooth=30)]


def headliner():
    """Roof lining under the roof skin (only the roof, not over the glass)."""
    st = np.linspace(D.S_ROOF_R + 0.02, D.S_ROOF_F - 0.02, 20)
    V, F = [], []
    K = 12
    for s in st:
        for i in range(K + 1):
            p = body.gh_top(s, -0.97 + 1.94 * i / K)
            V.append(p - np.array([0, 0, 0.025]))
    for a in range(len(st) - 1):
        for i in range(K):
            F.append((a * (K + 1) + i, (a + 1) * (K + 1) + i, (a + 1) * (K + 1) + i + 1, a * (K + 1) + i + 1))
    return [Part("headliner", np.array(V), F, ["interior_fabric"], [0] * len(F), origin=(0, -0.5, 1.3))]


def all_details(S):
    out = []
    for fn in (headlights, kidney_grille, front_panel, taillights, rub_strips, front_intake, plates, emblems,
               handles, cowl_and_wipers):
        out += fn(S)
    out += mirrors()
    out += exhaust()
    return out
