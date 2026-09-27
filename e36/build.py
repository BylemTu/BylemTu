"""Build the game-ready, low-poly BMW E36 sedan.

usage: python3 build.py <out_dir> --mod <mod_ext.blend>

<mod_ext.blend> comes from tools/extract_mod.py (stock exterior panels of the
GTA:SA E36 mod, used as the lower-body base). Everything above the belt line
(sedan greenhouse, glass) plus lamps, grille, mirrors, wheels etc. is generated
here.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from lib import meshkit as mk, materials as M, panels, wheels, details, modbase
from lib.conform import Surface

SOCKETS = {
    "hood": (0.0, 0.64, 0.88), "trunk_lid": (0.0, -1.70, 1.04),
    "bumper_F": (0.0, 1.95, 0.30), "bumper_R": (0.0, -2.10, 0.45),
    "fender_L": (0.80, 1.35, 0.66), "fender_R": (-0.80, 1.35, 0.66),
    "door_FL": (0.84, modbase.S_DOOR_F - 0.03, 0.60), "door_FR": (-0.84, modbase.S_DOOR_F - 0.03, 0.60),
    "door_RL": (0.84, modbase.S_DOOR_B - 0.03, 0.60), "door_RR": (-0.84, modbase.S_DOOR_B - 0.03, 0.60),
    "front_panel": (0.0, 1.98, 0.53), "headlight_L": (0.43, 1.95, 0.54), "headlight_R": (-0.43, 1.95, 0.54),
    "grille_kidney": (0.0, 2.02, 0.52),
    "taillight_L": (0.66, -2.13, 0.79), "taillight_R": (-0.66, -2.13, 0.79), "rear_panel": (0.0, -2.15, 0.79), "side_repeaters": (0.0, 0.91, 0.49),
}
DETAILS = ("headlights", "wipers")


def bl(p):
    return (p[0], -p[1], p[2])


def attach(child, parent):
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw


def build(out_dir, mod_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M.reset()
    col = mk.collection("E36_Sedan")
    root = bpy.data.objects.new("E36_Sedan", None)
    root.empty_display_type = 'ARROWS'
    col.objects.link(root)

    parts, bvh = modbase.build(mod_path, col)
    S = Surface(bvh)
    gh = panels.build_greenhouse(col)
    glass = panels.build_glass(col)
    for key in ("door_FL", "door_FR", "door_RL", "door_RR"):
        parts[key] = mk.join([parts[key], gh.pop(key)], key)
    V, F = modbase.wheel_wells()
    wells = mk.make_object("wheel_wells", V, F, [M.get("wheelwell")], None, col=col, car_frame=False)
    parts["body"] = mk.join([parts["body"], gh.pop("roof"), wells], "body")

    for name, ob in parts.items():
        mk.set_origin(ob, bl(SOCKETS.get(name, (0, 0, 0))))
        ob.parent = root
    for name, val in glass.items():
        owner, ob = val if isinstance(val, tuple) else ("body", val)
        attach(ob, parts[owner])
    extra = []
    for fn in DETAILS:
        extra += getattr(details, fn)(S)
    extra = [p for p in extra if not p.name.startswith(("headlight_", "indicator_"))]
    extra += details.mirrors() + details.exhaust()
    extra.append(details.plates(S)[0])
    for p in extra:
        ob = mk.make_object(p.name, p.verts, p.faces, [M.get(m) for m in p.mats], p.face_mat, col=col,
                            smooth_angle=p.smooth)
        org = p.origin if p.origin is not None else tuple(np.asarray(p.verts).mean(axis=0))
        mk.set_origin(ob, bl(org))
        attach(ob, parts[p.parent] if p.parent in parts else root)

    wheels.place_wheels(col, root)
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "e36_sedan.blend"))
    total = 0
    for ob in col.objects:
        if ob.type == 'MESH':
            t = sum(len(p.vertices) - 2 for p in ob.data.polygons)
            total += t
            if os.environ.get("E36_VERBOSE"):
                print(f"  {ob.name:24s} {t}")
    print("total tris:", total)


if __name__ == "__main__":
    args = sys.argv[1:]
    mod = args[args.index("--mod") + 1] if "--mod" in args else None
    if not mod:
        sys.exit("need --mod <mod_ext.blend> (see tools/extract_mod.py)")
    out = [a for a in args if a != "--mod" and a != mod]
    build(out[0] if out else os.path.join(os.path.dirname(__file__), "out"), mod)
