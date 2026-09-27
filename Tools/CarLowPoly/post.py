# Final visibility pass on the low-poly parts: delete unseen faces, flip back-facing ones, double-side thin flanges.
import bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
WH = {'FL': (-0.875, 1.596, -0.501), 'FR': (0.875, 1.597, -0.501), 'RL': (-0.875, -1.547, -0.501), 'RR': (0.875, -1.547, -0.501)}
G = -0.861
def dirs(n=160):
    i = np.arange(n) + 0.5; phi = np.arccos(1 - 2 * i / n); th = np.pi * (1 + 5 ** 0.5) * i
    D = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    return [Vector(d) for d in D if d[2] > -0.08]
DIRS = dirs()
def wheel_verts(me, side):   # wheel mesh placed at a wheel position (left side mirrored)
    s = 1 if side[1] == 'R' else -1
    return [((v.co.x * s + WH[side][0]), v.co.y + WH[side][1], v.co.z + WH[side][2]) for v in me.vertices]
def build_bvh(objs, wheel):
    Vs, Ts = [], []; off = 0
    def add(vs, ts):
        nonlocal off
        Vs.extend([tuple(v) for v in vs]); Ts.extend([[i + off for i in t] for t in ts]); off += len(vs)
    for o in objs:
        add([v.co[:] for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons])
    for side in WH:
        add(wheel_verts(wheel.data, side), [p.vertices[:] for p in wheel.data.polygons])
    add([(-9, -9, G), (9, -9, G), (9, 9, G), (-9, 9, G)], [(0, 1, 2), (0, 2, 3)])
    for lo, hi in (((-0.8, 0.95, -0.69), (0.8, 2.25, -0.05)), ((-0.8, -2.3, -0.62), (0.8, -1.25, 0.05))):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        add([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)])
    return BVHTree.FromPolygons(Vs, Ts)
def fix(ob, bvh, xform=None):
    """xform: function mapping local vertex -> world point (for the wheel)"""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.get('dbl') or bm.faces.layers.int.new('dbl')
    bm.faces.ensure_lookup_table()
    kill, flip, dbl = [], [], []
    for f in bm.faces:
        P = [Vector(xform(v.co) if xform else v.co) for v in f.verts]
        c = sum(P, Vector()) / len(P)
        n = (P[1] - P[0]).cross(P[2] - P[0]); 
        if n.length < 1e-12: kill.append(f); continue
        n.normalize(); pos = neg = 0
        for pt in [c] + [c + (p - c) * 0.6 for p in P]:
            for d in DIRS:
                if bvh.ray_cast(pt + d * 0.0015, d, 20.0)[0] is None:
                    if n.dot(d) >= 0: pos += 1
                    else: neg += 1
        if pos + neg == 0: kill.append(f)
        elif neg > pos:
            flip.append(f)
            if pos >= 4: dbl.append(f)
        elif neg >= 4: dbl.append(f)
    for f in flip: f.normal_flip()
    for f in dbl: f[lay] = 1          # made double-sided at export time
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(ob.data); bm.free()
    for p in ob.data.polygons: p.use_smooth = False
    return len(kill), len(flip), len(dbl)
def run():
    wheel = bpy.data.objects['wheel']
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o is not wheel]
    bvh = build_bvh(objs, wheel)
    for o in objs:
        print(f'  post {o.name:18s} removed {{}} flipped {{}} double-sided {{}}'.format(*fix(o, bvh)), f'inward twins {inward_twins(o)}', flush=True)
    ref = objs[0]
    me = underbody(0); ub = bpy.data.objects.new('underbody', me); bpy.context.scene.collection.objects.link(ub)
    for m in ref.data.materials: me.materials.append(m)
    me.polygons.foreach_set('material_index', np.full(len(me.polygons), ref.data.materials.find('Black'), np.int32))
    for p in me.polygons: p.use_smooth = False
    pass

ARCH = [(1.596, -0.501, 0.47), (-1.547, -0.501, 0.46)]
def inward_twins(ob):
    """faces whose normal points into the car (away from the body's centre line) get a reversed twin, so a stray
    inward-facing triangle never shows up as a hole when the engine culls back faces"""
    bm = bmesh.new(); bm.from_mesh(ob.data); n_add = 0; bm.normal_update()
    lay = bm.faces.layers.int.get('dbl') or bm.faces.layers.int.new('dbl')
    for f in list(bm.faces):
        c = f.calc_center_median(); n = f.normal
        if any(abs(c.y - y) < r and c.z < z + r for y, z, r in ARCH) and abs(c.x) > 0.6: continue
        radial = Vector((c.x / 1.0 ** 2, (c.y + 0.1) / 2.6 ** 2, (c.z + 0.05) / 0.75 ** 2))   # outward normal of an ellipsoid hugging the car
        if radial.length < 1e-6: continue
        if n.dot(radial.normalized()) < -0.15:
            if not f[lay]: f[lay] = 1; n_add += 1
    bm.to_mesh(ob.data); bm.free()
    for p in ob.data.polygons: p.use_smooth = False
    return n_add
def underbody(mat_index):
    """flat black floor so the car is closed from below (GTA frame)"""
    Z = -0.695
    quads = [((-0.70, -2.25), (0.70, 2.15)),                    # centre, between the wheels
             ((0.70, -1.08), (0.95, 1.12)), ((-0.95, -1.08), (-0.70, 1.12))]   # sills between the arches
    V, F = [], []
    for (x0, y0), (x1, y1) in quads:
        i = len(V); V += [(x0, y0, Z), (x0, y1, Z), (x1, y1, Z), (x1, y0, Z)]; F.append([i, i + 1, i + 2, i + 3])  # faces down
    # black radiator wall behind the grille / intakes (the engine bay is empty)
    for (x0, z0), (x1, z1) in (((-0.5, -0.45), (0.5, -0.12)), ((-0.8, -0.69), (0.8, -0.42))):
        i = len(V); Y = 2.2; V += [(x0, Y, z0), (x1, Y, z0), (x1, Y, z1), (x0, Y, z1)]; F.append([i + 3, i + 2, i + 1, i])   # faces forward
    # black cover over the notch at the top of the windscreen (the interior mirror mount used to hide it)
    notch = [(-0.095, 0.299, 0.558), (-0.081, 0.311, 0.553), (-0.078, 0.351, 0.535), (-0.072, 0.405, 0.51), (-0.064, 0.45, 0.489),
             (-0.054, 0.49, 0.469), (0.0, 0.498, 0.465)]
    notch += [(-x, y, z) for x, y, z in reversed(notch[:-1])]
    i = len(V); V += [(x, y, z + 0.002) for x, y, z in notch]
    f = list(range(i, i + len(notch)))
    a, b, c = (np.array(V[k]) for k in f[:3]); nrm = np.cross(np.array(V[f[len(f) // 2]]) - a, np.array(V[f[-1]]) - a)
    F.append(f if np.dot(nrm, (0, 0.5, 1)) > 0 else f[::-1])
    me = bpy.data.meshes.new('underbody'); me.from_pydata(V, [], F)
    return me
