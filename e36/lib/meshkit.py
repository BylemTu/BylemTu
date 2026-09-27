"""Blender mesh helpers."""
import math
import bpy
import bmesh
import numpy as np


def to_blender(p):
    """car frame (x, s, z) -> Blender (x, -s, z)."""
    p = np.asarray(p, float)
    out = p.copy()
    out[..., 1] = -p[..., 1]
    return out


def collection(name, parent=None):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    par = parent or bpy.context.scene.collection
    if col.name not in [c.name for c in par.children]:
        par.children.link(col)
    return col


def make_object(name, verts, faces, mats=None, face_mat=None, col=None, car_frame=True,
                smooth_angle=35.0, recalc=True, uv=True):
    v = to_blender(verts) if car_frame else np.asarray(verts, float)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in v], [], [tuple(int(i) for i in f) for f in faces])
    me.validate(clean_customdata=False)
    if mats:
        for m in mats:
            me.materials.append(m)
        if face_mat is not None:
            fm = list(face_mat)
            for poly in me.polygons:
                poly.material_index = int(fm[poly.index]) if poly.index < len(fm) else 0
    ob = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(ob)
    if recalc:
        recalc_normals(ob)
    shade(ob, smooth_angle)
    if uv:
        box_uv(ob)
    return ob


def recalc_normals(ob, inside=False):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if inside:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def shade(ob, angle=35.0):
    me = ob.data
    if angle is None:
        me.shade_flat()
        return
    me.shade_smooth()
    try:
        me.set_sharp_from_angle(angle=math.radians(angle))
    except Exception:
        pass


def box_uv(ob, scale=1.0):
    """Cheap tri-planar box projection UVs (games need a UV set even for flat PBR)."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers.active.data
    for poly in me.polygons:
        n = poly.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                uv = (co.y, co.z)
            elif ax == 1:
                uv = (co.x, co.z)
            else:
                uv = (co.x, co.y)
            uvl[li].uv = (uv[0] * scale, uv[1] * scale)


def smart_uv(ob, angle=66.0, margin=0.004):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')


def lathe(profile, segments=48, axis='x', cap_start=False, cap_end=False):
    """Revolve a (radius, axial) profile around an axis. Returns verts, faces (object local)."""
    prof = np.asarray(profile, float)
    n = len(prof)
    V, F = [], []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        c, s_ = math.cos(a), math.sin(a)
        for r, h in prof:
            if axis == 'x':
                V.append((h, r * c, r * s_))
            else:
                V.append((r * c, r * s_, h))
    for k in range(segments):
        k2 = (k + 1) % segments
        for j in range(n - 1):
            F.append((k * n + j, k2 * n + j, k2 * n + j + 1, k * n + j + 1))
    if cap_start:
        F.append(tuple(k * n for k in range(segments)))
    if cap_end:
        F.append(tuple(k * n + n - 1 for k in range(segments))[::-1])
    return np.array(V), F


def apply_boolean(ob, cutter, op='DIFFERENCE', solver='EXACT', hole_tolerant=False):
    mod = ob.modifiers.new("bool", 'BOOLEAN')
    mod.operation = op
    mod.solver = solver
    if isinstance(cutter, bpy.types.Collection):
        mod.operand_type = 'COLLECTION'
        mod.collection = cutter
    else:
        mod.object = cutter
    try:
        mod.material_mode = 'TRANSFER'
    except Exception:
        pass
    if solver == 'EXACT':
        mod.use_hole_tolerant = hole_tolerant
        mod.use_self = False
    apply_modifiers(ob)


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def box_mesh(cx, cy, cz, sx, sy, sz):
    """Axis aligned box in *Blender* coordinates. Returns verts, faces."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    V = [(cx + dx * hx, cy + dy * hy, cz + dz * hz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return V, F


def set_origin(ob, point_blender):
    """Move object origin to a Blender-space point without moving geometry."""
    import mathutils
    p = mathutils.Vector(point_blender)
    delta = p - ob.matrix_world.translation
    ob.data.transform(mathutils.Matrix.Translation(-delta))
    ob.matrix_world.translation = p


def join(objs, name=None):
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    ctx = bpy.context.copy()
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    if name:
        ob.name = name
        ob.data.name = name
    return ob
