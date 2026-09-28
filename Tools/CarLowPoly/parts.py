# Runs the careful decimator part by part on the right half of the car, then mirrors.
import bpy, bmesh, sys, os, time, numpy as np
sys.path.insert(0, '.')
import decim, kidney, retopo, wheel as W
TOL = float(os.environ.get('RETOPO_TOL', '0.016'))
CREASE_RT = float(os.environ.get('RETOPO_CREASE', '20'))   # low enough to catch rolled panel edges as separate strips
mode, out = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath('prep.blend'))
# vertex budget per part for the WHOLE car (both sides)
BUDGET = {'bodyshell': 1250, 'door_rf': 340, 'door_rf_glass': 16, 'bump_front': 820, 'bump_rear': 520,
          'boot': 250, 'boot_glass': 60, 'bonnet': 200, 'lights': 30, 'lights_glass': 100, 'tail_lights': 20,
          'tail_lights_glass': 110, 'fenders_f': 300, 'fenders_r': 240, 'skirts': 70, 'windscreen': 110, 'wheel': 460}
CREASE = {'wheel': 30.0}
DETAIL = 1.4                     # global multiplier on the budgets above (1.0 = the first, more low-poly, version)
BUDGET = {k: int(v * DETAIL) for k, v in BUDGET.items()}
def mesh_arrays(me):
    V = np.array([v.co[:] for v in me.vertices]); T = np.array([p.vertices[:] for p in me.polygons]); M = np.array([p.material_index for p in me.polygons])
    return V, T, M
def clean(bm, diag=0.035):
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
        if np.linalg.norm(co.max(0) - co.min(0)) < diag: kill += comp
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
total = 0
for ob in sorted([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: o.name):
    name = ob.name
    if name not in BUDGET:
        bpy.data.objects.remove(ob); continue
    t0 = time.time()
    bm = bmesh.new(); bm.from_mesh(ob.data); clean(bm)
    xs = np.array([v.co.x for v in bm.verts])
    sym = name != 'wheel' and xs.min() < -0.05 and xs.max() > 0.05
    if sym:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
        for v in bm.verts:
            if abs(v.co.x) < 1e-5: v.co.x = 0.0
    extra = None
    if name == 'bump_front':      # kidney grilles were cut out in prep; rebuild them clean
        extra = kidney.build(np.load('kidney_right.npy'))
        for f in bm.faces:   # plate strip -> black
            if ob.data.materials[f.material_index].name == 'Headlight': f.material_index = ob.data.materials.find('Black')
    if name in ('windscreen', 'boot_glass', 'tail_lights_glass', 'lights_glass'):   # close small holes in glass (removed interior bits)
        todo = {e for e in bm.edges if e.is_boundary}
        while todo:                      # walk each boundary loop; fill it only if it is small (< 25 cm)
            e0 = todo.pop(); loop = [e0]; st = [e0]
            while st:
                e = st.pop()
                for v in e.verts:
                    for f in v.link_edges:
                        if f in todo: todo.discard(f); loop.append(f); st.append(f)
            co = np.array([v.co[:] for e in loop for v in e.verts])
            if np.linalg.norm(co.max(0) - co.min(0)) < 0.25:
                bmesh.ops.holes_fill(bm, edges=loop, sides=len(loop) + 1)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data); bm.free()
    V, T, M = mesh_arrays(ob.data)
    half = sym or name.startswith('door')
    target = BUDGET[name] // 2 if half else BUDGET[name]
    V2, T2, M2 = V, T, M
    if name == 'wheel':
        wv, wf, wm = W.build(R=0.36, W=0.32)
        wv[:, 0] *= -1; wf = [f[::-1] for f in wf]          # outer face towards +X like the original
        MAP = {'tire': 'Tire', 'sidewall': 'Tire', 'black': 'Tire', 'rim': 'Rim', 'lip': 'Rim', 'hub': 'Brake', 'disc': 'Brake', 'caliper': 'Caliper'}
        if 'Caliper' not in [m.name for m in ob.data.materials]:
            cm = bpy.data.materials.new('Caliper'); cm.use_nodes = True
            cm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.08, 0.45, 1); cm.diffuse_color = (0.02, 0.08, 0.45, 1)
            ob.data.materials.append(cm)
        V2, T2, M2 = wv, np.array([list(f) for f in wf], dtype=object), np.array([ob.data.materials.find(MAP[m]) for m in wm])
        L2 = np.zeros(len(wv), bool); target = 10**9
    if mode == 'retopo' and name != 'wheel':
        V2, F2, M2, fb = retopo.remesh(V, T, M, tol=TOL, seam_x=0.0 if sym else None, crease=CREASE_RT)
        T2 = np.array(F2); L2 = np.zeros(len(V2), bool)
    for crease, cdot in (() if name == 'wheel' or mode == 'retopo' else ((CREASE.get(name, 38.0), -0.6), (50, -0.3), (62, 0.0), (75, 0.3))):   # relax protection only if needed
        V2, T2, M2, L2 = decim.decimate(V2, T2, M2, target, mode=mode, crease=crease, seam_x=0.0 if sym else None, corner_dot=cdot)
        if len(V2) <= target * 1.03: break
    faces = T2.tolist(); fm = M2.tolist(); verts = V2.tolist()
    if extra is not None:
        kv, kf, km = extra; o = len(verts); verts += kv.tolist()
        faces += [[i + o for i in f] for f in kf]; fm += [ob.data.materials.find(m) for m in km]
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    for m in ob.data.materials: me.materials.append(m)
    me.polygons.foreach_set('material_index', np.array(fm, np.int32))
    if half:   # mirror to the other side (seam vertices welded)
        bm = bmesh.new(); bm.from_mesh(me)
        res = bmesh.ops.duplicate(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:])
        dv = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
        for v in dv: v.co.x = -v.co.x
        bmesh.ops.reverse_faces(bm, faces=[g for g in res['geom'] if isinstance(g, bmesh.types.BMFace)])
        if sym: bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if abs(v.co.x) < 1e-6], dist=1e-5)
        bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    old = ob.data; ob.data = me; bpy.data.meshes.remove(old); me.name = name
    ob.name = name.replace('_rf', '')
    if name != 'wheel': total += len(me.vertices)
    print(f'{name:18s} {len(V):6d} -> {len(me.vertices):5d} verts, {len(me.polygons):5d} tris, locked {int(L2.sum())}  ({time.time()-t0:.0f}s)', flush=True)
import post; post.run()
total = sum(len(o.data.vertices) for o in bpy.data.objects if o.type == 'MESH' and o.name != 'wheel')
print('BODY TOTAL verts', total, 'wheel verts', len(bpy.data.objects['wheel'].data.vertices))
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out))
