"""Import the GTA:SA E36 mod (comet.dff) and save its stock exterior panels,
already placed in this generator's frame (Blender: car faces -Y, Z up, metres,
ground at z=0, axle midpoint at origin).

usage: python3 tools/extract_mod.py <path/to/DragonFF parent dir> <comet.dff> <out.blend>

DragonFF (https://github.com/Parik27/DragonFF) is used only as a DFF reader.
The resulting .blend is an intermediate file; it is not part of the repo.
"""
import math
import sys
import bpy

K = 2.70 / (1.733 + 1.28)          # GTA scale -> real wheelbase 2700 mm
Y0 = (1.733 - 1.28) / 2            # axle midpoint in mod space
LIFT = 0.035                       # undo the mod's lowered stance
Z_SCALE = 1.06                     # GTA body is squashed: belt 0.86 -> 0.91 m like the real E36

ROLES = {
    "default": "shell", "chassis.001": "rear_panel", "chassis.002": "front_panel",
    "bump_front_ok": "bumper_F", "Zderzaktyl": "bumper_R", "bonnet_ok": "hood", "boot_ok": "trunk_lid",
    "door_lf_ok": "door_R_coupe", "door_rf_ok": "door_L_coupe", "kierunybok": "side_repeaters",
    "klosz": "tail_lens", "lights": "head_lamps", "klosz.002": "head_lens", "chassis.003": "kidneys",
}


def main():
    ddir, dff, out = sys.argv[-3:]
    sys.path.insert(0, ddir)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import DragonFF
    DragonFF.register()
    bpy.ops.import_scene.dff(filepath=dff)
    keep = []
    for ob in list(bpy.data.objects):
        if ob.type != 'MESH' or ob.name not in ROLES:
            continue
        mw = ob.matrix_world.copy()
        me = ob.data.copy()
        me.transform(mw)
        nob = bpy.data.objects.new("MOD_" + ROLES[ob.name], me)
        bpy.context.scene.collection.objects.link(nob)
        keep.append(nob)
    for ob in list(bpy.data.objects):
        if ob not in keep:
            bpy.data.objects.remove(ob)
    import mathutils
    T = (mathutils.Matrix.Scale(Z_SCALE, 4, (0, 0, 1)) @ mathutils.Matrix.Translation((0, 0, LIFT))
         @ mathutils.Matrix.Scale(K, 4)
         @ mathutils.Matrix.Rotation(math.pi, 4, 'Z') @ mathutils.Matrix.Translation((0, -Y0, 0.69)))
    for ob in keep:
        ob.data.transform(T)
        # drop degenerate / far-away garbage vertices some GTA meshes carry
        bad = [v.index for v in ob.data.vertices if max(abs(c) for c in v.co) > 6]
        if bad:
            import bmesh
            bm = bmesh.new(); bm.from_mesh(ob.data)
            bm.verts.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.verts[i] for i in bad], context='VERTS')
            bm.to_mesh(ob.data); bm.free()
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("saved", out, [o.name for o in keep])


if __name__ == "__main__":
    main()
