# Assemble body + 4 wheels in Unity-friendly form and export FBX (+ .blend).
import bpy, bmesh, sys, os, numpy as np
args = sys.argv[sys.argv.index('--') + 1:]; src, outdir, tag = args[:3]; DEBUG = len(args) > 3
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(src))
sc = bpy.context.scene
SCALE = 4.671 / 5.233                      # GTA model -> real BMW M4 F82 length
OFF = np.array([0.0, 0.025, -0.861])       # origin: on the ground, midway between the axles
WH = {'Wheel_FL': (-0.875, 1.596, -0.501), 'Wheel_FR': (0.875, 1.597, -0.501), 'Wheel_RL': (-0.875, -1.547, -0.501), 'Wheel_RR': (0.875, -1.547, -0.501)}
NAME = 'BMW_M4_LowPoly' + ('' if tag == 'main' else '_' + tag)
R = np.array([-1, -1, 1])                  # 180 deg about Z: car faces -Y in Blender = +Z in Unity
def to_out(p): return (np.asarray(p, float) - OFF) * SCALE * R
wheel = bpy.data.objects['wheel']
parts = [o for o in bpy.data.objects if o.type == 'MESH' and o is not wheel]
# join body parts
bm = bmesh.new()
mats = list(parts[0].data.materials)
for o in parts:
    me = o.data.copy()
    for v in me.vertices: v.co = to_out(v.co[:])
    bm.from_mesh(me); bpy.data.meshes.remove(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
body_me = bpy.data.meshes.new('Body'); bm.to_mesh(body_me); bm.free()
for m in mats: body_me.materials.append(m)
root = bpy.data.objects.new(NAME + f'', None); sc.collection.objects.link(root)
body = bpy.data.objects.new('Body', body_me); sc.collection.objects.link(body); body.parent = root
for name, c in WH.items():
    me = wheel.data.copy(); me.name = name
    bm = bmesh.new(); bm.from_mesh(me)
    for v in bm.verts:
        p = np.array(v.co[:])
        if c[0] < 0: p[0] = -p[0]
        v.co = p * SCALE * R
    if c[0] < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); ob.parent = root
    ob.location = to_out(c)
for o in parts + [wheel]: bpy.data.objects.remove(o)
# optional: shading of the original dense model (NORMALS_FROM=prep.blend)
NREF = None
if os.environ.get('NORMALS_FROM'):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import normals
    NREF = normals.original_mesh(os.path.abspath(os.environ['NORMALS_FROM']), to_out)
# drop unused material slots
for ob in [body] + [o for o in root.children if o.name.startswith('Wheel')]:
    me = ob.data
    used = sorted({p.material_index for p in me.polygons})
    remap = {old: new for new, old in enumerate(used)}
    ms = [me.materials[i] for i in used]
    idx = [remap[p.material_index] for p in me.polygons]
    me.materials.clear()
    for m in ms: me.materials.append(m)
    me.polygons.foreach_set('material_index', np.array(idx, np.int32))
    # double-sided faces: append a reversed copy (shares the vertices)
    att = me.attributes.get('dbl')
    if att is not None and not DEBUG:
        flags = np.zeros(len(me.polygons), np.int32); att.data.foreach_get('value', flags)
        V = [v.co[:] for v in me.vertices]; Fs = [list(p.vertices) for p in me.polygons]; Mi = [p.material_index for p in me.polygons]
        extra = [i for i in range(len(Fs)) if flags[i]]
        new = bpy.data.meshes.new(me.name)
        new.from_pydata(V, [], Fs + [Fs[i][::-1] for i in extra])
        for m in me.materials: new.materials.append(m)
        new.polygons.foreach_set('material_index', np.array(Mi + [Mi[i] for i in extra], np.int32))
        ob.data = new; bpy.data.meshes.remove(me); me = new; me.name = ob.name
    SM = float(os.environ.get('SMOOTH_ANGLE', '0'))
    if NREF is not None and ob is body:
        import normals
        flat = normals.transfer(me, NREF)
        print(f'  normals transferred from the original ({flat} corners kept flat)')
        SM = 0; me.update()
    elif NREF is not None:
        SM = 40.0                         # wheels: smooth by angle
    if NREF is not None and ob is body:
        pass
    elif SM > 0:     # smooth inside panels, hard edges on creases > SM deg and on material / open borders
        import math
        for p in me.polygons: p.use_smooth = True
        fn = np.array([p.normal[:] for p in me.polygons]); mi = np.array([p.material_index for p in me.polygons])
        e2f = {}
        for p in me.polygons:
            for ek in p.edge_keys: e2f.setdefault(ek, []).append(p.index)
        sharp = np.zeros(len(me.edges), bool)
        c = math.cos(math.radians(SM))
        for ed in me.edges:
            fs = e2f.get(ed.key, [])
            if len(fs) != 2 or mi[fs[0]] != mi[fs[1]] or np.dot(fn[fs[0]], fn[fs[1]]) < c: sharp[ed.index] = True
        at = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
        at.data.foreach_set('value', sharp)
    else:
        for p in me.polygons: p.use_smooth = False
    me.update()
    print(f'{ob.name:10s} verts {len(me.vertices):5d} tris {len(me.polygons):5d} materials {[m.name for m in me.materials]}')
for w in bpy.data.worlds: pass
if DEBUG:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(outdir, f'debug_{tag}.blend'))); sys.exit(0)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(outdir, NAME + f'.blend')))
bpy.ops.export_scene.fbx(filepath=os.path.join(outdir, NAME + f'.fbx'), object_types={'EMPTY', 'MESH'},
                         axis_forward='-Z', axis_up='Y', bake_space_transform=True, apply_unit_scale=True,
                         apply_scale_options='FBX_SCALE_ALL', mesh_smooth_type='OFF', use_tspace=False,
                         add_leaf_bones=False, bake_anim=False)
