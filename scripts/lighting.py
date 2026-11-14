"""Late afternoon overcast-meets-sunlight world sky and key directional sun."""

import math
from typing import Dict, List

import bpy
from mathutils import Vector

from config import LAYOUT


def _sun_direction_vector(elevation_deg: float, azimuth_deg: float) -> Vector:
    """Compute unit vector pointing FROM scene TOWARD the sun (azimuth clockwise from +Y toward +X)."""
    el = math.radians(elevation_deg)
    az = math.radians(azimuth_deg)
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))).normalized()


def setup_lighting(cols: Dict[str, bpy.types.Collection]) -> List[bpy.types.Object]:
    """Configure physical procedural sky with left-cool / right-warm overcast gradient and key Sun."""
    col = cols["11_LIGHTING"]
    lcfg = LAYOUT["lighting"]

    world = bpy.data.worlds.get("World_Drowned_Sanctuary") or bpy.data.worlds.new("World_Drowned_Sanctuary")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (860, 0)

    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (620, 0)
    bg.inputs["Strength"].default_value = lcfg["sky_strength"]
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # Physical atmospheric scattering sky
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.location = (-360, 220)
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_disc = False
    sky.sun_elevation = math.radians(lcfg["sun_elevation_deg"])
    sky.sun_rotation = math.radians(-lcfg["sun_azimuth_deg"])
    sky.altitude = 120.0
    sky.air_density = lcfg["air_density"]
    sky.aerosol_density = lcfg["aerosol_density"]
    sky.ozone_density = lcfg["ozone_density"]

    # Direction-based overcast sky modulation: dark slate left (-X) -> warm bright silver-gold right (+X)
    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-950, -160)

    sky_glow_vec = _sun_direction_vector(
        lcfg["sun_elevation_deg"] - 4.0,
        lcfg.get("sky_glow_azimuth_deg", 56.0),
    )
    sun_vec = _sun_direction_vector(lcfg["sun_elevation_deg"], lcfg["sun_azimuth_deg"])
    dot_sun = nt.nodes.new("ShaderNodeVectorMath")
    dot_sun.operation = "DOT_PRODUCT"
    dot_sun.location = (-680, -100)
    dot_sun.inputs[1].default_value = (sky_glow_vec.x, sky_glow_vec.y, sky_glow_vec.z)
    nt.links.new(tex_coord.outputs["Generated"], dot_sun.inputs[0])

    # Soft cloud wisps across sky dome
    cloud_noise = nt.nodes.new("ShaderNodeTexNoise")
    cloud_noise.location = (-680, -340)
    cloud_noise.inputs["Scale"].default_value = 3.6
    cloud_noise.inputs["Detail"].default_value = 6.0
    cloud_noise.inputs["Roughness"].default_value = 0.62
    nt.links.new(tex_coord.outputs["Generated"], cloud_noise.inputs["Vector"])

    # Map dot_sun (-1..+1) -> 0..1 glow toward upper-right horizon
    sun_glow_map = nt.nodes.new("ShaderNodeMapRange")
    sun_glow_map.location = (-440, -100)
    sun_glow_map.clamp = True
    sun_glow_map.inputs["From Min"].default_value = -0.35
    sun_glow_map.inputs["From Max"].default_value = 0.85
    nt.links.new(dot_sun.outputs["Value"], sun_glow_map.inputs["Value"])

    # Cool overcast slate gradient on left vs warm silver-champagne haze on right
    ramp_sky_tint = nt.nodes.new("ShaderNodeValToRGB")
    ramp_sky_tint.location = (-200, -100)
    ramp_sky_tint.color_ramp.elements[0].position = 0.08
    ramp_sky_tint.color_ramp.elements[0].color = (0.09, 0.125, 0.135, 1.0)
    e_mid = ramp_sky_tint.color_ramp.elements.new(0.55)
    e_mid.color = (0.28, 0.31, 0.30, 1.0)
    ramp_sky_tint.color_ramp.elements[2].position = 0.94
    ramp_sky_tint.color_ramp.elements[2].color = (1.15, 1.08, 0.88, 1.0)
    nt.links.new(sun_glow_map.outputs["Result"], ramp_sky_tint.inputs["Fac"])

    # Multiply subtle cloud texture into overcast tint
    cloud_ramp = nt.nodes.new("ShaderNodeValToRGB")
    cloud_ramp.location = (-420, -340)
    cloud_ramp.color_ramp.elements[0].position = 0.25
    cloud_ramp.color_ramp.elements[0].color = (0.68, 0.72, 0.74, 1.0)
    cloud_ramp.color_ramp.elements[1].position = 0.75
    cloud_ramp.color_ramp.elements[1].color = (1.08, 1.06, 1.0, 1.0)
    nt.links.new(cloud_noise.outputs["Fac"], cloud_ramp.inputs["Fac"])

    mult_cloud = nt.nodes.new("ShaderNodeMix")
    mult_cloud.data_type = "RGBA"
    mult_cloud.blend_type = "MULTIPLY"
    mult_cloud.location = (60, -160)
    mult_cloud.inputs["Factor"].default_value = 0.85
    nt.links.new(ramp_sky_tint.outputs["Color"], mult_cloud.inputs[6])
    nt.links.new(cloud_ramp.outputs["Color"], mult_cloud.inputs[7])

    mix_sky = nt.nodes.new("ShaderNodeMix")
    mix_sky.data_type = "RGBA"
    mix_sky.location = (320, 60)
    mix_sky.inputs["Factor"].default_value = 0.65
    nt.links.new(sky.outputs["Color"], mix_sky.inputs[6])
    nt.links.new(mult_cloud.outputs[2], mix_sky.inputs[7])
    nt.links.new(mix_sky.outputs[2], bg.inputs["Color"])

    # 2. Primary Warm Late-Afternoon Key Sun Light (shining from upper-right toward front-left)
    sun_data = bpy.data.lights.new("SUN_Key_LateAfternoon", type="SUN")
    sun_data.energy = lcfg["sun_energy"]
    sun_data.angle = math.radians(lcfg["sun_angle_deg"])
    sun_data.color = lcfg["sun_color"]

    sun_obj = bpy.data.objects.new("SUN_Key_LateAfternoon", sun_data)
    sun_obj.location = (sun_vec.x * 80.0, sun_vec.y * 80.0, sun_vec.z * 80.0 + 25.0)
    light_dir = -sun_vec
    sun_obj.rotation_euler = light_dir.to_track_quat("-Z", "Y").to_euler()
    col.objects.link(sun_obj)

    # 3. Very subtle cool sky fill from upper-left to preserve readable stone carving inside shadows
    fill_data = bpy.data.lights.new("AREA_CoolSky_Fill", type="AREA")
    fill_data.energy = 800.0
    fill_data.size = 55.0
    fill_data.color = (0.48, 0.64, 0.78)

    fill_obj = bpy.data.objects.new("AREA_CoolSky_Fill", fill_data)
    fill_obj.location = (-55.0, -55.0, 52.0)
    fill_dir = (Vector((0.0, 2.0, 10.0)) - fill_obj.location).normalized()
    fill_obj.rotation_euler = fill_dir.to_track_quat("-Z", "Y").to_euler()
    col.objects.link(fill_obj)

    return [sun_obj, fill_obj]
