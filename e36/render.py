"""Render the E36 model from the standard review angles (Cycles, headless).

usage: python3 render.py <file.blend> <out_dir> [samples] [res_x] [views...]
"""
import math
import os
import sys
import bpy
import mathutils

VIEWS = {
    #   name        (azimuth deg, elevation deg, distance, focal mm, target z, ortho)
    "side": (90, 2, 11.0, 70, 0.62, True),
    "front34": (35, 12, 8.5, 55, 0.6, False),
    "rear34": (145, 14, 8.5, 55, 0.6, False),
    "front": (0, 3, 9.0, 70, 0.62, True),
    "rear": (180, 3, 9.0, 70, 0.62, True),
    "top": (90, 89.9, 9.0, 60, 0.0, True),
    "front34_low": (25, 5, 6.5, 40, 0.55, False),
    "detail_front": (28, 10, 3.6, 50, 0.55, False),
    "detail_rear": (150, 12, 3.6, 50, 0.7, False),
    "detail_cpillar": (120, 8, 3.4, 50, 1.0, False),
    "mod_front": (25, 10, 3.4, 50, 0.1, False),
    "mod_rear": (155, 12, 3.4, 50, 0.2, False),
    "left34": (-40, 12, 8.5, 55, 0.6, False),
}


def setup_scene(samples, res_x):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.render.resolution_x = res_x
    sc.render.resolution_y = int(res_x * 9 / 16)
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    # studio world: soft grey gradient
    world = bpy.data.worlds.new("studio")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (0.25, 0.25, 0.26, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
    map_ = nt.nodes.new("ShaderNodeMapRange")
    map_.inputs["From Min"].default_value = -1
    map_.inputs["From Max"].default_value = 1
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(tc.outputs["Normal"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], map_.inputs["Value"])
    nt.links.new(map_.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.6
    # cyclorama floor
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    fl = bpy.context.active_object
    fl.name = "_floor"
    m = bpy.data.materials.new("_floor")
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.62, 0.63, 0.65, 1)
    p.inputs["Roughness"].default_value = 0.35
    fl.data.materials.append(m)
    # key lights: big soft boxes like a photo studio
    def area(name, loc, size, energy, rot):
        l = bpy.data.lights.new(name, 'AREA')
        l.size = size
        l.energy = energy
        o = bpy.data.objects.new(name, l)
        sc.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = rot
        return o
    area("_top", (0, 0, 7), 7, 700, (0, 0, 0))
    area("_side_l", (7, 0, 3.5), 5, 350, (0, math.radians(60), 0))
    area("_side_r", (-7, 1, 3.5), 5, 250, (0, math.radians(-60), 0))
    area("_front", (0, -8, 3), 4, 220, (math.radians(65), 0, 0))
    area("_back", (0, 8, 3), 4, 220, (math.radians(-65), 0, 0))


def camera_for(view):
    az, el, dist, focal, tz, ortho = VIEWS[view]
    sc = bpy.context.scene
    cam = bpy.data.objects.get("_cam")
    if cam is None:
        cam = bpy.data.objects.new("_cam", bpy.data.cameras.new("_cam"))
        sc.collection.objects.link(cam)
    sc.camera = cam
    # azimuth measured from car front (-Y) toward car left (+X)
    a, e = math.radians(az), math.radians(el)
    d = mathutils.Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    target = mathutils.Vector((0, 0.08, tz))
    if view == "detail_front":
        target = mathutils.Vector((0.25, -1.7, tz))
    elif view == "detail_rear":
        target = mathutils.Vector((0.25, 1.8, tz))
    elif view == "mod_front":
        target = mathutils.Vector((0.0, -2.3, 0.1))
    elif view == "mod_rear":
        target = mathutils.Vector((0.0, 2.3, 0.2))
    elif view == "detail_cpillar":
        target = mathutils.Vector((0.7, 1.0, tz))
    cam.location = target + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = focal
    cam.data.clip_end = 200
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = 5.2 if view in ("side", "top") else 2.4 * 1.9
    else:
        cam.data.type = 'PERSP'


def explode():
    """Pull every top-level part away from the body to show the part split."""
    root = bpy.data.objects.get("E36_Sedan")
    for ob in list(root.children):
        if ob.name.startswith("body") or ob.name in ("interior", "headliner"):
            continue
        p = ob.matrix_world.translation.copy()
        d = mathutils.Vector((p.x * 0.9, p.y * 0.35, max(p.z - 0.5, 0) * 1.2))
        if ob.name.startswith("WHEEL_"):
            d = mathutils.Vector((p.x * 0.6, 0, 0))
        ob.location += d


def main():
    argv = sys.argv[1:]
    blend, out = argv[0], argv[1]
    samples = int(argv[2]) if len(argv) > 2 else 48
    res = int(argv[3]) if len(argv) > 3 else 1280
    views = argv[4:] or ["side", "front34", "rear34", "front", "rear", "top"]
    if blend.endswith(".glb"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=blend)
    else:
        bpy.ops.wm.open_mainfile(filepath=blend)
    setup_scene(samples, res)
    os.makedirs(out, exist_ok=True)
    for v in views:
        if v == "exploded":
            explode()
            camera_for("front34")
            cam = bpy.context.scene.camera
            cam.location *= 1.25
        else:
            camera_for(v)
        bpy.context.scene.render.filepath = os.path.join(out, v + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", v)


if __name__ == "__main__":
    main()
