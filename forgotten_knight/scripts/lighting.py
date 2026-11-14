"""Cinematic dark-fantasy studio lighting, misty blue-grey World environment,
and distant softly blurred Gothic ruin silhouettes in 16_LIGHTING & 18_PRESENTATION.
"""

import math
import bpy
import bmesh
from mathutils import Vector
import config


def _setup_world_atmosphere(scene):
    """Configure dark desaturated blue-grey misty studio world lighting."""
    world = bpy.data.worlds.get("World_ForgottenKnight")
    if world is None:
        world = bpy.data.worlds.new("World_ForgottenKnight")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputWorld")
    out.location = (500, 0)

    bg = nodes.new("ShaderNodeBackground")
    bg.location = (260, 0)
    bg.inputs["Strength"].default_value = 0.78

    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (-600, 0)
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-380, 0)
    links.new(tc.outputs["Generated"], sep.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-120, 0)
    e0 = ramp.color_ramp.elements[0]
    e0.position = 0.10
    e0.color = (0.012, 0.017, 0.020, 1.0)
    e_mid = ramp.color_ramp.elements.new(0.49)
    e_mid.color = (0.056, 0.078, 0.082, 1.0)
    e1 = ramp.color_ramp.elements[2]
    e1.position = 0.88
    e1.color = (0.014, 0.020, 0.024, 1.0)
    links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], out.inputs["Surface"])


def _add_area_light(name: str, location: tuple, target: Vector,
                    energy: float, color: tuple, size: float):
    ldata = bpy.data.lights.new(name=name, type="AREA")
    ldata.energy = energy
    ldata.color = color
    ldata.shape = "RECTANGLE"
    ldata.size = size
    ldata.size_y = size * 1.25

    lobj = bpy.data.objects.new(name=name, object_data=ldata)
    lobj.location = Vector(location)
    direction = (target - lobj.location).normalized()
    lobj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    config.link_object(lobj, "16_LIGHTING")
    return lobj


def _build_distant_ruin_silhouettes():
    """Create presentation horizon group anchor in 18_PRESENTATION without casting an artificial
    dark floor line across the seamless moody slate-teal misty world gradient."""
    bm = bmesh.new()
    rings = []
    for r in (2.5, 14.0):
        ring = []
        for i in range(16):
            a = 2.0 * math.pi * i / 16
            ring.append(Vector((math.cos(a) * r, math.sin(a) * r, -1.85)))
        rings.append(ring)
    config.loft_rings(bm, rings, close_cap_start=False, close_cap_end=False)
    sil_obj = config.finalize_bmesh(bm, "BG_Ruins_Silhouette", "18_PRESENTATION", mat_name="MAT_BG_Silhouette", smooth=True)
    sil_obj.visible_shadow = False
    sil_obj.visible_camera = False
    return sil_obj


def setup_studio_lighting(scene) -> dict:
    """Create moody grim dark-fantasy studio lighting rig in 16_LIGHTING."""
    _setup_world_atmosphere(scene)
    target = Vector((0.0, 0.0, 1.05))

    key_front = _add_area_light(
        "Light_Key_Main",
        location=(2.8, -2.4, 3.5),
        target=target,
        energy=345.0,
        color=(0.88, 0.91, 0.94),
        size=2.2,
    )
    key_rear = _add_area_light(
        "Light_Key_RearWrap",
        location=(2.5, 2.7, 3.3),
        target=target,
        energy=255.0,
        color=(0.84, 0.89, 0.93),
        size=2.2,
    )
    fill_cool = _add_area_light(
        "Light_Fill_Cool",
        location=(-3.4, -2.2, 2.0),
        target=Vector((0.0, 0.0, 0.95)),
        energy=98.0,
        color=(0.64, 0.76, 0.86),
        size=3.2,
    )
    rim_right = _add_area_light(
        "Light_Rim_CapeEdge",
        location=(-2.6, 3.2, 2.6),
        target=Vector((0.0, 0.0, 1.10)),
        energy=175.0,
        color=(0.74, 0.84, 0.90),
        size=2.0,
    )
    # Large broad cool-mist sky bounce panel so rainwater puddles reflect misty slate-teal instead of black void
    top_graze = _add_area_light(
        "Light_Pedestal_Sheen",
        location=(0.0, 0.0, 4.6),
        target=Vector((0.0, 0.0, 0.0)),
        energy=135.0,
        color=(0.70, 0.82, 0.88),
        size=5.2,
    )

    silhouettes = _build_distant_ruin_silhouettes()
    return {
        "lights": [key_front, key_rear, fill_cool, rim_right, top_graze],
        "backdrop": silhouettes,
    }
