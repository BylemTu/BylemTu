# Hole check that mimics Unity back-face culling: back faces are transparent and a red backdrop shows through holes.
import bpy, sys, os; sys.path.insert(0, '.')
import rend
blend, prefix = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
for m in bpy.data.materials:
    nt = m.node_tree; out = nt.nodes['Material Output']; bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Metallic'].default_value = 0; bsdf.inputs['Roughness'].default_value = 1
    geo = nt.nodes.new('ShaderNodeNewGeometry'); mix = nt.nodes.new('ShaderNodeMixShader'); tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'dbl'; at.attribute_type = 'GEOMETRY'
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; one = nt.nodes.new('ShaderNodeMath'); one.operation = 'SUBTRACT'
    one.inputs[0].default_value = 1.0; nt.links.new(at.outputs['Fac'], one.inputs[1])
    nt.links.new(geo.outputs['Backfacing'], mul.inputs[0]); nt.links.new(one.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], mix.inputs[0]); nt.links.new(bsdf.outputs[0], mix.inputs[1]); nt.links.new(tr.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs[0])
co = rend.setup((800, 460))
w = bpy.context.scene.world.node_tree.nodes['Background']; w.inputs[0].default_value = (1, 0, 0, 1); w.inputs[1].default_value = 1.0
bpy.context.scene.cycles.samples = 16
for i, (loc, tgt) in enumerate((((-5.2, -5.6, 2.2), (0, 0, 0.55)), ((5.0, 5.4, 2.4), (0, 0, 0.55)), ((9, 0, 0.7), (0, 0, 0.7)), ((-9, 0, 1.6), (0, 0, 0.6)), ((0, -8, 1.0), (0, 0, 0.6)), ((0, 8, 1.4), (0, 0, 0.6)), ((3, -1, 6), (0, 0, 0.5)))):
    rend.shot(co, loc, tgt, f'{prefix}_h{i}.png', 45)
rend.shot(co, (-0.3, 5.5, 2.4), (0, 1.9, 0.95), f'{prefix}_rw.png', 60)
