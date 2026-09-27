"""Lower body + greenhouse -> separated, named, swappable panels."""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from . import body, dims as D, glass, meshkit as mk, materials as M, seams as SE


def car(v):
    """Blender -> car frame."""
    return np.array([v[0], -v[1], v[2]])


def arch_cutters(col):
    for s, name in ((D.S_FA, "F"), (D.S_RA, "R")):
        for side in (1, -1):
            V, F = mk.lathe([(0.0, 0.50), (D.ARCH_R, 0.50), (D.ARCH_R, 1.2), (0.0, 1.2)], 72, 'x')
            V = np.asarray(V)
            V[:, 0] *= side
            V = V + np.array([0, -s, D.arch_z(name == "F")])
            mk.make_object(f"_arch{name}{side}", V, F, [M.get("wheelwell")], None, col=col,
                           car_frame=False, uv=False)


def make_bvh(ob):
    me = ob.data
    verts = [v.co.copy() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    return BVHTree.FromPolygons(verts, polys)


def split_by(ob, pred, name):
    """Move faces where pred(face) is True into a new object. Returns new object or None."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    sel = [f for f in bm.faces if pred(f)]
    if not sel:
        bm.free()
        return None
    bm2 = bm.copy()
    bm2.faces.ensure_lookup_table()
    keep_ids = {f.index for f in sel}
    bmesh.ops.delete(bm2, geom=[f for f in bm2.faces if f.index not in keep_ids], context='FACES')
    bmesh.ops.delete(bm, geom=sel, context='FACES')
    _clean_loose(bm)
    _clean_loose(bm2)
    bm.to_mesh(ob.data)
    me = bpy.data.meshes.new(name)
    bm2.to_mesh(me)
    bm.free()
    bm2.free()
    for m in ob.data.materials:
        me.materials.append(m)
    nob = bpy.data.objects.new(name, me)
    for c in ob.users_collection:
        c.objects.link(nob)
    nob.matrix_world = ob.matrix_world.copy()
    return nob


def _clean_loose(bm):
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')


def delete_faces(ob, pred):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pred(f)], context='FACES')
    _clean_loose(bm)
    bm.to_mesh(ob.data)
    bm.free()


def islands_simple(ob):
    """Robust island split via bpy separate-by-loose."""
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    return [o for o in bpy.context.selected_objects]


def stats(ob):
    V = np.array([car(v.co) for v in ob.data.vertices])
    area = sum(p.area for p in ob.data.polygons)
    return V.mean(axis=0), V.min(axis=0), V.max(axis=0), area


def classify(ob):
    c, lo, hi, area = stats(ob)
    x, s, z = c
    side = "L" if x > 0 else "R"
    if area < 0.004:
        return "body"
    if s > SE.S_HOOD_REAR and lo[2] > 0.55 and abs(x) < 0.3 and hi[2] > 0.72:
        return "hood"
    if s < SE.S_TRUNK_FRONT + 0.02 and hi[2] > 0.9 and abs(x) < 0.3 and lo[2] > 0.5:
        return "trunk_lid"
    if s > 1.6 and hi[2] < SE.Z_BUMPER_F + 0.02 and abs(x) < 0.3:
        return "bumper_F"
    if s < -1.6 and hi[2] < SE.Z_BUMPER_R + 0.02 and abs(x) < 0.3:
        return "bumper_R"
    if s > 1.85 and lo[2] > SE.Z_BUMPER_F - 0.01 and hi[2] < SE.Z_HOOD_FRONT + 0.04:
        return "nose"
    if s > SE.S_DOOR_F - 0.05 and abs(x) > 0.5 and lo[2] > 0.25 and s < 1.9:
        return f"fender_{side}"
    if SE.S_DOOR_B < s < SE.S_DOOR_F and abs(x) > 0.6 and lo[2] > 0.25:
        return f"door_F{side}"
    if SE.S_DOOR_R - 0.1 < s < SE.S_DOOR_B and abs(x) > 0.6 and lo[2] > 0.25:
        return f"door_R{side}"
    return "body"


# hinge / attachment points (car frame) for every swappable part
SOCKETS = {
    "hood": (0.0, SE.S_HOOD_REAR + 0.03, 0.87),
    "trunk_lid": (0.0, SE.S_TRUNK_FRONT - 0.03, 0.95),
    "bumper_F": (0.0, 1.95, 0.35),
    "bumper_R": (0.0, -2.1, 0.40),
    "fender_L": (0.78, 1.35, 0.66), "fender_R": (-0.78, 1.35, 0.66),
    "door_FL": (0.80, SE.S_DOOR_F - 0.03, 0.62), "door_FR": (-0.80, SE.S_DOOR_F - 0.03, 0.62),
    "door_RL": (0.81, SE.S_DOOR_B - 0.03, 0.62), "door_RR": (-0.81, SE.S_DOOR_B - 0.03, 0.62),
}


def build_lower(col):
    V, F, T = body.lower_body()
    lower = mk.make_object("body", V, F, [M.get("paint"), M.get("underbody")], T, col=col)
    bvh = make_bvh(lower)
    cut_col = bpy.data.collections.new("_cutters")
    arch_cutters(cut_col)
    SE.make_cutters(cut_col)
    mk.apply_boolean(lower, cut_col, 'DIFFERENCE')
    for o in list(cut_col.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(cut_col)
    mats = [m.name for m in lower.data.materials]
    i_cav = mats.index("cavity")
    i_well = mats.index("wheelwell")

    # open the cabin: remove the flat deck under the greenhouse
    def cabin_deck(f):
        c = car(f.calc_center_median())
        n = f.normal
        return (-1.80 < c[1] < 0.80 and abs(c[0]) < 0.762 and c[2] > 0.8 and n.z > 0.5
                and f.material_index not in (i_cav, i_well))
    delete_faces(lower, cabin_deck)

    # shut-line walls: keep only the part near the skin
    def far_cavity(f):
        if f.material_index != i_cav:
            return False
        c = f.calc_center_median()
        hit = bvh.find_nearest(c)
        return hit[0] is None or hit[3] > 0.035
    delete_faces(lower, far_cavity)
    gaps = split_by(lower, lambda f: f.material_index == i_cav, "shut_lines")
    wells = split_by(lower, lambda f: f.material_index == i_well, "wheel_wells")

    parts = {}
    for isl in islands_simple(lower):
        name = classify(isl)
        parts.setdefault(name, []).append(isl)
    out = {}
    for name, objs in parts.items():
        out[name] = mk.join(objs, name) if len(objs) > 1 else objs[0]
        out[name].name = name
        out[name].data.name = name
    out["body"] = mk.join([out["body"], wells, gaps], "body")
    return out, bvh


def build_greenhouse(col):
    V, F, info = body.greenhouse()
    mats = [M.get("paint"), M.get("trim_black_gloss"), M.get("rubber")]
    regs = glass.regions()
    fm, keep = [], []
    tags = []   # owner per face
    for (sc, zone, v, s0, s1) in info:
        mat, owner = 0, "body"
        if zone in (1, -1):
            side = "L" if zone == 1 else "R"
            in_glass = (any(glass.inside_region(n, sc, v, 0.012, 0.03) for n in ("glass_F", "glass_R"))
                        or glass.inside_region("glass_Q", sc, v, 0.022, 0.04))
            if v < 0.035 and sc > -1.40:
                mat = 2
            elif v < 0.935 and sc > glass.c_pillar(v) + 0.035:
                mat = 1
            if v < 0.935 and sc > glass.c_pillar(v) - 0.012:
                owner = f"door_F{side}" if sc > SE.S_DOOR_B else f"door_R{side}"
            elif v < 0.035 and sc > glass.c_pillar(0.0) - 0.03:
                owner = f"door_F{side}" if sc > SE.S_DOOR_B else f"door_R{side}"
            keep.append(not in_glass)
        else:
            in_glass = any(glass.inside_region(n, sc, v, 0.025, 0.045) for n in ("windshield", "rear_window"))
            keep.append(not in_glass)
        fm.append(mat)
        tags.append(owner)
    F2 = [f for f, k in zip(F, keep) if k]
    fm2 = [m for m, k in zip(fm, keep) if k]
    tags2 = [t for t, k in zip(tags, keep) if k]
    gh = mk.make_object("greenhouse", V, F2, mats, fm2, col=col)
    # remove unused verts
    delete_faces(gh, lambda f: False)
    out = {}
    owners = sorted(set(tags2) - {"body"})
    # tag via a temporary face attribute
    attr = gh.data.attributes.new("owner", 'INT', 'FACE')
    for i, t in enumerate(tags2):
        attr.data[i].value = 0 if t == "body" else owners.index(t) + 1
    for k, o in enumerate(owners):
        out[o] = _split_attr(gh, "owner", k + 1, f"{o}_frame")
    gh.data.attributes.remove(gh.data.attributes["owner"])
    for o in out.values():
        if "owner" in o.data.attributes:
            o.data.attributes.remove(o.data.attributes["owner"])
    out["roof"] = gh
    return out


def _split_attr(ob, attr, value, name):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.get(attr)
    ids = {f.index for f in bm.faces if f[lay] == value}
    bm.free()
    return split_by(ob, lambda f: f.index in ids, name)


def build_glass(col):
    out = {}
    V, F, B = glass.glass_mesh("windshield", 1.0, 0.003, 8, 5)
    out["glass_windshield"] = mk.make_object("glass_windshield", V, F,
                                             [M.get("glass"), M.get("trim_black_gloss")], B, col=col)
    V, F, B = glass.glass_mesh("rear_window", 1.0, 0.003, 6, 5)
    out["glass_rear"] = mk.make_object("glass_rear", V, F, [M.get("glass"), M.get("trim_black_gloss")],
                                       B, col=col)
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        for key, owner in (("glass_F", f"door_F{side}"), ("glass_R", f"door_R{side}"),
                           ("glass_Q", f"door_R{side}")):
            V, F, B = glass.glass_mesh(key, sgn, 0.004, 5, 3)
            nm = f"{key}{side}".replace("glass_F", "glass_door_F").replace("glass_R", "glass_door_R") \
                .replace("glass_Q", "glass_quarter_R")
            out[nm] = (owner, mk.make_object(nm, V, F, [M.get("glass"), M.get("rubber")], B, col=col))
    return out
