# 30 close-up review shots around the car (10 directions x 3 heights), back faces culled like in Unity.
# usage: python3 review.py -- <debug blend> <out prefix>
import bpy, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rend
args = sys.argv[sys.argv.index('--') + 1:]
blend, prefix = args[0], args[1]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
for m in bpy.data.materials:
    if not m.use_nodes: continue
    nt = m.node_tree; out = nt.nodes['Material Output']; bsdf = nt.nodes['Principled BSDF']
    geo = nt.nodes.new('ShaderNodeNewGeometry'); mix = nt.nodes.new('ShaderNodeMixShader'); tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'dbl'; at.attribute_type = 'GEOMETRY'
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; one = nt.nodes.new('ShaderNodeMath'); one.operation = 'SUBTRACT'
    one.inputs[0].default_value = 1.0; nt.links.new(at.outputs['Fac'], one.inputs[1])
    nt.links.new(geo.outputs['Backfacing'], mul.inputs[0]); nt.links.new(one.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], mix.inputs[0]); nt.links.new(bsdf.outputs[0], mix.inputs[1]); nt.links.new(tr.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs[0])
bpy.ops.mesh.primitive_plane_add(size=60); g = bpy.context.object
gm = bpy.data.materials.new('gr'); gm.use_nodes = True; gm.node_tree.nodes['Principled BSDF'].inputs[0].default_value = (0.42, 0.43, 0.45, 1); g.data.materials.append(gm)
co = rend.setup((640, 400)); bpy.context.scene.cycles.samples = 40
i = 0
for h_t, h_c in ((0.45, 0.55), (0.85, 1.25), (1.2, 2.1)):
    for k in range(10):
        a = 2 * math.pi * (k + 0.5 * (h_t > 0.5)) / 10
        tx, ty = 0.85 * math.cos(a), 2.0 * math.sin(a)
        dx, dy = math.cos(a) * 2.0, math.sin(a) * 1.0
        n = math.hypot(dx, dy); dx, dy = dx / n * 2.1, dy / n * 2.1
        rend.shot(co, (tx + dx, ty + dy, h_c), (tx, ty, h_t), f'{prefix}_{i:02d}.png', 35)
        i += 1
