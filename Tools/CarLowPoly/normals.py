"""Normal transfer: low-poly body gets the shading of the original dense model.

For every corner of every low-poly face we look up the point of the ORIGINAL surface under it (a bit
inside the face, so a corner on a crease picks the correct side) and take the original's interpolated
normal there. The original normals are smooth inside a panel and split on creases > `crease` deg,
on material borders and on open borders, so hard edges stay exactly where the real car has them.
Faces with no original surface nearby (rebuilt grille, floor plate) keep flat normals.
"""
import math
import bpy, bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


def original_mesh(prep_path, to_out, skip=('wheel',)):
    """joined original exterior (from prep.blend) in the output frame"""
    with bpy.data.libraries.load(prep_path) as (src, dst):
        dst.meshes = [n for n in src.meshes if n not in skip]
    bm = bmesh.new()
    for me in dst.meshes:
        if me is None:
            continue
        for v in me.vertices:
            v.co = to_out(v.co[:])
        bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    # consistent winding per connected piece, otherwise smooth normals of neighbours cancel out
    # (the direction itself does not matter, transfer() flips it to match the low-poly face)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    out = bpy.data.meshes.new('orig_ref'); bm.to_mesh(out); bm.free()
    return out


def corner_normals(me, crease=35.0):
    """smooth normals with splits on creases / material borders (per face corner)"""
    for p in me.polygons:
        p.use_smooth = True
    fn = np.array([p.normal[:] for p in me.polygons]); mi = np.array([p.material_index for p in me.polygons])
    e2f = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            e2f.setdefault(ek, []).append(p.index)
    c = math.cos(math.radians(crease))
    sharp = np.zeros(len(me.edges), bool)
    for ed in me.edges:
        fs = e2f.get(ed.key, [])
        if len(fs) != 2 or mi[fs[0]] != mi[fs[1]] or abs(np.dot(fn[fs[0]], fn[fs[1]])) < c:
            sharp[ed.index] = True
    at = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    at.data.foreach_set('value', sharp)
    me.update()
    cn = np.zeros(len(me.loops) * 3)
    me.corner_normals.foreach_get('vector', cn)
    return cn.reshape(-1, 3)


def transfer(me, ref, max_dist=0.012, inset=0.04, weld_deg=28.0):
    """set custom split normals on `me` from the reference mesh `ref`"""
    rcn = corner_normals(ref)
    rV = [v.co[:] for v in ref.vertices]
    rT = [p.vertices[:] for p in ref.polygons]
    rL = [list(p.loop_indices) for p in ref.polygons]
    bvh = BVHTree.FromPolygons(rV, rT, all_triangles=True)
    I = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    loops = np.zeros((len(me.loops), 3))
    n_flat = 0
    for p in me.polygons:
        fnrm = p.normal.copy()
        vs = [me.vertices[k].co.copy() for k in p.vertices]
        ctr = sum(vs, Vector()) / len(vs)
        for li, co in zip(p.loop_indices, vs):
            q = co + (ctr - co) * inset
            loc, _, fi, dist = bvh.find_nearest(q)
            n = None
            if fi is not None and dist <= max_dist:
                a, b, c = (Vector(rV[k]) for k in rT[fi])
                w = barycentric_transform(loc, a, b, c, *I)
                n = sum((Vector(rcn[rL[fi][k]]) * w[k] for k in range(3)), Vector())
                if n.length > 1e-9:
                    n.normalize()
                    if n.dot(fnrm) < 0:        # reversed twin / inward face: use the mirrored normal
                        n = -n
                    if n.dot(fnrm) < 0.2:      # nearly perpendicular to the face: keep it flat
                        n = None
                else:
                    n = None
            if n is None:
                n = fnrm; n_flat += 1
            loops[li] = n[:]
    # corners of one vertex: average those that belong to the same smooth side (< weld_deg apart),
    # so the shading is continuous across triangles and only breaks on real creases
    wc = math.cos(math.radians(weld_deg))
    by_vert = {}
    for p in me.polygons:
        for li, vi in zip(p.loop_indices, p.vertices):
            by_vert.setdefault(vi, []).append(li)
    for vi, lis in by_vert.items():
        left = list(lis)
        while left:
            seed = left.pop(0); grp = [seed]
            for li in left[:]:
                if np.dot(loops[li], loops[seed]) > wc:
                    grp.append(li); left.remove(li)
            avg = loops[grp].sum(0); avg /= max(np.linalg.norm(avg), 1e-12)
            loops[grp] = avg
    for p in me.polygons:
        p.use_smooth = True
    me.normals_split_custom_set([tuple(x) for x in loops])
    me.update()
    return n_flat
