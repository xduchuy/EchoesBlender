"""Procedural physically based material library for THE FORGOTTEN KNIGHT.
Implements all 14 Section 15 materials tuned for gritty dark-fantasy steel,
deep desaturated pine-green wool, cracked dark leather, aged muted bronze/brass,
and limestone with flat top-only reflective rainwater puddles.
"""

import math
import os
import bpy
import config


def _set_input(node, names, value):
    """Set the first matching input socket on a Blender node safely."""
    if isinstance(names, str):
        names = [names]
    for n in names:
        sock = node.inputs.get(n)
        if sock is not None:
            sock.default_value = value
            return sock
    return None


def _new_material(name: str):
    """Create or replace a material with clean node tree and return (mat, nodes, links, bsdf, out)."""
    old = bpy.data.materials.get(name)
    if old is not None:
        bpy.data.materials.remove(old, do_unlink=True)
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (550, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, nodes, links, bsdf, out


def _add_tex_coord(nodes, x=-1100, y=0):
    tc = nodes.new("ShaderNodeTexCoord")
    tc.location = (x, y)
    return tc


def _generate_tabard_crest_image() -> bpy.types.Image:
    """Procedurally paint a worn faded medieval heraldic crest RGBA image via Blender API."""
    w, h = 256, 256
    img_name = "tex_tabard_crest.png"
    img_path = os.path.join(config.TEXTURES_DIR, img_name)
    old = bpy.data.images.get(img_name)
    if old is not None:
        bpy.data.images.remove(old, do_unlink=True)

    img = bpy.data.images.new(img_name, width=w, height=h, alpha=True)
    pixels = [0.0] * (w * h * 4)
    rng = config.seeded_rng(901)

    for py in range(h):
        ny = py / (h - 1)
        for px in range(w):
            nx = px / (w - 1)
            idx = (py * w + px) * 4

            sx = (nx - 0.50) / 0.28
            sy = (ny - 0.52) / 0.32
            in_shield = False
            shield_border = False
            if -1.0 <= sx <= 1.0 and -1.0 <= sy <= 0.90:
                bottom_limit = -0.92 + 0.50 * (sx * sx)
                if sy >= bottom_limit:
                    in_shield = True
                    dist_edge = min(1.0 - abs(sx), 0.90 - sy, (sy - bottom_limit) * 1.4)
                    if 0.0 < dist_edge < 0.075:
                        shield_border = True

            fig = False
            if in_shield and not shield_border:
                lx = nx - 0.50
                ly = ny - 0.50
                if abs(lx * 1.15 - ly * 0.72) < 0.048 and -0.13 < ly < 0.13:
                    fig = True
                if (lx + 0.04) ** 2 + (ly - 0.15) ** 2 < 0.052 ** 2:
                    fig = True
                if abs((ly - 0.11) - (-0.45 * lx)) < 0.022 and -0.16 < lx < 0.04:
                    fig = True
                if abs(lx - (0.08 + 0.055 * math.sin((ly + 0.06) * 16.0))) < 0.020 and -0.09 < ly < 0.15:
                    fig = True
                if abs(lx - 0.045) < 0.022 and -0.20 < ly < -0.02:
                    fig = True
                if abs(lx + 0.065 + 0.25 * (ly + 0.10)) < 0.022 and -0.19 < ly < -0.04:
                    fig = True

            wear = rng.random()
            scratches = math.sin(nx * 52.0 + ny * 24.0) * math.cos(ny * 37.0 - nx * 17.0)
            fade = max(0.0, min(1.0, 0.72 + 0.35 * scratches - 0.50 * max(0.0, wear - 0.48)))
            bottom_mud = max(0.0, min(1.0, (ny - 0.10) / 0.25))

            alpha = 0.0
            if shield_border or fig:
                alpha = fade * bottom_mud * 0.78
            elif in_shield:
                alpha = fade * bottom_mud * 0.14

            # Worn faded sage-parchment ink clearly readable on weathered dark-green cloth
            pixels[idx + 0] = 0.38 + 0.04 * (wear - 0.5)
            pixels[idx + 1] = 0.42 + 0.04 * (wear - 0.5)
            pixels[idx + 2] = 0.30 + 0.03 * (wear - 0.5)
            pixels[idx + 3] = max(0.0, min(1.0, alpha))

    img.pixels.foreach_set(pixels)
    img.filepath_raw = img_path
    img.file_format = "PNG"
    try:
        img.save()
        img.pack()
    except Exception:
        pass
    return img


def _build_steel_material(name: str, base_dark, base_mid, base_edge, rust_tint,
                          base_rough: float = 0.48, rust_amount: float = 0.38,
                          scratch_scale: float = 30.0):
    """Build gritty ancient dark steel with mottling, pitted bump, AO seam rust, and worn edges."""
    mat, nodes, links, bsdf, _ = _new_material(name)
    tc = _add_tex_coord(nodes, -1400, 0)

    n_macro = nodes.new("ShaderNodeTexNoise")
    n_macro.location = (-1120, 220)
    n_macro.inputs["Scale"].default_value = 11.5
    n_macro.inputs["Detail"].default_value = 9.0
    n_macro.inputs["Roughness"].default_value = 0.72
    links.new(tc.outputs["Object"], n_macro.inputs["Vector"])

    mp = nodes.new("ShaderNodeMapping")
    mp.location = (-1180, -80)
    mp.inputs["Scale"].default_value = (1.0, 6.0, 1.5)
    mp.inputs["Rotation"].default_value = (0.35, 0.2, 0.45)
    links.new(tc.outputs["Object"], mp.inputs["Vector"])

    n_scratch = nodes.new("ShaderNodeTexNoise")
    n_scratch.location = (-980, -80)
    n_scratch.inputs["Scale"].default_value = scratch_scale
    n_scratch.inputs["Detail"].default_value = 11.0
    n_scratch.inputs["Roughness"].default_value = 0.75
    links.new(mp.outputs["Vector"], n_scratch.inputs["Vector"])

    vor = nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-980, -320)
    vor.inputs["Scale"].default_value = 52.0
    vor.feature = "F1"
    links.new(tc.outputs["Object"], vor.inputs["Vector"])

    geom = nodes.new("ShaderNodeNewGeometry")
    geom.location = (-1100, 480)
    ramp_edge = nodes.new("ShaderNodeValToRGB")
    ramp_edge.location = (-820, 480)
    ramp_edge.color_ramp.elements[0].position = 0.485
    ramp_edge.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_edge.color_ramp.elements[1].position = 0.56
    ramp_edge.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(geom.outputs["Pointiness"], ramp_edge.inputs["Fac"])

    ao = nodes.new("ShaderNodeAmbientOcclusion")
    ao.location = (-1100, 680)
    ao.samples = 8
    ao.inputs["Distance"].default_value = 0.16
    ramp_ao = nodes.new("ShaderNodeValToRGB")
    ramp_ao.location = (-820, 680)
    ramp_ao.color_ramp.elements[0].position = 0.24
    ramp_ao.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    ramp_ao.color_ramp.elements[1].position = 0.80
    ramp_ao.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    links.new(ao.outputs["AO"], ramp_ao.inputs["Fac"])

    mix_steel = nodes.new("ShaderNodeMix")
    mix_steel.data_type = "RGBA"
    mix_steel.location = (-500, 200)
    mix_steel.inputs[6].default_value = (*base_dark, 1.0)
    mix_steel.inputs[7].default_value = (*base_mid, 1.0)
    links.new(n_macro.outputs["Fac"], mix_steel.inputs[0])

    mix_edge = nodes.new("ShaderNodeMix")
    mix_edge.data_type = "RGBA"
    mix_edge.location = (-260, 260)
    mix_edge.inputs[7].default_value = (*base_edge, 1.0)
    links.new(ramp_edge.outputs["Color"], mix_edge.inputs[0])
    links.new(mix_steel.outputs[2], mix_edge.inputs[6])

    m_rust_mul = nodes.new("ShaderNodeMath")
    m_rust_mul.operation = "MULTIPLY"
    m_rust_mul.location = (-520, 560)
    links.new(ramp_ao.outputs["Color"], m_rust_mul.inputs[0])
    links.new(n_macro.outputs["Fac"], m_rust_mul.inputs[1])

    m_rust_scale = nodes.new("ShaderNodeMath")
    m_rust_scale.operation = "MULTIPLY"
    m_rust_scale.use_clamp = True
    m_rust_scale.location = (-320, 560)
    m_rust_scale.inputs[1].default_value = min(1.0, rust_amount * 2.5)
    links.new(m_rust_mul.outputs["Value"], m_rust_scale.inputs[0])

    mix_rust = nodes.new("ShaderNodeMix")
    mix_rust.data_type = "RGBA"
    mix_rust.location = (20, 300)
    mix_rust.inputs[7].default_value = (*rust_tint, 1.0)
    links.new(m_rust_scale.outputs["Value"], mix_rust.inputs[0])
    links.new(mix_edge.outputs[2], mix_rust.inputs[6])
    links.new(mix_rust.outputs[2], bsdf.inputs["Base Color"])

    m_met = nodes.new("ShaderNodeMath")
    m_met.operation = "SUBTRACT"
    m_met.use_clamp = True
    m_met.location = (200, 120)
    m_met.inputs[0].default_value = 0.90
    m_met_mul = nodes.new("ShaderNodeMath")
    m_met_mul.operation = "MULTIPLY"
    m_met_mul.location = (-20, 120)
    m_met_mul.inputs[1].default_value = 0.72
    links.new(m_rust_scale.outputs["Value"], m_met_mul.inputs[0])
    links.new(m_met_mul.outputs["Value"], m_met.inputs[1])
    links.new(m_met.outputs["Value"], bsdf.inputs["Metallic"])

    ramp_r = nodes.new("ShaderNodeValToRGB")
    ramp_r.location = (-400, -40)
    ramp_r.color_ramp.elements[0].position = 0.18
    r_lo = max(0.24, base_rough - 0.16)
    r_hi = min(0.94, base_rough + 0.28)
    ramp_r.color_ramp.elements[0].color = (r_lo, r_lo, r_lo, 1.0)
    ramp_r.color_ramp.elements[1].position = 0.84
    ramp_r.color_ramp.elements[1].color = (r_hi, r_hi, r_hi, 1.0)
    links.new(n_scratch.outputs["Fac"], ramp_r.inputs["Fac"])

    m_r_rust = nodes.new("ShaderNodeMath")
    m_r_rust.operation = "MAXIMUM"
    m_r_rust.use_clamp = True
    m_r_rust.location = (180, -40)
    links.new(ramp_r.outputs["Color"], m_r_rust.inputs[0])
    links.new(m_rust_scale.outputs["Value"], m_r_rust.inputs[1])
    links.new(m_r_rust.outputs["Value"], bsdf.inputs["Roughness"])

    m_bump = nodes.new("ShaderNodeMath")
    m_bump.operation = "ADD"
    m_bump.location = (-280, -240)
    links.new(n_scratch.outputs["Fac"], m_bump.inputs[0])
    m_pit = nodes.new("ShaderNodeMath")
    m_pit.operation = "MULTIPLY"
    m_pit.location = (-540, -320)
    m_pit.inputs[1].default_value = 0.45
    links.new(vor.outputs["Distance"], m_pit.inputs[0])
    links.new(m_pit.outputs["Value"], m_bump.inputs[1])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (220, -220)
    bump.inputs["Strength"].default_value = 0.34
    bump.inputs["Distance"].default_value = 0.0035
    links.new(m_bump.outputs["Value"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    _set_input(bsdf, ["Specular IOR Level", "Specular"], 0.48)
    return mat


def _build_fabric_material(name: str, dark_rgb, light_rgb, grime_rgb,
                           weave_scale: float = 175.0, with_crest_img=None):
    """Build deep pine-forest-green medieval wool cloth with heavy fold AO darkening,
    woven twill micro-bump, and dirty mud splatter near lower hems."""
    mat, nodes, links, bsdf, _ = _new_material(name)
    tc = _add_tex_coord(nodes, -1400, 0)

    w_x = nodes.new("ShaderNodeTexWave")
    w_x.location = (-1000, -180)
    w_x.wave_type = "BANDS"
    w_x.bands_direction = "X"
    w_x.inputs["Scale"].default_value = weave_scale
    w_x.inputs["Distortion"].default_value = 1.6
    links.new(tc.outputs["UV"], w_x.inputs["Vector"])

    w_y = nodes.new("ShaderNodeTexWave")
    w_y.location = (-1000, -400)
    w_y.wave_type = "BANDS"
    w_y.bands_direction = "Y"
    w_y.inputs["Scale"].default_value = weave_scale
    w_y.inputs["Distortion"].default_value = 1.6
    links.new(tc.outputs["UV"], w_y.inputs["Vector"])

    m_weave = nodes.new("ShaderNodeMath")
    m_weave.operation = "MULTIPLY"
    m_weave.location = (-740, -290)
    links.new(w_x.outputs["Fac"], m_weave.inputs[0])
    links.new(w_y.outputs["Fac"], m_weave.inputs[1])

    n_fade = nodes.new("ShaderNodeTexNoise")
    n_fade.location = (-1000, 220)
    n_fade.inputs["Scale"].default_value = 7.5
    n_fade.inputs["Detail"].default_value = 8.0
    n_fade.inputs["Roughness"].default_value = 0.68
    links.new(tc.outputs["Object"], n_fade.inputs["Vector"])

    ao = nodes.new("ShaderNodeAmbientOcclusion")
    ao.location = (-1000, 440)
    ao.samples = 8
    ao.inputs["Distance"].default_value = 0.22

    mix_col = nodes.new("ShaderNodeMix")
    mix_col.data_type = "RGBA"
    mix_col.location = (-560, 200)
    mix_col.inputs[6].default_value = (*dark_rgb, 1.0)
    mix_col.inputs[7].default_value = (*light_rgb, 1.0)
    links.new(n_fade.outputs["Fac"], mix_col.inputs[0])

    ramp_ao = nodes.new("ShaderNodeValToRGB")
    ramp_ao.location = (-740, 440)
    ramp_ao.color_ramp.elements[0].position = 0.18
    ramp_ao.color_ramp.elements[0].color = (0.28, 0.28, 0.28, 1.0)
    ramp_ao.color_ramp.elements[1].position = 0.88
    ramp_ao.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(ao.outputs["AO"], ramp_ao.inputs["Fac"])

    mix_fold = nodes.new("ShaderNodeMix")
    mix_fold.data_type = "RGBA"
    mix_fold.blend_type = "MULTIPLY"
    mix_fold.location = (-320, 260)
    mix_fold.inputs[0].default_value = 0.90
    links.new(mix_col.outputs[2], mix_fold.inputs[6])
    links.new(ramp_ao.outputs["Color"], mix_fold.inputs[7])

    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1020, 620)
    links.new(tc.outputs["Object"], sep.inputs["Vector"])

    ramp_z = nodes.new("ShaderNodeValToRGB")
    ramp_z.location = (-740, 620)
    ramp_z.color_ramp.elements[0].position = 0.22
    ramp_z.color_ramp.elements[0].color = (0.65, 0.65, 0.65, 1.0)
    ramp_z.color_ramp.elements[1].position = 0.56
    ramp_z.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    links.new(sep.outputs["Z"], ramp_z.inputs["Fac"])

    mix_dirt = nodes.new("ShaderNodeMix")
    mix_dirt.data_type = "RGBA"
    mix_dirt.location = (-40, 300)
    mix_dirt.inputs[7].default_value = (*grime_rgb, 1.0)
    links.new(ramp_z.outputs["Color"], mix_dirt.inputs[0])
    links.new(mix_fold.outputs[2], mix_dirt.inputs[6])

    if with_crest_img is not None:
        tex_img = nodes.new("ShaderNodeTexImage")
        tex_img.location = (-320, -40)
        tex_img.image = with_crest_img
        tex_img.extension = "CLIP"
        links.new(tc.outputs["UV"], tex_img.inputs["Vector"])

        mix_crest = nodes.new("ShaderNodeMix")
        mix_crest.data_type = "RGBA"
        mix_crest.location = (220, 280)
        links.new(tex_img.outputs["Alpha"], mix_crest.inputs[0])
        links.new(mix_dirt.outputs[2], mix_crest.inputs[6])
        links.new(tex_img.outputs["Color"], mix_crest.inputs[7])
        links.new(mix_crest.outputs[2], bsdf.inputs["Base Color"])
    else:
        links.new(mix_dirt.outputs[2], bsdf.inputs["Base Color"])

    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.94
    _set_input(bsdf, ["Specular IOR Level", "Specular"], 0.12)
    _set_input(bsdf, ["Sheen Weight", "Sheen"], 0.22)
    _set_input(bsdf, ["Sheen Roughness"], 0.80)

    bump = nodes.new("ShaderNodeBump")
    bump.location = (220, -240)
    bump.inputs["Strength"].default_value = 0.32
    bump.inputs["Distance"].default_value = 0.0030
    links.new(m_weave.outputs["Value"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _build_leather_material(name: str, dark_rgb, worn_rgb, roughness_base: float = 0.58):
    """Build cracked weathered medieval leather with worn edge highlights."""
    mat, nodes, links, bsdf, _ = _new_material(name)
    tc = _add_tex_coord(nodes, -1200, 0)

    vor_crack = nodes.new("ShaderNodeTexVoronoi")
    vor_crack.location = (-940, -180)
    vor_crack.feature = "DISTANCE_TO_EDGE"
    vor_crack.inputs["Scale"].default_value = 38.0
    links.new(tc.outputs["Object"], vor_crack.inputs["Vector"])

    n_grain = nodes.new("ShaderNodeTexNoise")
    n_grain.location = (-940, 80)
    n_grain.inputs["Scale"].default_value = 48.0
    n_grain.inputs["Detail"].default_value = 8.0
    links.new(tc.outputs["Object"], n_grain.inputs["Vector"])

    geom = nodes.new("ShaderNodeNewGeometry")
    geom.location = (-940, 320)
    ramp_edge = nodes.new("ShaderNodeValToRGB")
    ramp_edge.location = (-680, 320)
    ramp_edge.color_ramp.elements[0].position = 0.49
    ramp_edge.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_edge.color_ramp.elements[1].position = 0.57
    ramp_edge.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(geom.outputs["Pointiness"], ramp_edge.inputs["Fac"])

    mix_col = nodes.new("ShaderNodeMix")
    mix_col.data_type = "RGBA"
    mix_col.location = (-400, 140)
    mix_col.inputs[6].default_value = (*dark_rgb, 1.0)
    mix_col.inputs[7].default_value = (*worn_rgb, 1.0)
    links.new(n_grain.outputs["Fac"], mix_col.inputs[0])

    mix_edge = nodes.new("ShaderNodeMix")
    mix_edge.data_type = "RGBA"
    mix_edge.location = (-120, 220)
    mix_edge.inputs[7].default_value = (min(1.0, worn_rgb[0] * 1.4), min(1.0, worn_rgb[1] * 1.3), min(1.0, worn_rgb[2] * 1.25), 1.0)
    links.new(ramp_edge.outputs["Color"], mix_edge.inputs[0])
    links.new(mix_col.outputs[2], mix_edge.inputs[6])
    links.new(mix_edge.outputs[2], bsdf.inputs["Base Color"])

    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = roughness_base
    _set_input(bsdf, ["Specular IOR Level", "Specular"], 0.30)

    bump = nodes.new("ShaderNodeBump")
    bump.location = (180, -180)
    bump.inputs["Strength"].default_value = 0.24
    bump.inputs["Distance"].default_value = 0.0025
    links.new(vor_crack.outputs["Distance"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _build_stone_pedestal_material():
    """Build cracked limestone pedestal where shallow rainwater puddles ONLY collect
    on flat upward-facing floor planes (Normal.Z > 0.88), never on vertical side rims."""
    mat, nodes, links, bsdf, _ = _new_material("MAT_Stone_Weathered")
    tc = _add_tex_coord(nodes, -1400, 0)
    geom = nodes.new("ShaderNodeNewGeometry")
    geom.location = (-1400, -340)

    sep_n = nodes.new("ShaderNodeSeparateXYZ")
    sep_n.location = (-1160, -340)
    links.new(geom.outputs["Normal"], sep_n.inputs["Vector"])

    # Normal Z mask: 1.0 only on horizontal upward stone faces
    ramp_up = nodes.new("ShaderNodeValToRGB")
    ramp_up.location = (-940, -340)
    ramp_up.color_ramp.elements[0].position = 0.88
    ramp_up.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_up.color_ramp.elements[1].position = 0.96
    ramp_up.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(sep_n.outputs["Z"], ramp_up.inputs["Fac"])

    n_stone = nodes.new("ShaderNodeTexNoise")
    n_stone.location = (-1040, 200)
    n_stone.inputs["Scale"].default_value = 18.0
    n_stone.inputs["Detail"].default_value = 12.0
    n_stone.inputs["Roughness"].default_value = 0.76
    links.new(tc.outputs["Object"], n_stone.inputs["Vector"])

    vor_slab = nodes.new("ShaderNodeTexVoronoi")
    vor_slab.location = (-1040, -560)
    vor_slab.feature = "DISTANCE_TO_EDGE"
    vor_slab.inputs["Scale"].default_value = 3.2
    links.new(tc.outputs["Object"], vor_slab.inputs["Vector"])

    ramp_crack = nodes.new("ShaderNodeValToRGB")
    ramp_crack.location = (-780, -560)
    ramp_crack.color_ramp.elements[0].position = 0.00
    ramp_crack.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_crack.color_ramp.elements[1].position = 0.055
    ramp_crack.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(vor_slab.outputs["Distance"], ramp_crack.inputs["Fac"])

    n_puddle = nodes.new("ShaderNodeTexNoise")
    n_puddle.location = (-1040, -100)
    n_puddle.inputs["Scale"].default_value = 2.8
    n_puddle.inputs["Detail"].default_value = 4.0
    n_puddle.inputs["Roughness"].default_value = 0.50
    links.new(tc.outputs["Object"], n_puddle.inputs["Vector"])

    ramp_puddle_raw = nodes.new("ShaderNodeValToRGB")
    ramp_puddle_raw.location = (-780, -100)
    ramp_puddle_raw.color_ramp.elements[0].position = 0.45
    ramp_puddle_raw.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    ramp_puddle_raw.color_ramp.elements[1].position = 0.55
    ramp_puddle_raw.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    links.new(n_puddle.outputs["Fac"], ramp_puddle_raw.inputs["Fac"])

    # Combine puddle noise strictly with upward flat floor mask
    m_puddle_flat = nodes.new("ShaderNodeMath")
    m_puddle_flat.operation = "MULTIPLY"
    m_puddle_flat.location = (-540, -160)
    links.new(ramp_puddle_raw.outputs["Color"], m_puddle_flat.inputs[0])
    links.new(ramp_up.outputs["Color"], m_puddle_flat.inputs[1])

    ao = nodes.new("ShaderNodeAmbientOcclusion")
    ao.location = (-1040, 440)
    ao.samples = 8
    ao.inputs["Distance"].default_value = 0.18

    mix_stone = nodes.new("ShaderNodeMix")
    mix_stone.data_type = "RGBA"
    mix_stone.location = (-680, 220)
    mix_stone.inputs[6].default_value = (0.072, 0.082, 0.075, 1.0)
    mix_stone.inputs[7].default_value = (0.148, 0.160, 0.145, 1.0)
    links.new(n_stone.outputs["Fac"], mix_stone.inputs[0])

    # Subtle weathered stone mortar crack lines across pedestal floor/rim
    mix_crack_col = nodes.new("ShaderNodeMix")
    mix_crack_col.data_type = "RGBA"
    mix_crack_col.location = (-500, 220)
    mix_crack_col.inputs[6].default_value = (0.032, 0.038, 0.032, 1.0)
    links.new(ramp_crack.outputs["Color"], mix_crack_col.inputs[0])
    links.new(mix_stone.outputs[2], mix_crack_col.inputs[7])

    # Damp puddle stone underneath rainwater reflects cool sky without flat pitch-black ink blot
    mix_wet_col = nodes.new("ShaderNodeMix")
    mix_wet_col.data_type = "RGBA"
    mix_wet_col.location = (-320, 200)
    mix_wet_col.inputs[7].default_value = (0.046, 0.054, 0.052, 1.0)
    links.new(m_puddle_flat.outputs["Value"], mix_wet_col.inputs[0])
    links.new(mix_crack_col.outputs[2], mix_wet_col.inputs[6])

    mix_ao = nodes.new("ShaderNodeMix")
    mix_ao.data_type = "RGBA"
    mix_ao.blend_type = "MULTIPLY"
    mix_ao.location = (0, 220)
    mix_ao.inputs[0].default_value = 0.85
    links.new(mix_wet_col.outputs[2], mix_ao.inputs[6])
    links.new(ao.outputs["AO"], mix_ao.inputs[7])
    links.new(mix_ao.outputs[2], bsdf.inputs["Base Color"])

    mix_rough = nodes.new("ShaderNodeMix")
    mix_rough.data_type = "FLOAT"
    mix_rough.location = (-180, -80)
    mix_rough.inputs[2].default_value = 0.88  # Dry rough limestone
    mix_rough.inputs[3].default_value = 0.08  # Misty rainwater reflection sheen
    links.new(m_puddle_flat.outputs["Value"], mix_rough.inputs[0])
    links.new(mix_rough.outputs[0], bsdf.inputs["Roughness"])

    bsdf.inputs["Metallic"].default_value = 0.0
    _set_input(bsdf, ["Specular IOR Level", "Specular"], 0.54)

    m_stone_h = nodes.new("ShaderNodeMath")
    m_stone_h.operation = "MULTIPLY"
    m_stone_h.location = (-480, -400)
    links.new(n_stone.outputs["Fac"], m_stone_h.inputs[0])
    links.new(ramp_crack.outputs["Color"], m_stone_h.inputs[1])

    m_bump_dry = nodes.new("ShaderNodeMath")
    m_bump_dry.operation = "SUBTRACT"
    m_bump_dry.location = (-360, -280)
    m_bump_dry.inputs[0].default_value = 1.0
    links.new(m_puddle_flat.outputs["Value"], m_bump_dry.inputs[1])

    m_bump_str = nodes.new("ShaderNodeMath")
    m_bump_str.operation = "MULTIPLY"
    m_bump_str.location = (-160, -280)
    m_bump_str.inputs[1].default_value = 0.46
    links.new(m_bump_dry.outputs["Value"], m_bump_str.inputs[0])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (220, -240)
    bump.inputs["Distance"].default_value = 0.010
    links.new(m_bump_str.outputs["Value"], bump.inputs["Strength"])
    links.new(m_stone_h.outputs["Value"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def create_all_materials() -> dict:
    """Create and return the entire project material library."""
    mats = {}

    # 1-3: Gritty ancient dark desaturated weathered medieval steel
    mats["MAT_Steel_Worn"] = _build_steel_material(
        "MAT_Steel_Worn",
        base_dark=(0.052, 0.056, 0.060),
        base_mid=(0.125, 0.132, 0.138),
        base_edge=(0.28, 0.29, 0.30),
        rust_tint=(0.13, 0.065, 0.032),
        base_rough=0.46,
        rust_amount=0.38,
    )
    mats["MAT_Steel_Oxidized"] = _build_steel_material(
        "MAT_Steel_Oxidized",
        base_dark=(0.042, 0.046, 0.050),
        base_mid=(0.092, 0.100, 0.106),
        base_edge=(0.22, 0.23, 0.24),
        rust_tint=(0.14, 0.068, 0.034),
        base_rough=0.54,
        rust_amount=0.42,
    )
    mats["MAT_Steel_Dark"] = _build_steel_material(
        "MAT_Steel_Dark",
        base_dark=(0.025, 0.028, 0.030),
        base_mid=(0.065, 0.070, 0.074),
        base_edge=(0.18, 0.19, 0.20),
        rust_tint=(0.12, 0.055, 0.028),
        base_rough=0.58,
        rust_amount=0.36,
    )

    # 4: Chainmail dark gunmetal grime
    mat_cm, nodes, links, bsdf, _ = _new_material("MAT_Chainmail")
    tc = _add_tex_coord(nodes, -1100, 0)
    vor = nodes.new("ShaderNodeTexVoronoi")
    vor.location = (-780, -160)
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 100.0
    links.new(tc.outputs["Object"], vor.inputs["Vector"])
    n_grime = nodes.new("ShaderNodeTexNoise")
    n_grime.location = (-780, 120)
    n_grime.inputs["Scale"].default_value = 14.0
    links.new(tc.outputs["Object"], n_grime.inputs["Vector"])
    mix_cm = nodes.new("ShaderNodeMix")
    mix_cm.data_type = "RGBA"
    mix_cm.location = (-360, 120)
    mix_cm.inputs[6].default_value = (0.025, 0.028, 0.030, 1.0)
    mix_cm.inputs[7].default_value = (0.088, 0.095, 0.100, 1.0)
    links.new(n_grime.outputs["Fac"], mix_cm.inputs[0])
    links.new(mix_cm.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.84
    bsdf.inputs["Roughness"].default_value = 0.54
    bump_cm = nodes.new("ShaderNodeBump")
    bump_cm.location = (180, -160)
    bump_cm.inputs["Strength"].default_value = 0.35
    bump_cm.inputs["Distance"].default_value = 0.003
    links.new(vor.outputs["Distance"], bump_cm.inputs["Height"])
    links.new(bump_cm.outputs["Normal"], bsdf.inputs["Normal"])
    mats["MAT_Chainmail"] = mat_cm

    # 5-6: Dark & Brown Weathered Leather
    mats["MAT_Leather_Dark"] = _build_leather_material(
        "MAT_Leather_Dark",
        dark_rgb=(0.020, 0.017, 0.014),
        worn_rgb=(0.052, 0.042, 0.034),
        roughness_base=0.62,
    )
    mats["MAT_Leather_Brown"] = _build_leather_material(
        "MAT_Leather_Brown",
        dark_rgb=(0.048, 0.028, 0.018),
        worn_rgb=(0.105, 0.065, 0.040),
        roughness_base=0.56,
    )

    # 7-9: Deep Dark Pine-Forest Green Cloth & Crest Tabard
    crest_img = _generate_tabard_crest_image()
    mats["MAT_Fabric_ForestGreen"] = _build_fabric_material(
        "MAT_Fabric_ForestGreen",
        dark_rgb=(0.016, 0.034, 0.026),
        light_rgb=(0.042, 0.072, 0.056),
        grime_rgb=(0.038, 0.040, 0.030),
        weave_scale=185.0,
    )
    mats["MAT_Fabric_Cape"] = _build_fabric_material(
        "MAT_Fabric_Cape",
        dark_rgb=(0.014, 0.028, 0.022),
        light_rgb=(0.038, 0.062, 0.048),
        grime_rgb=(0.035, 0.036, 0.028),
        weave_scale=150.0,
    )
    mats["MAT_Fabric_Tabard"] = _build_fabric_material(
        "MAT_Fabric_Tabard",
        dark_rgb=(0.016, 0.032, 0.025),
        light_rgb=(0.040, 0.068, 0.054),
        grime_rgb=(0.038, 0.040, 0.030),
        weave_scale=175.0,
        with_crest_img=crest_img,
    )

    # 10: Muted Aged Tarnished Bronze/Brass
    mats["MAT_Brass_Aged"] = _build_steel_material(
        "MAT_Brass_Aged",
        base_dark=(0.082, 0.066, 0.032),
        base_mid=(0.155, 0.122, 0.056),
        base_edge=(0.27, 0.21, 0.095),
        rust_tint=(0.045, 0.055, 0.034),
        base_rough=0.48,
        rust_amount=0.42,
        scratch_scale=34.0,
    )

    # 11: Rust
    mat_rust, nodes, links, bsdf, _ = _new_material("MAT_Rust")
    tc = _add_tex_coord(nodes, -900, 0)
    n_r = nodes.new("ShaderNodeTexNoise")
    n_r.location = (-620, 100)
    n_r.inputs["Scale"].default_value = 28.0
    n_r.inputs["Detail"].default_value = 8.0
    links.new(tc.outputs["Object"], n_r.inputs["Vector"])
    mix_r = nodes.new("ShaderNodeMix")
    mix_r.data_type = "RGBA"
    mix_r.location = (-280, 100)
    mix_r.inputs[6].default_value = (0.085, 0.035, 0.016, 1.0)
    mix_r.inputs[7].default_value = (0.18, 0.075, 0.032, 1.0)
    links.new(n_r.outputs["Fac"], mix_r.inputs[0])
    links.new(mix_r.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.20
    bsdf.inputs["Roughness"].default_value = 0.90
    bump_r = nodes.new("ShaderNodeBump")
    bump_r.location = (180, -140)
    bump_r.inputs["Strength"].default_value = 0.30
    bump_r.inputs["Distance"].default_value = 0.004
    links.new(n_r.outputs["Fac"], bump_r.inputs["Height"])
    links.new(bump_r.outputs["Normal"], bsdf.inputs["Normal"])
    mats["MAT_Rust"] = mat_rust

    # 12: Weathered Stone Pedestal
    mats["MAT_Stone_Weathered"] = _build_stone_pedestal_material()

    # 13: Dark Olive Moss
    mat_moss, nodes, links, bsdf, _ = _new_material("MAT_Moss")
    tc = _add_tex_coord(nodes, -800, 0)
    n_m = nodes.new("ShaderNodeTexNoise")
    n_m.location = (-540, 100)
    n_m.inputs["Scale"].default_value = 38.0
    n_m.inputs["Detail"].default_value = 10.0
    links.new(tc.outputs["Object"], n_m.inputs["Vector"])
    mix_m = nodes.new("ShaderNodeMix")
    mix_m.data_type = "RGBA"
    mix_m.location = (-240, 100)
    mix_m.inputs[6].default_value = (0.025, 0.042, 0.018, 1.0)
    mix_m.inputs[7].default_value = (0.068, 0.092, 0.040, 1.0)
    links.new(n_m.outputs["Fac"], mix_m.inputs[0])
    links.new(mix_m.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.94
    _set_input(bsdf, ["Sheen Weight", "Sheen"], 0.30)
    bump_m = nodes.new("ShaderNodeBump")
    bump_m.location = (160, -140)
    bump_m.inputs["Strength"].default_value = 0.38
    bump_m.inputs["Distance"].default_value = 0.005
    links.new(n_m.outputs["Fac"], bump_m.inputs["Height"])
    links.new(bump_m.outputs["Normal"], bsdf.inputs["Normal"])
    mats["MAT_Moss"] = mat_moss

    # 14: Dirt & Wet Bark Roots
    mats["MAT_Dirt"] = _build_leather_material(
        "MAT_Dirt",
        dark_rgb=(0.025, 0.022, 0.016),
        worn_rgb=(0.058, 0.050, 0.036),
        roughness_base=0.82,
    )

    # Utility materials
    mat_void, _, _, bsdf_v, _ = _new_material("MAT_Helm_Void")
    bsdf_v.inputs["Base Color"].default_value = (0.003, 0.003, 0.004, 1.0)
    bsdf_v.inputs["Metallic"].default_value = 0.0
    bsdf_v.inputs["Roughness"].default_value = 0.98
    _set_input(bsdf_v, ["Specular IOR Level", "Specular"], 0.01)
    mats["MAT_Helm_Void"] = mat_void

    mat_flame, _, _, bsdf_f, _ = _new_material("MAT_Lantern_Flame")
    bsdf_f.inputs["Base Color"].default_value = (0.72, 0.42, 0.16, 1.0)
    bsdf_f.inputs["Roughness"].default_value = 0.35
    _set_input(bsdf_f, ["Emission Color", "Emission"], (0.92, 0.52, 0.18, 1.0))
    _set_input(bsdf_f, ["Emission Strength"], 1.15)
    mats["MAT_Lantern_Flame"] = mat_flame

    mat_bg, nodes, links, bsdf_bg, _ = _new_material("MAT_BG_Silhouette")
    bsdf_bg.inputs["Base Color"].default_value = (0.015, 0.022, 0.025, 1.0)
    bsdf_bg.inputs["Roughness"].default_value = 0.99
    _set_input(bsdf_bg, ["Specular IOR Level", "Specular"], 0.0)
    _set_input(bsdf_bg, ["Emission Color", "Emission"], (0.014, 0.020, 0.024, 1.0))
    _set_input(bsdf_bg, ["Emission Strength"], 0.18)
    mats["MAT_BG_Silhouette"] = mat_bg

    return mats
