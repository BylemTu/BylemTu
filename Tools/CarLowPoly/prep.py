# Step 1 (shared by both versions): exterior parts from the DFF, welded, with hidden faces removed.
import bpy, bmesh, sys, os, numpy as np
sys.path.insert(0, '.')
import dff, ref
from mathutils import Vector
from mathutils.bvhtree import BVHTree
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
CATS = ['Paint', 'Glass', 'Black', 'Chrome', 'Headlight', 'Taillight', 'Plate', 'Tire', 'Rim', 'Brake']
COL = {'Paint': (0.03, 0.18, 0.62), 'Glass': (0.02, 0.025, 0.035), 'Black': (0.012, 0.012, 0.014), 'Chrome': (0.35, 0.36, 0.38),
       'Headlight': (0.85, 0.88, 0.92), 'Taillight': (0.55, 0.01, 0.01), 'Plate': (0.85, 0.85, 0.82), 'Tire': (0.02, 0.02, 0.022),
       'Rim': (0.45, 0.46, 0.48), 'Brake': (0.12, 0.12, 0.13)}
REFCAT = {1: 'Paint', 2: 'Glass', 3: 'Black', 4: 'Chrome', 5: 'Headlight', 6: 'Taillight', 7: 'Plate', 0: 'Black'}
mats = {}
for c in CATS:
    m = bpy.data.materials.new(c); m.diffuse_color = (*COL[c], 1)
    m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*COL[c], 1)
    b.inputs['Roughness'].default_value = {'Glass': 0.1, 'Chrome': 0.25, 'Paint': 0.35}.get(c, 0.6)
    b.inputs['Metallic'].default_value = 1.0 if c in ('Chrome', 'Rim') else 0.0
    mats[c] = m
r = ref.r; F = ref.F
skip = {'interior', 'interior__parts', 'interior_decals', 'interior_glass', 'steeringwheel_glow', 'steeringwheel_ok', 'enginemesh', 'suspension'}
objs = []; seen = set(); names = {}; KID = []
for a in r['atomics']:
    name = F[a['frame']]['name']
    if name in skip or a['geom'] in seen or (name == 'bodyshell' and 'bodyshell' in names): continue
    seen.add(a['geom']); g = r['geoms'][a['geom']]
    if name == 'wheel':
        M = np.eye(4)            # keep the wheel at its own origin
        cats = [('Tire' if (m['tex'] or '') in ('sidewall', 'yokohama') or m['color'][:3] == (153, 153, 153) else
                 'Brake' if (m['tex'] or '').startswith('bmw_m4_disc') else 'Rim') for m in g['mats']]
    else:
        M = ref.world(a['frame'])
        cats = [REFCAT[ref.cat(name, m)] for m in g['mats']]
    v = g['v'] @ M[:3, :3].T + M[:3, 3]
    nm = name.replace('_ok', '').replace('0', '')
    names[nm] = names.get(nm, 0) + 1
    if names[nm] > 1: nm += '_glass'
    me = bpy.data.meshes.new(nm); me.from_pydata(v.tolist(), [], g['tris'].tolist())
    for c in CATS: me.materials.append(mats[c])
    me.polygons.foreach_set('material_index', np.array([CATS.index(cats[i]) for i in g['mat']], np.int32))
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0004)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-5)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    if name != 'wheel':
        # before the visibility test: drop tiny bits (badges, sensors) and cut out the dense kidney grilles,
        # so that whatever sits behind them is kept
        seen = set(); kill = []
        for f in bm.faces:
            if f in seen: continue
            st = [f]; comp = []; seen.add(f)
            while st:
                g = st.pop(); comp.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h not in seen: seen.add(h); st.append(h)
            co = np.array([v.co[:] for g in comp for v in g.verts])
            if np.linalg.norm(co.max(0) - co.min(0)) < 0.035: kill += comp
            elif nm == 'bump_front' and len(comp) > 800 and all(g.material_index == CATS.index('Chrome') for g in comp):
                KID.append(co); kill += comp
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(nm, me); sc.collection.objects.link(ob); objs.append(ob)
# ---- visibility culling: a face survives if some ray from it escapes to the sky/sides.
# Occluders: all exterior parts, the 4 wheels, and the ground plane (so the underbody goes too).
WH = [(-0.875, 1.596, -0.501), (0.875, 1.597, -0.501), (-0.875, -1.547, -0.501), (0.875, -1.547, -0.501)]
Vs, Ts = [], []; off = 0
wheel = [o for o in objs if o.name == 'wheel'][0]
for o in objs:
    pts = [np.array(v.co[:]) for v in o.data.vertices]
    tris = [list(p.vertices) for p in o.data.polygons]
    if o is wheel:
        for w in WH:
            Vs += [(p * np.array([1 if w[0] > 0 else -1, 1, 1]) + w).tolist() for p in pts]
            Ts += [[i + off for i in t] for t in tris]; off += len(pts)
        continue
    Vs += [p.tolist() for p in pts]; Ts += [[i + off for i in t] for t in tris]; off += len(pts)
G = -0.861
Vs += [[-9, -9, G], [9, -9, G], [9, 9, G], [-9, 9, G]]; Ts += [[off, off + 1, off + 2], [off, off + 2, off + 3]]
# stand-in occluders for what was removed: engine block and boot contents
def add_box(lo, hi):
    global off
    x0, y0, z0 = lo; x1, y1, z1 = hi
    Vs.extend([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    for q in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        Ts.append([off + q[0], off + q[1], off + q[2]]); Ts.append([off + q[0], off + q[2], off + q[3]])
    off += 8
add_box((-0.8, 0.95, -0.69), (0.8, 2.25, -0.05))
add_box((-0.8, -2.3, -0.62), (0.8, -1.25, 0.05))
bvh = BVHTree.FromPolygons(Vs, Ts, all_triangles=True)
n = 160; i = np.arange(n) + 0.5
phi = np.arccos(1 - 2 * i / n); th = np.pi * (1 + 5 ** 0.5) * i
DIRS = [Vector(d) for d in np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1) if d[2] > -0.08]  # game cameras never look from below
def visible(pt):
    for d in DIRS:
        if bvh.ray_cast(pt + d * 0.002, d, 20.0)[0] is None: return d
    return None
for o in objs:
    if o is wheel: continue
    me = o.data; kill = []; flip = []
    for p in me.polygons:
        vs = [Vector(me.vertices[k].co) for k in p.vertices]; c = sum(vs, Vector()) / 3
        n = p.normal; pos = neg = 0
        for pt in [c] + [c + (v - c) * 0.7 for v in vs]:
            for d in DIRS:
                if bvh.ray_cast(pt + d * 0.002, d, 20.0)[0] is None:
                    if n.dot(d) >= 0: pos += 1
                    else: neg += 1
            if pos + neg >= 6: break
        if pos + neg == 0: kill.append(p.index)
        elif neg > pos: flip.append(p.index)   # face towards the side it is mostly seen from
    bm = bmesh.new(); bm.from_mesh(me)
    cut = bm.verts.layers.int.get('cut') or bm.verts.layers.int.new('cut')
    bm.faces.ensure_lookup_table()
    for k in flip: bm.faces[k].normal_flip()
    for k in kill:                 # remember where hidden faces were cut away (those borders are not real edges)
        for v in bm.faces[k].verts: v[cut] = 1
    before = len(bm.faces)
    bmesh.ops.delete(bm, geom=[bm.faces[k] for k in kill], context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free()
    print(f'{o.name:14s} faces {before:6d} -> {len(me.polygons):6d}  verts {len(me.vertices)}')
np.save('kidney_right.npy', [k for k in KID if k[:, 0].mean() > 0][0])
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath('prep.blend'))
