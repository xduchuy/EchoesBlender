"""Procedural PBR material library for The Drowned Sanctuary (Blender 5.3)."""

from typing import Dict, Tuple

import bpy

from config import COLORS


def _new_material(name: str) -> Tuple[bpy.types.Material, bpy.types.NodeTree, bpy.types.Node, bpy.types.Node]:
    """Create or reset a material with clean Principled BSDF and Material Output."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, nt, bsdf, out


def _add_triplanar_stone_coords(nt: bpy.types.NodeTree, pos_out, nrm_out=None, x_loc: int = -1100):
    """Build true axis-selected triplanar UV coordinates ((X,Z), (Y,Z), or (X,Y)) for stone masonry."""
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (x_loc, -250)
    nt.links.new(pos_out, sep.inputs["Vector"])

    # Candidate planar projections without X+Y diagonal shearing
    comb_xz = nt.nodes.new("ShaderNodeCombineXYZ")
    comb_xz.location = (x_loc + 180, -140)
    nt.links.new(sep.outputs["X"], comb_xz.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb_xz.inputs["Y"])

    if nrm_out is None:
        return sep, comb_xz

    comb_yz = nt.nodes.new("ShaderNodeCombineXYZ")
    comb_yz.location = (x_loc + 180, -250)
    nt.links.new(sep.outputs["Y"], comb_yz.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb_yz.inputs["Y"])

    comb_xy = nt.nodes.new("ShaderNodeCombineXYZ")
    comb_xy.location = (x_loc + 180, -360)
    nt.links.new(sep.outputs["X"], comb_xy.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb_xy.inputs["Y"])

    abs_n = nt.nodes.new("ShaderNodeVectorMath")
    abs_n.operation = "ABSOLUTE"
    abs_n.location = (x_loc - 120, -430)
    nt.links.new(nrm_out, abs_n.inputs[0])

    sep_n = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep_n.location = (x_loc + 30, -430)
    nt.links.new(abs_n.outputs["Vector"], sep_n.inputs["Vector"])

    cmp_xy = nt.nodes.new("ShaderNodeMath")
    cmp_xy.operation = "GREATER_THAN"
    cmp_xy.location = (x_loc + 180, -460)
    nt.links.new(sep_n.outputs["X"], cmp_xy.inputs[0])
    nt.links.new(sep_n.outputs["Y"], cmp_xy.inputs[1])

    mix_side = nt.nodes.new("ShaderNodeMix")
    mix_side.data_type = "VECTOR"
    mix_side.location = (x_loc + 360, -220)
    nt.links.new(cmp_xy.outputs["Value"], mix_side.inputs["Factor"])
    nt.links.new(comb_xz.outputs["Vector"], mix_side.inputs[4])
    nt.links.new(comb_yz.outputs["Vector"], mix_side.inputs[5])

    cmp_top = nt.nodes.new("ShaderNodeMapRange")
    cmp_top.location = (x_loc + 200, -560)
    cmp_top.clamp = True
    cmp_top.inputs["From Min"].default_value = 0.60
    cmp_top.inputs["From Max"].default_value = 0.78
    nt.links.new(sep_n.outputs["Z"], cmp_top.inputs["Value"])

    mix_tri = nt.nodes.new("ShaderNodeMix")
    mix_tri.data_type = "VECTOR"
    mix_tri.location = (x_loc + 520, -240)
    nt.links.new(cmp_top.outputs["Result"], mix_tri.inputs["Factor"])
    nt.links.new(mix_side.outputs[1], mix_tri.inputs[4])
    nt.links.new(comb_xy.outputs["Vector"], mix_tri.inputs[5])

    # Keep unified `.outputs["Vector"]` contract for brick_warp via Reroute / Separate->Combine wrapper
    out_comb = nt.nodes.new("ShaderNodeCombineXYZ")
    out_comb.location = (x_loc + 680, -240)
    sep_out = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep_out.location = (x_loc + 600, -240)
    nt.links.new(mix_tri.outputs[1], sep_out.inputs["Vector"])
    nt.links.new(sep_out.outputs["X"], out_comb.inputs["X"])
    nt.links.new(sep_out.outputs["Y"], out_comb.inputs["Y"])
    return sep, out_comb


def build_limestone_material(
    name: str,
    color_a: Tuple[float, float, float, float],
    color_b: Tuple[float, float, float, float],
    shadow_col: Tuple[float, float, float, float],
    moss_amount: float = 0.25,
    wet_height: float = 2.4,
    base_roughness: float = 0.84,
    bump_strength: float = 0.28,
    mortar_strength: float = 0.35,
) -> bpy.types.Material:
    """Build procedural weathered limestone with mortar courses, waterline dampness, moss, and edge wear."""
    mat, nt, bsdf, _ = _new_material(name)

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1350, 0)

    sep_pos, brick_vec = _add_triplanar_stone_coords(
        nt, geo.outputs["Position"], geo.outputs["Normal"], -1100
    )

    # Broad mineral weathering noise
    noise_macro = nt.nodes.new("ShaderNodeTexNoise")
    noise_macro.location = (-800, 300)
    noise_macro.inputs["Scale"].default_value = 0.14
    noise_macro.inputs["Detail"].default_value = 6.0
    noise_macro.inputs["Roughness"].default_value = 0.65
    nt.links.new(geo.outputs["Position"], noise_macro.inputs["Vector"])

    # Medium stone grain
    noise_med = nt.nodes.new("ShaderNodeTexNoise")
    noise_med.location = (-800, 80)
    noise_med.inputs["Scale"].default_value = 1.6
    noise_med.inputs["Detail"].default_value = 8.0
    noise_med.inputs["Roughness"].default_value = 0.7
    nt.links.new(geo.outputs["Position"], noise_med.inputs["Vector"])

    # Fine micro grain
    noise_fine = nt.nodes.new("ShaderNodeTexNoise")
    noise_fine.location = (-800, -520)
    noise_fine.inputs["Scale"].default_value = 11.0
    noise_fine.inputs["Detail"].default_value = 5.0
    noise_fine.inputs["Roughness"].default_value = 0.6
    nt.links.new(geo.outputs["Position"], noise_fine.inputs["Vector"])

    # Stone block courses (mortar + subtle per-block color shift)
    brick_warp = nt.nodes.new("ShaderNodeMix")
    brick_warp.data_type = "VECTOR"
    brick_warp.location = (-580, -240)
    brick_warp.inputs["Factor"].default_value = 0.045
    nt.links.new(brick_vec.outputs["Vector"], brick_warp.inputs[4])
    nt.links.new(noise_med.outputs["Color"], brick_warp.inputs[5])

    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.location = (-380, -240)
    brick.offset = 0.5
    brick.squash = 1.0
    brick.inputs["Scale"].default_value = 1.15
    brick.inputs["Mortar Size"].default_value = 0.014
    brick.inputs["Mortar Smooth"].default_value = 0.25
    brick.inputs["Bias"].default_value = 0.0
    brick.inputs["Brick Width"].default_value = 1.25
    brick.inputs["Row Height"].default_value = 0.52
    brick.inputs["Color1"].default_value = color_a
    brick.inputs["Color2"].default_value = color_b
    brick.inputs["Mortar"].default_value = (0.045, 0.048, 0.042, 1.0)
    nt.links.new(brick_warp.outputs[1], brick.inputs["Vector"])

    # Mix macro weathering across stone blocks
    mix_macro = nt.nodes.new("ShaderNodeMix")
    mix_macro.data_type = "RGBA"
    mix_macro.location = (-160, 120)
    mix_macro.inputs[7].default_value = shadow_col
    nt.links.new(noise_macro.outputs["Fac"], mix_macro.inputs["Factor"])
    nt.links.new(brick.outputs["Color"], mix_macro.inputs[6])

    # Subtle edge highlight using Pointiness
    ramp_point = nt.nodes.new("ShaderNodeValToRGB")
    ramp_point.location = (-400, 480)
    ramp_point.color_ramp.elements[0].position = 0.48
    ramp_point.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_point.color_ramp.elements[1].position = 0.62
    ramp_point.color_ramp.elements[1].color = (0.35, 0.35, 0.35, 1.0)
    nt.links.new(geo.outputs["Pointiness"], ramp_point.inputs["Fac"])

    mix_edge = nt.nodes.new("ShaderNodeMix")
    mix_edge.data_type = "RGBA"
    mix_edge.blend_type = "ADD"
    mix_edge.location = (20, 220)
    mix_edge.inputs[7].default_value = (0.14, 0.13, 0.10, 1.0)
    nt.links.new(ramp_point.outputs["Color"], mix_edge.inputs["Factor"])
    nt.links.new(mix_macro.outputs[2], mix_edge.inputs[6])

    # Upward-facing moss mask (Normal.Z * macro noise)
    sep_n = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep_n.location = (-600, 620)
    nt.links.new(geo.outputs["Normal"], sep_n.inputs["Vector"])

    ramp_up = nt.nodes.new("ShaderNodeValToRGB")
    ramp_up.location = (-400, 640)
    ramp_up.color_ramp.elements[0].position = 0.35
    ramp_up.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_up.color_ramp.elements[1].position = 0.85
    ramp_up.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(sep_n.outputs["Z"], ramp_up.inputs["Fac"])

    moss_mult = nt.nodes.new("ShaderNodeMath")
    moss_mult.operation = "MULTIPLY"
    moss_mult.location = (-180, 560)
    nt.links.new(ramp_up.outputs["Color"], moss_mult.inputs[0])
    nt.links.new(noise_macro.outputs["Fac"], moss_mult.inputs[1])

    moss_scale = nt.nodes.new("ShaderNodeMath")
    moss_scale.operation = "MULTIPLY"
    moss_scale.location = (0, 560)
    moss_scale.inputs[1].default_value = moss_amount * 1.6
    nt.links.new(moss_mult.outputs["Value"], moss_scale.inputs[0])

    mix_moss = nt.nodes.new("ShaderNodeMix")
    mix_moss.data_type = "RGBA"
    mix_moss.location = (190, 260)
    mix_moss.inputs[7].default_value = COLORS["moss_olive"]
    nt.links.new(moss_scale.outputs["Value"], mix_moss.inputs["Factor"])
    nt.links.new(mix_edge.outputs[2], mix_moss.inputs[6])

    # Waterline dampness mask based on World Z (darkens & makes wet near Z <= wet_height)
    wet_map = nt.nodes.new("ShaderNodeMapRange")
    wet_map.location = (-360, -480)
    wet_map.clamp = True
    wet_map.inputs["From Min"].default_value = -0.2
    wet_map.inputs["From Max"].default_value = max(0.3, wet_height)
    wet_map.inputs["To Min"].default_value = 1.0
    wet_map.inputs["To Max"].default_value = 0.0
    nt.links.new(sep_pos.outputs["Z"], wet_map.inputs["Value"])

    # Modulate waterline unevenly with medium noise
    wet_noise = nt.nodes.new("ShaderNodeMath")
    wet_noise.operation = "MULTIPLY"
    wet_noise.location = (-160, -480)
    nt.links.new(wet_map.outputs["Result"], wet_noise.inputs[0])
    nt.links.new(noise_med.outputs["Fac"], wet_noise.inputs[1])

    wet_clamp = nt.nodes.new("ShaderNodeMath")
    wet_clamp.operation = "MAXIMUM"
    wet_clamp.use_clamp = True
    wet_clamp.location = (10, -480)
    nt.links.new(wet_noise.outputs["Value"], wet_clamp.inputs[0])

    wet_base = nt.nodes.new("ShaderNodeMapRange")
    wet_base.location = (-160, -640)
    wet_base.clamp = True
    wet_base.inputs["From Min"].default_value = -0.2
    wet_base.inputs["From Max"].default_value = max(0.25, wet_height * 0.55)
    wet_base.inputs["To Min"].default_value = 0.85
    wet_base.inputs["To Max"].default_value = 0.0
    nt.links.new(sep_pos.outputs["Z"], wet_base.inputs["Value"])
    nt.links.new(wet_base.outputs["Result"], wet_clamp.inputs[1])

    # Darken wet stone color
    mix_wet_col = nt.nodes.new("ShaderNodeMix")
    mix_wet_col.data_type = "RGBA"
    mix_wet_col.location = (380, 180)
    mix_wet_col.inputs[7].default_value = (0.038, 0.044, 0.036, 1.0)
    nt.links.new(wet_clamp.outputs["Value"], mix_wet_col.inputs["Factor"])
    nt.links.new(mix_moss.outputs[2], mix_wet_col.inputs[6])
    nt.links.new(mix_wet_col.outputs[2], bsdf.inputs["Base Color"])

    # Roughness: dry stone ~0.84, wet stone ~0.24
    rough_map = nt.nodes.new("ShaderNodeMapRange")
    rough_map.location = (220, -140)
    rough_map.clamp = True
    rough_map.inputs["From Min"].default_value = 0.0
    rough_map.inputs["From Max"].default_value = 1.0
    rough_map.inputs["To Min"].default_value = max(0.55, base_roughness - 0.08)
    rough_map.inputs["To Max"].default_value = min(0.96, base_roughness + 0.08)
    nt.links.new(noise_med.outputs["Fac"], rough_map.inputs["Value"])

    mix_rough = nt.nodes.new("ShaderNodeMix")
    mix_rough.data_type = "FLOAT"
    mix_rough.location = (410, -140)
    mix_rough.inputs[3].default_value = 0.24
    nt.links.new(wet_clamp.outputs["Value"], mix_rough.inputs["Factor"])
    nt.links.new(rough_map.outputs["Result"], mix_rough.inputs[2])
    nt.links.new(mix_rough.outputs[0], bsdf.inputs["Roughness"])

    # Bump: mortar + stone grain
    bump_add1 = nt.nodes.new("ShaderNodeMath")
    bump_add1.operation = "MULTIPLY_ADD"
    bump_add1.location = (120, -340)
    bump_add1.inputs[1].default_value = mortar_strength
    nt.links.new(brick.outputs["Fac"], bump_add1.inputs[0])
    nt.links.new(noise_fine.outputs["Fac"], bump_add1.inputs[2])

    bump_add2 = nt.nodes.new("ShaderNodeMath")
    bump_add2.operation = "MULTIPLY_ADD"
    bump_add2.location = (280, -340)
    bump_add2.inputs[1].default_value = 0.55
    nt.links.new(noise_med.outputs["Fac"], bump_add2.inputs[0])
    nt.links.new(bump_add1.outputs["Value"], bump_add2.inputs[2])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (440, -340)
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.12
    nt.links.new(bump_add2.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_cliff_material(name: str, is_dark: bool = False) -> bpy.types.Material:
    """Build stratified limestone cliff rock with horizontal strata, fine fissures, and patchy olive turf."""
    mat, nt, bsdf, _ = _new_material(name)

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1350, 0)

    sep_pos = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep_pos.location = (-1120, -150)
    nt.links.new(geo.outputs["Position"], sep_pos.inputs["Vector"])

    # Compressed Z coordinate for horizontal limestone strata layers
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-1100, 180)
    mapping.inputs["Scale"].default_value = (0.08, 0.08, 1.25)
    nt.links.new(geo.outputs["Position"], mapping.inputs["Vector"])

    strata_noise = nt.nodes.new("ShaderNodeTexNoise")
    strata_noise.location = (-860, 180)
    strata_noise.inputs["Scale"].default_value = 1.6
    strata_noise.inputs["Detail"].default_value = 8.0
    strata_noise.inputs["Roughness"].default_value = 0.72
    strata_noise.inputs["Distortion"].default_value = 0.35
    nt.links.new(mapping.outputs["Vector"], strata_noise.inputs["Vector"])

    # Fine rocky grain & directional stratified rock fractures (zero Voronoi cellular rings!)
    rock_detail = nt.nodes.new("ShaderNodeTexNoise")
    rock_detail.location = (-860, -80)
    rock_detail.inputs["Scale"].default_value = 2.4
    rock_detail.inputs["Detail"].default_value = 11.0
    rock_detail.inputs["Roughness"].default_value = 0.82
    rock_detail.inputs["Distortion"].default_value = 0.65
    nt.links.new(geo.outputs["Position"], rock_detail.inputs["Vector"])

    # Secondary crisp horizontal bedding-plane cracks
    bedding_map = nt.nodes.new("ShaderNodeMapping")
    bedding_map.location = (-1080, -300)
    bedding_map.inputs["Scale"].default_value = (0.14, 0.14, 2.6)
    nt.links.new(geo.outputs["Position"], bedding_map.inputs["Vector"])

    bedding_noise = nt.nodes.new("ShaderNodeTexNoise")
    bedding_noise.location = (-860, -300)
    bedding_noise.inputs["Scale"].default_value = 1.8
    bedding_noise.inputs["Detail"].default_value = 8.0
    bedding_noise.inputs["Roughness"].default_value = 0.75
    bedding_noise.inputs["Distortion"].default_value = 0.35
    nt.links.new(bedding_map.outputs["Vector"], bedding_noise.inputs["Vector"])

    crack_ramp = nt.nodes.new("ShaderNodeValToRGB")
    crack_ramp.location = (-480, -300)
    crack_ramp.color_ramp.elements[0].position = 0.32
    crack_ramp.color_ramp.elements[0].color = (0.28, 0.28, 0.28, 1.0)
    crack_ramp.color_ramp.elements[1].position = 0.65
    crack_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(bedding_noise.outputs["Fac"], crack_ramp.inputs["Fac"])

    # Large patchy variation for mossy/dry areas
    patch_noise = nt.nodes.new("ShaderNodeTexNoise")
    patch_noise.location = (-860, 440)
    patch_noise.inputs["Scale"].default_value = 0.14
    patch_noise.inputs["Detail"].default_value = 4.0
    nt.links.new(geo.outputs["Position"], patch_noise.inputs["Vector"])

    ramp_rock = nt.nodes.new("ShaderNodeValToRGB")
    ramp_rock.location = (-580, 180)
    if is_dark:
        ramp_rock.color_ramp.elements[0].color = (0.018, 0.022, 0.022, 1.0)
        ramp_rock.color_ramp.elements[1].color = (0.068, 0.072, 0.064, 1.0)
    else:
        ramp_rock.color_ramp.elements[0].position = 0.28
        ramp_rock.color_ramp.elements[0].color = (0.042, 0.043, 0.036, 1.0)
        e_rmid = ramp_rock.color_ramp.elements.new(0.55)
        e_rmid.color = (0.115, 0.110, 0.092, 1.0)
        ramp_rock.color_ramp.elements[2].position = 0.80
        ramp_rock.color_ramp.elements[2].color = (0.210, 0.195, 0.155, 1.0)
    nt.links.new(strata_noise.outputs["Fac"], ramp_rock.inputs["Fac"])

    # Modulate rock with fine mineral grain and sharp rock cracks
    mix_grain = nt.nodes.new("ShaderNodeMix")
    mix_grain.data_type = "RGBA"
    mix_grain.blend_type = "MULTIPLY"
    mix_grain.location = (-320, 140)
    mix_grain.inputs["Factor"].default_value = 0.72
    nt.links.new(ramp_rock.outputs["Color"], mix_grain.inputs[6])
    nt.links.new(rock_detail.outputs["Color"], mix_grain.inputs[7])

    mix_cracks = nt.nodes.new("ShaderNodeMix")
    mix_cracks.data_type = "RGBA"
    mix_cracks.blend_type = "MULTIPLY"
    mix_cracks.location = (-160, 140)
    mix_cracks.inputs["Factor"].default_value = 0.80
    nt.links.new(mix_grain.outputs[2], mix_cracks.inputs[6])
    nt.links.new(crack_ramp.outputs["Color"], mix_cracks.inputs[7])

    # Upward-facing grass/moss strictly on flatter ledges (Normal.Z > 0.56 AND patchy noise)
    sep_n = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep_n.location = (-620, 520)
    nt.links.new(geo.outputs["Normal"], sep_n.inputs["Vector"])

    ramp_up = nt.nodes.new("ShaderNodeValToRGB")
    ramp_up.location = (-400, 520)
    ramp_up.color_ramp.elements[0].position = 0.54
    ramp_up.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_up.color_ramp.elements[1].position = 0.78
    ramp_up.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(sep_n.outputs["Z"], ramp_up.inputs["Fac"])

    ramp_patch = nt.nodes.new("ShaderNodeValToRGB")
    ramp_patch.location = (-400, 340)
    ramp_patch.color_ramp.elements[0].position = 0.34
    ramp_patch.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_patch.color_ramp.elements[1].position = 0.62
    ramp_patch.color_ramp.elements[1].color = (0.90, 0.90, 0.90, 1.0)
    nt.links.new(patch_noise.outputs["Fac"], ramp_patch.inputs["Fac"])

    z_mask = nt.nodes.new("ShaderNodeMapRange")
    z_mask.location = (-400, 220)
    z_mask.clamp = True
    z_mask.inputs["From Min"].default_value = 2.5
    z_mask.inputs["From Max"].default_value = 5.5
    nt.links.new(sep_pos.outputs["Z"], z_mask.inputs["Value"])

    gm1 = nt.nodes.new("ShaderNodeMath")
    gm1.operation = "MULTIPLY"
    gm1.location = (-170, 440)
    nt.links.new(ramp_up.outputs["Color"], gm1.inputs[0])
    nt.links.new(ramp_patch.outputs["Color"], gm1.inputs[1])

    grass_mask = nt.nodes.new("ShaderNodeMath")
    grass_mask.operation = "MULTIPLY"
    grass_mask.location = (0, 360)
    nt.links.new(gm1.outputs["Value"], grass_mask.inputs[0])
    nt.links.new(z_mask.outputs["Result"], grass_mask.inputs[1])

    mix_grass = nt.nodes.new("ShaderNodeMix")
    mix_grass.data_type = "RGBA"
    mix_grass.location = (160, 180)
    mix_grass.inputs[7].default_value = COLORS["grass_muted"]
    nt.links.new(grass_mask.outputs["Value"], mix_grass.inputs["Factor"])
    nt.links.new(mix_cracks.outputs[2], mix_grass.inputs[6])

    # Wet rock near Z <= 1.8m
    wet_map = nt.nodes.new("ShaderNodeMapRange")
    wet_map.location = (-100, -240)
    wet_map.clamp = True
    wet_map.inputs["From Min"].default_value = -0.3
    wet_map.inputs["From Max"].default_value = 2.0
    wet_map.inputs["To Min"].default_value = 0.85
    wet_map.inputs["To Max"].default_value = 0.0
    nt.links.new(sep_pos.outputs["Z"], wet_map.inputs["Value"])

    mix_wet = nt.nodes.new("ShaderNodeMix")
    mix_wet.data_type = "RGBA"
    mix_wet.location = (340, 160)
    mix_wet.inputs[7].default_value = (0.022, 0.026, 0.023, 1.0)
    nt.links.new(wet_map.outputs["Result"], mix_wet.inputs["Factor"])
    nt.links.new(mix_grass.outputs[2], mix_wet.inputs[6])
    nt.links.new(mix_wet.outputs[2], bsdf.inputs["Base Color"])

    mix_rough = nt.nodes.new("ShaderNodeMix")
    mix_rough.data_type = "FLOAT"
    mix_rough.location = (340, -60)
    mix_rough.inputs[2].default_value = 0.88
    mix_rough.inputs[3].default_value = 0.28
    nt.links.new(wet_map.outputs["Result"], mix_rough.inputs["Factor"])
    nt.links.new(mix_rough.outputs[0], bsdf.inputs["Roughness"])

    bump_mix = nt.nodes.new("ShaderNodeMath")
    bump_mix.operation = "MULTIPLY_ADD"
    bump_mix.location = (80, -260)
    bump_mix.inputs[1].default_value = 0.65
    nt.links.new(strata_noise.outputs["Fac"], bump_mix.inputs[0])
    nt.links.new(rock_detail.outputs["Fac"], bump_mix.inputs[2])

    bump_mix2 = nt.nodes.new("ShaderNodeMath")
    bump_mix2.operation = "MULTIPLY_ADD"
    bump_mix2.location = (210, -260)
    bump_mix2.inputs[1].default_value = 0.85
    nt.links.new(crack_ramp.outputs["Color"], bump_mix2.inputs[0])
    nt.links.new(bump_mix.outputs["Value"], bump_mix2.inputs[2])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (360, -260)
    bump.inputs["Strength"].default_value = 0.92
    bump.inputs["Distance"].default_value = 0.55
    nt.links.new(bump_mix2.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_bark_material(name: str = "MAT_Bark_Ancient") -> bpy.types.Material:
    """Build weathered ancient dark brown-grey bark with longitudinal grooves and damp moss."""
    mat, nt, bsdf, _ = _new_material(name)

    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-1000, 0)

    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-800, 0)
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 4.5)
    nt.links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])

    noise_bark = nt.nodes.new("ShaderNodeTexNoise")
    noise_bark.location = (-580, 120)
    noise_bark.inputs["Scale"].default_value = 5.5
    noise_bark.inputs["Detail"].default_value = 8.0
    noise_bark.inputs["Roughness"].default_value = 0.72
    noise_bark.inputs["Distortion"].default_value = 0.3
    nt.links.new(mapping.outputs["Vector"], noise_bark.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-320, 140)
    ramp.color_ramp.elements[0].color = (0.022, 0.017, 0.012, 1.0)
    ramp.color_ramp.elements[1].color = (0.072, 0.058, 0.042, 1.0)
    nt.links.new(noise_bark.outputs["Fac"], ramp.inputs["Fac"])

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-800, 360)
    sep_n = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep_n.location = (-580, 360)
    nt.links.new(geo.outputs["Normal"], sep_n.inputs["Vector"])

    moss_ramp = nt.nodes.new("ShaderNodeValToRGB")
    moss_ramp.location = (-320, 360)
    moss_ramp.color_ramp.elements[0].position = 0.45
    moss_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    moss_ramp.color_ramp.elements[1].position = 0.85
    moss_ramp.color_ramp.elements[1].color = (0.45, 0.45, 0.45, 1.0)
    nt.links.new(sep_n.outputs["Z"], moss_ramp.inputs["Fac"])

    mix_col = nt.nodes.new("ShaderNodeMix")
    mix_col.data_type = "RGBA"
    mix_col.location = (60, 180)
    mix_col.inputs[7].default_value = COLORS["moss_dark"]
    nt.links.new(moss_ramp.outputs["Color"], mix_col.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], mix_col.inputs[6])
    nt.links.new(mix_col.outputs[2], bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = 0.82

    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (220, -140)
    bump.inputs["Strength"].default_value = 0.42
    bump.inputs["Distance"].default_value = 0.08
    nt.links.new(noise_bark.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_water_material(name: str = "MAT_Water_Dark") -> bpy.types.Material:
    """Build calm, deep green-black reflective flooded basin water."""
    mat, nt, bsdf, out = _new_material(name)

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1000, 0)

    # Broad subtle swells + fine surface capillary ripples
    noise_broad = nt.nodes.new("ShaderNodeTexNoise")
    noise_broad.location = (-700, 180)
    noise_broad.inputs["Scale"].default_value = 0.16
    noise_broad.inputs["Detail"].default_value = 3.0
    noise_broad.inputs["Roughness"].default_value = 0.45
    nt.links.new(geo.outputs["Position"], noise_broad.inputs["Vector"])

    noise_ripple = nt.nodes.new("ShaderNodeTexNoise")
    noise_ripple.location = (-700, -80)
    noise_ripple.inputs["Scale"].default_value = 1.65
    noise_ripple.inputs["Detail"].default_value = 6.0
    noise_ripple.inputs["Roughness"].default_value = 0.5
    nt.links.new(geo.outputs["Position"], noise_ripple.inputs["Vector"])

    mix_wave = nt.nodes.new("ShaderNodeMath")
    mix_wave.operation = "MULTIPLY_ADD"
    mix_wave.location = (-400, 60)
    mix_wave.inputs[1].default_value = 0.35
    nt.links.new(noise_ripple.outputs["Fac"], mix_wave.inputs[0])
    nt.links.new(noise_broad.outputs["Fac"], mix_wave.inputs[2])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (180, -120)
    bump.inputs["Strength"].default_value = 0.055
    bump.inputs["Distance"].default_value = 0.04
    nt.links.new(mix_wave.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    # Subtle roughness variation for realistic calm dark water (not mirror chrome!)
    rough_map = nt.nodes.new("ShaderNodeMapRange")
    rough_map.location = (160, 80)
    rough_map.clamp = True
    rough_map.inputs["From Min"].default_value = 0.25
    rough_map.inputs["From Max"].default_value = 0.75
    rough_map.inputs["To Min"].default_value = 0.055
    rough_map.inputs["To Max"].default_value = 0.145
    nt.links.new(noise_broad.outputs["Fac"], rough_map.inputs["Value"])
    nt.links.new(rough_map.outputs["Result"], bsdf.inputs["Roughness"])

    # Deep green-black flooded water: dark murky absorption + restrained grazing sky glare
    bsdf.inputs["Base Color"].default_value = (0.004, 0.013, 0.011, 1.0)
    bsdf.inputs["IOR"].default_value = 1.333
    bsdf.inputs["Specular IOR Level"].default_value = 0.34
    bsdf.inputs["Transmission Weight"].default_value = 0.14

    # Strong murky emerald-black volume absorption for shallow courtyard edges
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
    vol.location = (600, -240)
    vol.inputs["Color"].default_value = (0.010, 0.042, 0.034, 1.0)
    vol.inputs["Density"].default_value = 5.2
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])

    return mat


def build_statue_material(name: str = "MAT_Statue_Weathered") -> bpy.types.Material:
    """Build aged grey-green limestone for the monumental courtyard statue."""
    return build_limestone_material(
        name=name,
        color_a=COLORS["statue_stone"],
        color_b=(0.135, 0.142, 0.118, 1.0),
        shadow_col=(0.052, 0.062, 0.048, 1.0),
        moss_amount=0.45,
        wet_height=2.2,
        base_roughness=0.80,
        bump_strength=0.22,
        mortar_strength=0.0,  # Carved monolith, no brick mortar lines!
    )


def build_simple_ground_material(
    name: str,
    base_col: Tuple[float, float, float, float],
    alt_col: Tuple[float, float, float, float],
    roughness: float = 0.90,
    bump_strength: float = 0.25,
) -> bpy.types.Material:
    """Build organic procedural ground/mud/grass material."""
    mat, nt, bsdf, _ = _new_material(name)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-700, 0)

    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-450, 0)
    noise.inputs["Scale"].default_value = 1.8
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])

    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.location = (-160, 80)
    mix.inputs[6].default_value = base_col
    mix.inputs[7].default_value = alt_col
    nt.links.new(noise.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness

    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (140, -120)
    bump.inputs["Strength"].default_value = bump_strength
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def build_volume_mist_material(
    name: str,
    base_density: float = 0.011,
    color: Tuple[float, float, float, float] = (0.72, 0.76, 0.77, 1.0),
    noise_scale: float = 0.045,
    anisotropy: float = 0.45,
    is_uniform: bool = False,
) -> bpy.types.Material:
    """Build bounded volumetric mist / atmospheric perspective shader."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (650, 0)
    pv = nt.nodes.new("ShaderNodeVolumePrincipled")
    pv.location = (350, 0)
    pv.inputs["Color"].default_value = color
    pv.inputs["Anisotropy"].default_value = anisotropy
    nt.links.new(pv.outputs["Volume"], out.inputs["Volume"])

    if is_uniform:
        pv.inputs["Density"].default_value = base_density
        return mat

    # Height falloff inside local bounding box (Generated Z in 0..1) + 3D drifting wisps
    tex = nt.nodes.new("ShaderNodeTexCoord")
    tex.location = (-900, 0)

    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-650, 220)
    nt.links.new(tex.outputs["Generated"], sep.inputs["Vector"])

    # Soft fade near ALL faces of volume box (X, Y, and Z in Generated 0..1) so no hard bounding walls show!
    ramp_z = nt.nodes.new("ShaderNodeValToRGB")
    ramp_z.location = (-400, 240)
    ramp_z.color_ramp.elements[0].position = 0.02
    ramp_z.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    e_mid = ramp_z.color_ramp.elements.new(0.28)
    e_mid.color = (1.0, 1.0, 1.0, 1.0)
    ramp_z.color_ramp.elements[2].position = 0.96
    ramp_z.color_ramp.elements[2].color = (0.0, 0.0, 0.0, 1.0)
    nt.links.new(sep.outputs["Z"], ramp_z.inputs["Fac"])

    ramp_x = nt.nodes.new("ShaderNodeValToRGB")
    ramp_x.location = (-400, 440)
    ramp_x.color_ramp.elements[0].position = 0.03
    ramp_x.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    e_xm = ramp_x.color_ramp.elements.new(0.22)
    e_xm.color = (1.0, 1.0, 1.0, 1.0)
    e_xm2 = ramp_x.color_ramp.elements.new(0.78)
    e_xm2.color = (1.0, 1.0, 1.0, 1.0)
    ramp_x.color_ramp.elements[3].position = 0.97
    ramp_x.color_ramp.elements[3].color = (0.0, 0.0, 0.0, 1.0)
    nt.links.new(sep.outputs["X"], ramp_x.inputs["Fac"])

    ramp_y = nt.nodes.new("ShaderNodeValToRGB")
    ramp_y.location = (-400, 620)
    ramp_y.color_ramp.elements[0].position = 0.03
    ramp_y.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    e_ym = ramp_y.color_ramp.elements.new(0.22)
    e_ym.color = (1.0, 1.0, 1.0, 1.0)
    e_ym2 = ramp_y.color_ramp.elements.new(0.78)
    e_ym2.color = (1.0, 1.0, 1.0, 1.0)
    ramp_y.color_ramp.elements[3].position = 0.97
    ramp_y.color_ramp.elements[3].color = (0.0, 0.0, 0.0, 1.0)
    nt.links.new(sep.outputs["Y"], ramp_y.inputs["Fac"])

    mult_xy = nt.nodes.new("ShaderNodeMath")
    mult_xy.operation = "MULTIPLY"
    mult_xy.location = (-180, 500)
    nt.links.new(ramp_x.outputs["Color"], mult_xy.inputs[0])
    nt.links.new(ramp_y.outputs["Color"], mult_xy.inputs[1])

    mult_xyz = nt.nodes.new("ShaderNodeMath")
    mult_xyz.operation = "MULTIPLY"
    mult_xyz.location = (-180, 320)
    nt.links.new(ramp_z.outputs["Color"], mult_xyz.inputs[0])
    nt.links.new(mult_xy.outputs["Value"], mult_xyz.inputs[1])

    noise_wisp = nt.nodes.new("ShaderNodeTexNoise")
    noise_wisp.location = (-650, -80)
    noise_wisp.inputs["Scale"].default_value = noise_scale
    noise_wisp.inputs["Detail"].default_value = 3.5
    noise_wisp.inputs["Roughness"].default_value = 0.55
    nt.links.new(tex.outputs["Object"], noise_wisp.inputs["Vector"])

    ramp_n = nt.nodes.new("ShaderNodeValToRGB")
    ramp_n.location = (-400, -80)
    ramp_n.color_ramp.elements[0].position = 0.36
    ramp_n.color_ramp.elements[0].color = (0.10, 0.10, 0.10, 1.0)
    ramp_n.color_ramp.elements[1].position = 0.74
    ramp_n.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(noise_wisp.outputs["Fac"], ramp_n.inputs["Fac"])

    mult1 = nt.nodes.new("ShaderNodeMath")
    mult1.operation = "MULTIPLY"
    mult1.location = (-40, 80)
    nt.links.new(mult_xyz.outputs["Value"], mult1.inputs[0])
    nt.links.new(ramp_n.outputs["Color"], mult1.inputs[1])

    mult2 = nt.nodes.new("ShaderNodeMath")
    mult2.operation = "MULTIPLY"
    mult2.location = (100, 80)
    mult2.inputs[1].default_value = base_density
    nt.links.new(mult1.outputs["Value"], mult2.inputs[0])
    nt.links.new(mult2.outputs["Value"], pv.inputs["Density"])

    return mat


def create_all_materials() -> Dict[str, bpy.types.Material]:
    """Create the entire named PBR material library and return a lookup dictionary."""
    mats: Dict[str, bpy.types.Material] = {}

    mats["MAT_Limestone_Base"] = build_limestone_material(
        "MAT_Limestone_Base",
        color_a=COLORS["limestone_mid"],
        color_b=COLORS["limestone_sunlit"],
        shadow_col=COLORS["limestone_shadow"],
        moss_amount=0.22,
        wet_height=2.4,
        base_roughness=0.84,
        bump_strength=0.28,
        mortar_strength=0.35,
    )
    mats["MAT_Limestone_Light"] = build_limestone_material(
        "MAT_Limestone_Light",
        color_a=COLORS["limestone_sunlit"],
        color_b=(0.45, 0.41, 0.31, 1.0),
        shadow_col=COLORS["limestone_mid"],
        moss_amount=0.14,
        wet_height=1.6,
        base_roughness=0.80,
        bump_strength=0.24,
        mortar_strength=0.28,
    )
    mats["MAT_Limestone_Wet"] = build_limestone_material(
        "MAT_Limestone_Wet",
        color_a=(0.11, 0.115, 0.095, 1.0),
        color_b=(0.075, 0.082, 0.070, 1.0),
        shadow_col=(0.04, 0.045, 0.04, 1.0),
        moss_amount=0.38,
        wet_height=4.0,
        base_roughness=0.45,
        bump_strength=0.32,
        mortar_strength=0.35,
    )
    mats["MAT_Limestone_Eroded"] = build_limestone_material(
        "MAT_Limestone_Eroded",
        color_a=COLORS["limestone_eroded"],
        color_b=COLORS["limestone_shadow"],
        shadow_col=(0.07, 0.075, 0.068, 1.0),
        moss_amount=0.28,
        wet_height=2.2,
        base_roughness=0.90,
        bump_strength=0.38,
        mortar_strength=0.22,
    )
    mats["MAT_Limestone_Moss"] = build_limestone_material(
        "MAT_Limestone_Moss",
        color_a=COLORS["limestone_mid"],
        color_b=COLORS["moss_olive"],
        shadow_col=COLORS["moss_dark"],
        moss_amount=0.72,
        wet_height=2.8,
        base_roughness=0.85,
        bump_strength=0.30,
        mortar_strength=0.32,
    )
    mats["MAT_Rock_Cliff"] = build_cliff_material("MAT_Rock_Cliff", is_dark=False)
    mats["MAT_Rock_Dark"] = build_cliff_material("MAT_Rock_Dark", is_dark=True)
    mats["MAT_Bark_Ancient"] = build_bark_material("MAT_Bark_Ancient")
    mats["MAT_Water_Dark"] = build_water_material("MAT_Water_Dark")
    mats["MAT_Statue_Weathered"] = build_statue_material("MAT_Statue_Weathered")
    mats["MAT_Submerged_Stone"] = build_limestone_material(
        "MAT_Submerged_Stone",
        color_a=(0.055, 0.065, 0.052, 1.0),
        color_b=(0.038, 0.048, 0.040, 1.0),
        shadow_col=(0.025, 0.030, 0.026, 1.0),
        moss_amount=0.55,
        wet_height=5.0,
        base_roughness=0.34,
        bump_strength=0.34,
        mortar_strength=0.28,
    )
    mats["MAT_Ground_Grass"] = build_simple_ground_material(
        "MAT_Ground_Grass", COLORS["grass_muted"], COLORS["moss_dark"], 0.92, 0.25
    )
    mats["MAT_Ground_Mud"] = build_simple_ground_material(
        "MAT_Ground_Mud", COLORS["mud_dark"], (0.025, 0.026, 0.022, 1.0), 0.55, 0.20
    )
    mats["MAT_Dark_Silhouette"] = build_simple_ground_material(
        "MAT_Dark_Silhouette", (0.015, 0.016, 0.018, 1.0), (0.028, 0.030, 0.032, 1.0), 0.85, 0.1
    )
    mats["MAT_Fog_Volume"] = build_volume_mist_material(
        "MAT_Fog_Volume",
        base_density=0.011,
        color=(0.74, 0.78, 0.78, 1.0),
        noise_scale=0.045,
        anisotropy=0.45,
        is_uniform=False,
    )
    mats["MAT_Distant_Haze_Volume"] = build_volume_mist_material(
        "MAT_Distant_Haze_Volume",
        base_density=0.0028,
        color=(0.82, 0.84, 0.80, 1.0),
        anisotropy=0.55,
        is_uniform=True,
    )

    return mats
