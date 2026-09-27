"""15" steel wheel (6.5Jx15, ET42, 5x120) with 185/65 R15 tyre, brake disc + caliper."""
import math
import numpy as np
import bpy
from . import dims as D, meshkit as mk, materials as M


def tyre_profile():
    r0, R, hw = D.RIM_R + 0.004, D.TYRE_R, D.TYRE_W / 2
    side = [(r0, -hw + 0.012), (r0 + 0.02, -hw - 0.004), (r0 + 0.07, -hw - 0.007),
            (R - 0.022, -hw - 0.002), (R - 0.004, -hw + 0.02)]
    tread = [(R, -hw + 0.045), (R, hw - 0.045)]
    other = [(r, -a) for r, a in side[::-1]]
    return side + tread + other


def rim_profile():
    """Profile (r, a) of the steel wheel, a>0 = outboard. Starts at inner flange, ends at hub."""
    rr = D.RIM_R
    return [
        (rr + 0.012, -0.086), (rr - 0.003, -0.075), (rr - 0.028, -0.018), (rr - 0.030, 0.020),
        (rr - 0.004, 0.034), (rr + 0.013, 0.083), (rr + 0.004, 0.088), (rr - 0.009, 0.06),
        (0.150, 0.045), (0.125, 0.052), (0.096, 0.044), (0.082, 0.062), (0.048, 0.064), (0.035, 0.045),
    ]


def build_wheel_meshes(col):
    """Create the shared wheel meshes; returns dict of objects (at origin, axis +X outward)."""
    out = {}
    V, F = mk.lathe(tyre_profile(), 24, 'x')
    out['tyre'] = mk.make_object("tyre", V, F, [M.get("tyre")], None, col=col, car_frame=False,
                                 smooth_angle=50)
    V, F = mk.lathe(rim_profile(), 20, 'x')
    rim = mk.make_object("rim", V, F, [M.get("steel_rim")], None, col=col, car_frame=False,
                         smooth_angle=40)
    # cooling holes in the disc: 10 round holes + 5 lug nuts
    cut_col = bpy.data.collections.new("_rim_cut")
    for k in range(0):
        a = 2 * math.pi * (k + 0.5) / 10
        cv, cf = mk.lathe([(0.0, -0.1), (0.0135, -0.1), (0.0135, 0.1), (0.0, 0.1)], 8, 'x')
        cv = np.asarray(cv) + np.array([0.04, 0.128 * math.cos(a), 0.128 * math.sin(a)])
        o = mk.make_object(f"_hole{k}", cv, cf, None, None, col=cut_col, car_frame=False, uv=False)
        o.location.x = 0
    mk.apply_boolean(rim, cut_col, 'DIFFERENCE')
    for o in list(cut_col.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(cut_col)
    mk.shade(rim, 40)
    # lug nuts
    nuts_v, nuts_f = [], []
    for k in range(5):
        a = 2 * math.pi * k / 5 + math.pi / 2
        v, f = mk.lathe([(0.0, 0.058), (0.0095, 0.058), (0.0095, 0.072), (0.0, 0.079)], 6, 'x')
        v = np.asarray(v) + np.array([0, 0.06 * math.cos(a), 0.06 * math.sin(a)])
        nuts_f += [tuple(i + len(nuts_v) for i in ff) for ff in f]
        nuts_v += list(v)
    # small centre cap
    v, f = mk.lathe([(0.0, 0.07), (0.028, 0.068), (0.036, 0.05)], 12, 'x')
    nuts_f += [tuple(i + len(nuts_v) for i in ff) for ff in f]
    nuts_v += list(v)
    nuts = mk.make_object("_nuts", nuts_v, nuts_f, [M.get("metal_raw")], None, col=col, car_frame=False,
                          smooth_angle=30)
    out['rim'] = mk.join([rim, nuts], "rim")
    # brake disc + hub (not visible much, but fills the wheel)
    V, F = mk.lathe([(0.05, -0.02), (0.143, -0.02), (0.143, 0.002), (0.05, 0.002), (0.05, 0.03),
                     (0.035, 0.035)], 16, 'x')
    out['brake'] = mk.make_object("brake_disc", V, F, [M.get("brake_disc")], None, col=col,
                                  car_frame=False, smooth_angle=40)
    # caliper (block wrapped around the disc, rearward-up position set per wheel)
    V, F = [], []
    ang = np.linspace(math.radians(-25), math.radians(25), 7)
    for a in ang:
        for r, x in ((0.105, -0.045), (0.155, -0.045), (0.155, 0.018), (0.105, 0.018)):
            V.append((x, r * math.cos(a), r * math.sin(a)))
    n = len(ang)
    for i in range(n - 1):
        for j in range(4):
            j2 = (j + 1) % 4
            F.append((i * 4 + j, (i + 1) * 4 + j, (i + 1) * 4 + j2, i * 4 + j2))
    F.append((0, 1, 2, 3)[::-1])
    F.append(tuple((n - 1) * 4 + j for j in range(4)))
    out['caliper'] = mk.make_object("caliper", V, F, [M.get("metal_raw")], None, col=col,
                                    car_frame=False, smooth_angle=30)
    return out


WHEELS = {
    "FL": (D.S_FA, D.TRACK_F / 2, 1), "FR": (D.S_FA, D.TRACK_F / 2, -1),
    "RL": (D.S_RA, D.TRACK_R / 2, 1), "RR": (D.S_RA, D.TRACK_R / 2, -1),
}


def place_wheels(col, parent):
    base = build_wheel_meshes(col)
    objs = {}
    for key, (s, x, side) in WHEELS.items():
        hub = bpy.data.objects.new(f"WHEEL_{key}", None)
        hub.empty_display_type = 'SPHERE'
        hub.empty_display_size = 0.1
        col.objects.link(hub)
        hub.location = (x * side, -s, D.WHEEL_Z)
        hub.rotation_euler = (0, 0, 0 if side > 0 else math.pi)
        hub.parent = parent
        for part in ("rim", "tyre", "brake", "caliper"):
            src = base[part]
            ob = bpy.data.objects.new(f"{part}_{key}", src.data)
            col.objects.link(ob)
            ob.parent = hub
            if part == "caliper":
                # caliper sits behind the axle, pointing up-rear
                ang = math.radians(110 if side > 0 else 70)
                ob.rotation_euler = (ang if side > 0 else -ang + math.pi, 0, 0)
            objs[f"{part}_{key}"] = ob
        objs[f"WHEEL_{key}"] = hub
    for o in base.values():
        bpy.data.objects.remove(o)
    return objs
