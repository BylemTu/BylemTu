"""Build the lower body panels from the extracted GTA:SA E36 mod geometry
(see tools/extract_mod.py): clean, map materials, decimate to a low-poly
budget and split the coupe panels into sedan parts with plane cuts."""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from . import dims as D, materials as M, meshkit as mk

S_DOOR_F = 0.644        # coupe door leading edge = sedan front door leading edge
S_DOOR_B = -0.33        # B-pillar shut line
S_DOOR_R = -1.30        # sedan rear door trailing edge
Z_SILL = 0.30
BELT = (0.65, 0.862, -1.70, 0.912)   # (s0, z0, s1, z1) belt line of the mod

DELETE = object()


def belt_z(s):
    s0, z0, s1, z1 = BELT
    return z0 + (s - s0) * (z1 - z0) / (s1 - s0)


def map_material(m, role):
    """Mod material -> library material name, or DELETE."""
    tex = []
    col = (1, 1, 1)
    if m is not None and m.node_tree:
        tex = [n.image.name.lower() for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
        b = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED']
        if b:
            col = tuple(b[0].inputs['Base Color'].default_value[:3])
    t = tex[0] if tex else ""
    if any(k in t for k in ("leater", "inside", "cockpit", "emzone", "engine")):
        return DELETE
    if any(k in t for k in ("badges", "e36_detales", "obrys")):
        return "chrome"
    if t.startswith("c0"):
        return "bumper_plastic" if role in ("bumper_F",) else "paint"
    if t.startswith("alu"):
        return "chrome"
    if role == "head_lamps":
        return "reflector" if t.startswith("lights") else "plastic_black"
    if role == "head_lens":
        return "lens_orange" if t.startswith("kierunek") else "glass_lamp"
    if role == "kidneys":
        return "trim_black_gloss"
    if t.startswith("rej"):
        return "plate"
    if t.startswith("misc") or t.startswith("carbon") or t.startswith("cache") or t.startswith("swiatlo"):
        return "plastic_black"
    if not t and role == "shell":
        return DELETE          # tuning decal (iron cross) behind the front wheel
    if not t:
        g = sum(col) / 3
        if role == "bumper_R" and 0.15 < g < 0.4:
            return "bumper_plastic"
        return "plastic_black" if g < 0.9 else "plastic_black"
    return "plastic_black"


def color_taillight(ob):
    """Pre-facelift sedan lamp: red upper band; lower band amber (outer),
    red (middle) and clear reverse lamp (inner)."""
    xs = [abs(v.co.x) for v in ob.data.vertices]
    x0, x1 = min(xs), max(xs)
    sg = 1 if sum(v.co.x for v in ob.data.vertices) > 0 else -1
    bisect(ob, (0, 0, 0.80), (0, 0, 1))
    for f in (0.22, 0.55):
        bisect(ob, (sg * (x0 + f * (x1 - x0)), 0, 0), (1, 0, 0))
    me = ob.data
    names = ["lens_red", "lens_orange", "lens_clear", "plastic_black"]
    me.materials.clear()
    for n in names:
        me.materials.append(M.get(n))
    for p in me.polygons:
        c = p.center
        f = (abs(c.x) - x0) / max(x1 - x0, 1e-6)
        if c.z > 0.80:
            p.material_index = 0
        elif f > 0.55:
            p.material_index = 1
        elif f > 0.22:
            p.material_index = 0
        else:
            p.material_index = 2


def car(v):
    return np.array([v[0], -v[1], v[2]])


def load(path):
    with bpy.data.libraries.load(path) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("MOD_")]
    objs = {}
    for ob in dst.objects:
        bpy.context.scene.collection.objects.link(ob)
        objs[ob.name[4:]] = ob
    return objs


def remap_materials(ob, role):
    me = ob.data
    names = [map_material(m, role) for m in me.materials]
    keep = sorted({n for n in names if n is not DELETE})
    old_idx = [p.material_index for p in me.polygons]
    me.materials.clear()
    for n in keep:
        me.materials.append(M.get(n))
    for p, i in zip(me.polygons, old_idx):
        p.material_index = i
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0006)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    dead = [f for f in bm.faces if names[f.material_index] is DELETE]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0006)
    idx = {n: i for i, n in enumerate(keep)}
    for f in bm.faces:
        f.material_index = idx[names[f.material_index]]
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(me)
    bm.free()


def bisect(ob, co_car, no_car):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=Vector(car(co_car)), plane_no=Vector(car(no_car)), dist=1e-5)
    bm.to_mesh(ob.data)
    bm.free()


def split(ob, pred, name):
    """Move faces whose car-frame centre satisfies pred(c) into a new object."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    sel = {f.index for f in bm.faces if pred(car(f.calc_center_median()))}
    bm.free()
    if not sel:
        return None
    from .panels import split_by
    return split_by(ob, lambda f: f.index in sel, name)


def delete(ob, pred):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pred(car(f.calc_center_median()))], context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(ob.data)
    bm.free()


def decimate(ob, target_tris):
    """Collapse-decimate to the budget, then transfer the high-res shading
    normals back onto the low-poly mesh (keeps the panels smooth)."""
    import os
    tris = tri_count(ob)
    mk.shade(ob, 40)
    if os.environ.get("E36_NODEC") or tris <= target_tris:
        return
    hi = ob.copy()
    hi.data = ob.data.copy()
    for c in ob.users_collection:
        c.objects.link(hi)
    mod = ob.modifiers.new("dec", 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = target_tris / tris
    mod.use_symmetry = True
    mod.symmetry_axis = 'X'
    mod.use_collapse_triangulate = True
    mk.apply_modifiers(ob)
    mk.shade(ob, 40)
    dt = ob.modifiers.new("nrm", 'DATA_TRANSFER')
    dt.object = hi
    dt.use_loop_data = True
    dt.data_types_loops = {'CUSTOM_NORMAL'}
    dt.loop_mapping = 'POLYINTERP_NEAREST'
    mk.apply_modifiers(ob)
    me = hi.data
    bpy.data.objects.remove(hi)
    bpy.data.meshes.remove(me)


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


BUDGET = {"headlight_L": 450, "headlight_R": 450, "grille_kidney": 500, "taillight_L": 400, "taillight_R": 400,
          "bumper_F": 1100, "bumper_R": 800, "hood": 1100, "trunk_lid": 800,
          "door": 1000, "fender": 800, "body": 3800, "front_panel": 450, "rear_panel": 300}


def build(path, col):
    objs = load(path)
    for role, ob in objs.items():
        if role != "tail_lens":
            remap_materials(ob, role)
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        col.objects.link(ob)
    # reference surface for conforming detail parts (lamps, plates, ...) before anything is cut
    verts, polys = [], []
    for role in ("shell", "front_panel", "rear_panel", "bumper_F", "bumper_R", "hood", "trunk_lid",
                 "head_lens", "head_lamps", "tail_lens", "kidneys", "door_L_coupe", "door_R_coupe"):
        ob = objs[role]
        off = len(verts)
        verts += [v.co.copy() for v in ob.data.vertices]
        polys += [tuple(off + i for i in p.vertices) for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    bpy.data.objects.remove(objs.pop("side_repeaters"))
    tail = objs.pop("tail_lens")
    objs["taillight_L"] = tail
    objs["taillight_R"] = split(tail, lambda c: c[0] < 0, "taillight_R")
    for ob in (objs["taillight_L"], objs["taillight_R"]):
        color_taillight(ob)
    # stock twin-round headlamps + kidneys of the mod become their own swappable parts
    lamps = mk.join([objs.pop("head_lamps"), objs.pop("head_lens")], "_lamps")
    objs["headlight_L"] = lamps
    objs["headlight_R"] = split(lamps, lambda c: c[0] < 0, "headlight_R")
    objs["grille_kidney"] = objs.pop("kidneys")

    shell = objs.pop("shell")
    # remove the coupe greenhouse (roof, pillars) above the belt
    bs0, bz0, bs1, bz1 = BELT
    t = np.array([0.0, bs1 - bs0, bz1 - bz0])
    n = np.cross(t, [1.0, 0, 0])
    n /= np.linalg.norm(n)
    if n[2] < 0:
        n = -n
    bisect(shell, (0, bs0, bz0), n)

    def above_belt(c):
        s, z = c[1], c[2]
        if -1.86 < s <= -1.45 and abs(c[0]) > 0.5:
            return z > 1.0                     # coupe C-pillar: keep the quarter top
        in_cabin = (-1.45 < s < 0.60) or (0.60 <= s < 0.74 and abs(c[0]) > 0.60)
        return in_cabin and z > belt_z(s) + 0.002
    delete(shell, above_belt)
    for key in ("door_L_coupe", "door_R_coupe"):
        d = objs[key]
        bisect(d, (0, bs0, bz0), n)
        delete(d, lambda c: c[2] > belt_z(c[1]) + 0.002)

    # sedan door lines
    for ob in (shell, objs["door_L_coupe"], objs["door_R_coupe"]):
        bisect(ob, (0, S_DOOR_B, 0), (0, 1, 0))
    bisect(shell, (0, S_DOOR_R, 0), (0, 1, 0))
    bisect(shell, (0, 0, Z_SILL), (0, 0, 1))
    arch_c = np.array([D.S_RA, D.arch_z(False)])
    parts = {}
    for side, sg in (("L", 1), ("R", -1)):
        coupe = objs.pop(f"door_{side}_coupe")
        coupe.name = f"door_F{side}"
        rear_a = split(coupe, lambda c: c[1] < S_DOOR_B, f"_dr{side}")

        def rear_door(c, sg=sg):
            return (c[0] * sg > 0.6 and S_DOOR_R < c[1] < S_DOOR_B and Z_SILL < c[2] < belt_z(c[1]) + 0.01
                    and np.hypot(c[1] - arch_c[0], c[2] - arch_c[1]) > D.ARCH_R + 0.03)
        rear_b = split(shell, rear_door, f"_drs{side}")
        parts[f"door_R{side}"] = mk.join([o for o in (rear_a, rear_b) if o], f"door_R{side}")
        parts[f"door_F{side}"] = coupe

        def fender(c, sg=sg):
            return c[0] * sg > 0.58 and S_DOOR_F - 0.02 < c[1] < 2.0 and c[2] > 0.45
        parts[f"fender_{side}"] = split(shell, fender, f"fender_{side}")
    parts["body"] = shell
    shell.name = "body"
    for role, ob in objs.items():
        parts[role] = ob
        ob.name = role
    # decimate to the low-poly budget
    for name, ob in parts.items():
        key = "door" if name.startswith("door") else ("fender" if name.startswith("fender") else name)
        target = BUDGET.get(key, 800)
        decimate(ob, target)
        ob.data.name = ob.name
        mk.box_uv(ob)
    return parts, bvh


def wheel_wells():
    """Black liners inside the arches + a flat underbody so nothing is see-through."""
    V, F = [], []

    def add(v, f):
        off = len(V)
        V.extend(v)
        F.extend([tuple(i + off for i in ff) for ff in f])
    for s, front in ((D.S_FA, True), (D.S_RA, False)):
        zc = D.arch_z(front)
        R = D.ARCH_R + 0.01
        for sg in (1, -1):
            ring_o, ring_i = [], []
            angs = np.linspace(math.radians(-15), math.radians(195), 22)
            for a in angs:
                ring_o.append((sg * 0.79, s + R * math.cos(a), zc + R * math.sin(a)))
                ring_i.append((sg * 0.48, s + R * math.cos(a), zc + R * math.sin(a)))
            v = ring_o + ring_i + [(sg * 0.48, s, zc - 0.05)]
            nA = len(angs)
            f = [(k, k + 1, nA + k + 1, nA + k) for k in range(nA - 1)]
            f += [(nA + k, nA + k + 1, 2 * nA) for k in range(nA - 1)]
            add(v, f)
    add([(-0.48, -2.0, 0.24), (0.48, -2.0, 0.24), (0.48, 1.9, 0.24), (-0.48, 1.9, 0.24)], [(0, 1, 2, 3)])
    return np.array(V), F
