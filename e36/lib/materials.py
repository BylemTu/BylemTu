"""PBR materials (Principled BSDF only, so they export 1:1 to glTF)."""
import bpy

_CACHE = {}


def _principled(name, color, metallic=0.0, rough=0.5, coat=0.0, alpha=1.0, emission=None,
                transmission=0.0, ior=1.45, double_sided=False, spec=0.5):
    if name in _CACHE:
        return _CACHE[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = ior
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = spec
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.03
    if transmission and "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = transmission
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            m.blend_method = 'BLEND'
    if emission:
        b.inputs["Emission Color"].default_value = (*emission[0], 1.0)
        b.inputs["Emission Strength"].default_value = emission[1]
    m.use_backface_culling = not double_sided
    m.diffuse_color = (*color, alpha)
    _CACHE[name] = m
    return m


def get(name):
    """Named material library for the car."""
    lib = {
        # body colour: E36 "Arktissilber"-ish dark metallic grey like the reference render
        "paint": dict(color=(0.052, 0.054, 0.058), metallic=0.6, rough=0.35, coat=1.0),
        "bumper_plastic": dict(color=(0.03, 0.031, 0.033), rough=0.55, coat=0.2),
        "plastic_black": dict(color=(0.018, 0.018, 0.019), rough=0.62),
        "plastic_textured": dict(color=(0.028, 0.028, 0.03), rough=0.8),
        "trim_black_gloss": dict(color=(0.01, 0.01, 0.01), rough=0.18, coat=0.5),
        "rubber": dict(color=(0.012, 0.012, 0.012), rough=0.85),
        "tyre": dict(color=(0.02, 0.02, 0.021), rough=0.78, spec=0.3),
        "chrome": dict(color=(0.85, 0.85, 0.86), metallic=1.0, rough=0.08),
        "steel_rim": dict(color=(0.025, 0.026, 0.028), metallic=0.4, rough=0.45),
        "metal_raw": dict(color=(0.35, 0.34, 0.33), metallic=1.0, rough=0.55),
        "glass": dict(color=(0.012, 0.014, 0.016), rough=0.03, ior=1.52, spec=0.8, coat=1.0),
        "glass_lamp": dict(color=(0.9, 0.92, 0.95), rough=0.02, alpha=0.18, ior=1.5, double_sided=True),
        "glass_lamp_inner": dict(color=(0.9, 0.9, 0.92), rough=0.12, alpha=0.3, ior=1.5, double_sided=True),
        "mirror": dict(color=(0.9, 0.9, 0.9), metallic=1.0, rough=0.02),
        "reflector": dict(color=(0.9, 0.9, 0.9), metallic=1.0, rough=0.12),
        "lens_red": dict(color=(0.45, 0.01, 0.01), rough=0.12, coat=0.6),
        "lens_red_dark": dict(color=(0.16, 0.005, 0.005), rough=0.12, coat=0.6),
        "lens_orange": dict(color=(0.85, 0.32, 0.02), rough=0.15, coat=0.6),
        "lens_clear": dict(color=(0.75, 0.75, 0.75), rough=0.1, coat=0.5),
        "interior": dict(color=(0.03, 0.03, 0.032), rough=0.85, double_sided=True),
        "interior_fabric": dict(color=(0.05, 0.05, 0.055), rough=0.95),
        "underbody": dict(color=(0.02, 0.02, 0.02), rough=0.9, double_sided=True),
        "wheelwell": dict(color=(0.015, 0.015, 0.016), rough=0.9, double_sided=True),
        "cavity": dict(color=(0.006, 0.006, 0.006), rough=0.9, double_sided=True),
        "plate": dict(color=(0.85, 0.85, 0.85), rough=0.35),
        "plate_text": dict(color=(0.02, 0.02, 0.02), rough=0.4),
        "emblem_blue": dict(color=(0.02, 0.18, 0.55), rough=0.2, coat=1.0),
        "emblem_white": dict(color=(0.85, 0.85, 0.85), rough=0.2, coat=1.0),
        "brake_disc": dict(color=(0.3, 0.29, 0.28), metallic=1.0, rough=0.4),
    }
    return _principled(name, **lib[name])


def reset():
    _CACHE.clear()
