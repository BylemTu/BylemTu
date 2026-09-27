"""Export the built E36 to game formats.

usage: python3 export.py <e36_sedan.blend> <out_dir>

Writes:
  e36_sedan.glb            whole car, full hierarchy (LOD0)
  e36_sedan_LOD1.glb       whole car, ~45% triangles
  parts/<part>.glb         every swappable part on its own, origin = its socket
  sockets.json             socket name -> parent, position/rotation (glTF, Y-up), tris, file
"""
import json
import math
import os
import sys
import bpy


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons) if ob.type == 'MESH' else 0


def gltf(path, selection):
    bpy.ops.object.select_all(action='DESELECT')
    for o in selection:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True, export_extras=True)


def subtree(ob):
    out = [ob]
    for c in ob.children:
        out += subtree(c)
    return out


def to_gltf(v):
    return [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]


def main():
    blend, out = sys.argv[1], sys.argv[2]
    bpy.ops.wm.open_mainfile(filepath=blend)
    os.makedirs(os.path.join(out, "parts"), exist_ok=True)
    root = bpy.data.objects["E36_Sedan"]
    everything = subtree(root)
    gltf(os.path.join(out, "e36_sedan.glb"), everything)

    sockets = {}
    done_meshes = set()
    for ob in everything[1:]:
        if ob.type == 'EMPTY':            # wheel hubs: sockets without their own mesh
            sockets[ob.name] = dict(parent=ob.parent.name, position=to_gltf(ob.matrix_world.translation),
                                    rotation_y_deg=round(math.degrees(ob.rotation_euler.z), 2),
                                    kind="wheel_hub", file=None, tris=0)
            continue
        mesh_key = ob.data.name
        name = ob.name
        fname = None
        if ob.parent and ob.parent.type == 'EMPTY' and ob.parent.name.startswith("WHEEL_"):
            # the 4 wheels share one mesh per component: export it once
            name_generic = name.rsplit("_", 1)[0]
            fname = f"parts/wheel_{name_generic}.glb"
            if mesh_key not in done_meshes:
                done_meshes.add(mesh_key)
                mw = ob.matrix_world.copy()
                par = ob.parent
                ob.parent = None
                ob.matrix_world.identity()
                gltf(os.path.join(out, fname), [ob])
                ob.parent = par
                ob.matrix_world = mw
        else:
            fname = f"parts/{name}.glb"
            # export the part alone (children are exported as their own parts) at its socket origin
            mw = ob.matrix_world.copy()
            par = ob.parent
            kids = list(ob.children)
            for k in kids:
                k["_mw"] = [list(r) for r in k.matrix_world]
            ob.parent = None
            ob.matrix_world.identity()
            gltf(os.path.join(out, fname), [ob])
            ob.parent = par
            ob.matrix_world = mw
            from mathutils import Matrix
            for k in kids:
                k.matrix_world = Matrix(k["_mw"])
                del k["_mw"]
        sockets[name] = dict(parent=ob.parent.name if ob.parent else None,
                             position=to_gltf(ob.matrix_world.translation),
                             file=fname, tris=tris(ob),
                             materials=[m.name for m in ob.data.materials if m])
    total = sum(tris(o) for o in everything)
    with open(os.path.join(out, "sockets.json"), "w") as f:
        json.dump(dict(model="BMW E36 sedan (non-M, pre-facelift)", units="meters", up="+Y", forward="+Z",
                       total_tris_lod0=total, sockets=sockets), f, indent=1)

    # LOD1: decimate every mesh
    for ob in everything:
        if ob.type == 'MESH' and tris(ob) > 200:
            if ob.data.users > 1:
                ob.data = ob.data.copy()
            m = ob.modifiers.new("lod", 'DECIMATE')
            m.ratio = 0.45
            m.use_collapse_triangulate = True
    gltf(os.path.join(out, "e36_sedan_LOD1.glb"), everything)
    print("LOD0 tris", total)


if __name__ == "__main__":
    main()
