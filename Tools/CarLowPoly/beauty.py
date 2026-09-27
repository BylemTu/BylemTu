# Presentation renders (back faces culled like in Unity; faces flagged 'dbl' render two-sided).
import bpy, sys, os, math; sys.path.insert(0, '.')
import rend
args = sys.argv[sys.argv.index('--') + 1:]
blend, prefix, wire = args[0], args[1], len(args) > 2
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
for m in bpy.data.materials:
    nt = m.node_tree; out = nt.nodes['Material Output']; bsdf = nt.nodes['Principled BSDF']
    geo = nt.nodes.new('ShaderNodeNewGeometry'); mix = nt.nodes.new('ShaderNodeMixShader'); tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'dbl'; at.attribute_type = 'GEOMETRY'
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; one = nt.nodes.new('ShaderNodeMath'); one.operation = 'SUBTRACT'
    one.inputs[0].default_value = 1.0; nt.links.new(at.outputs['Fac'], one.inputs[1])
    nt.links.new(geo.outputs['Backfacing'], mul.inputs[0]); nt.links.new(one.outputs[0], mul.inputs[1])
    nt.links.new(mul.outputs[0], mix.inputs[0]); nt.links.new(bsdf.outputs[0], mix.inputs[1]); nt.links.new(tr.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs[0])
if wire:
    wm = bpy.data.materials.new('wire'); wm.use_nodes = True; wm.node_tree.nodes['Principled BSDF'].inputs[0].default_value = (0, 0, 0, 1)
    for o in [o for o in bpy.data.objects if o.type == 'MESH']:
        w = o.copy(); w.data = o.data.copy(); bpy.context.scene.collection.objects.link(w)
        w.data.materials.clear(); w.data.materials.append(wm)
        md = w.modifiers.new('w', 'WIREFRAME'); md.thickness = 0.006; md.use_replace = True; md.use_even_offset = False; md.use_relative_offset = False; md.material_offset = 0
bpy.ops.mesh.primitive_plane_add(size=60); g = bpy.context.object
gm = bpy.data.materials.new('gr'); gm.use_nodes = True; gm.node_tree.nodes['Principled BSDF'].inputs[0].default_value = (0.42, 0.43, 0.45, 1); g.data.materials.append(gm)
co = rend.setup((1280, 720))
sc = bpy.context.scene; sc.cycles.samples = 96
try: sc.cycles.use_denoising = True
except Exception: pass
sc.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
rend.shot(co, (-4.6, -5.4, 1.9), (0, -0.2, 0.55), prefix + '_front.png', 42)
rend.shot(co, (4.4, 5.3, 2.1), (0, 0.2, 0.55), prefix + '_rear.png', 42)
rend.shot(co, (7.5, 0, 0.75), (0, 0, 0.62), prefix + '_side.png', ortho=5.2)
