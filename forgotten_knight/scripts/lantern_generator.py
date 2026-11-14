"""Grounded medieval hanging lantern generator for THE FORGOTTEN KNIGHT (Section 14).
Suspended cleanly from left hip/belt attachment anchor near left gauntlet with aged brass
cage frame, dome cap, vertical guard bars, frosted glass inner chamber, and subtle ember wick
in collection 14_LANTERN (zero neon/bright magical glow).
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix
import config


def build_lantern(detail: str = "MEDIUM") -> dict:
    """Build hanging medieval iron/brass lantern attached beside Left (+X) hip."""
    anchor = config.LANTERN_ANCHOR  # (0.295, 0.018, 0.735)
    # Slight natural gravity hang tilt outward & down
    rot = Matrix.Rotation(math.radians(-6.0), 4, "Y") @ Matrix.Rotation(math.radians(8.0), 4, "X")
    base_xf = Matrix.Translation(anchor) @ rot

    # 1. Suspension Hook & Chain Link connecting UP into Left waist/baldric belt at Z~0.83
    bm_chain = bmesh.new()
    chain_pts = [
        anchor + Vector((-0.075, -0.02, 0.14)),  # Anchors directly into left waist belt
        anchor + Vector((-0.035, -0.01, 0.085)),
        anchor + Vector((-0.012, 0.0, 0.045)),
        anchor + Vector((0.0, 0.0, 0.005)),
    ]
    config.tube_along_points(bm_chain, chain_pts, radii=0.0042, radial_segs=8)
    # Top suspension ring
    ring_pts = [
        base_xf @ Vector((math.cos(2 * math.pi * k / 14) * 0.015, 0.0, 0.012 + math.sin(2 * math.pi * k / 14) * 0.015))
        for k in range(15)
    ]
    config.tube_along_points(bm_chain, ring_pts, radii=0.0038, radial_segs=6, cap_start=False, cap_end=False)
    chain_obj = config.finalize_bmesh(bm_chain, "Lantern_Chain_Hook", "14_LANTERN", mat_name="MAT_Steel_Dark", smooth=True)

    # 2. Metal Housing: hexagonal stepped dome cap, mid guard band, lower oil reservoir pan, 6 pillars
    bm_frame = bmesh.new()
    cap_slices = [
        (0.002, 0.007),
        (-0.008, 0.016),
        (-0.022, 0.036),
        (-0.032, 0.047),
        (-0.038, 0.049),
        (-0.044, 0.039),
    ]
    rings_cap = []
    for z, r in cap_slices:
        rings_cap.append([base_xf @ Vector((math.cos(2 * math.pi * k / 12) * r, math.sin(2 * math.pi * k / 12) * r, z)) for k in range(12)])
    config.loft_rings(bm_frame, rings_cap, close_cap_start=True, close_cap_end=True)

    # Mid equatorial reinforcing ring & bottom oil pan + turned finial
    band_pts = [base_xf @ Vector((math.cos(2 * math.pi * k / 16) * 0.037, math.sin(2 * math.pi * k / 16) * 0.037, -0.086)) for k in range(17)]
    config.tube_along_points(bm_frame, band_pts, radii=0.0026, radial_segs=6, cap_start=False, cap_end=False)

    base_slices = [
        (-0.130, 0.037),
        (-0.138, 0.046),
        (-0.148, 0.044),
        (-0.160, 0.028),
        (-0.174, 0.005),
    ]
    rings_bot = []
    for z, r in base_slices:
        rings_bot.append([base_xf @ Vector((math.cos(2 * math.pi * k / 12) * r, math.sin(2 * math.pi * k / 12) * r, z)) for k in range(12)])
    config.loft_rings(bm_frame, rings_bot, close_cap_start=True, close_cap_end=True)

    # 6 vertical corner guard struts
    for k in range(6):
        ang = k * math.pi / 3.0
        p_t = base_xf @ Vector((math.cos(ang) * 0.037, math.sin(ang) * 0.037, -0.040))
        p_b = base_xf @ Vector((math.cos(ang) * 0.035, math.sin(ang) * 0.035, -0.134))
        config.tube_along_points(bm_frame, [p_t, p_b], radii=0.0032, radial_segs=6)

    housing_obj = config.finalize_bmesh(bm_frame, "Lantern_Frame_Housing", "14_LANTERN", mat_name="MAT_Brass_Aged", smooth=True)

    # 3. Hexagonal Glass Housing Shell + Inner Tallow Candle & Dim Ember Wick
    bm_glass = bmesh.new()
    g_rings = [
        [base_xf @ Vector((math.cos(2 * math.pi * k / 6) * 0.029, math.sin(2 * math.pi * k / 6) * 0.029, -0.043)) for k in range(6)],
        [base_xf @ Vector((math.cos(2 * math.pi * k / 6) * 0.031, math.sin(2 * math.pi * k / 6) * 0.031, -0.086)) for k in range(6)],
        [base_xf @ Vector((math.cos(2 * math.pi * k / 6) * 0.028, math.sin(2 * math.pi * k / 6) * 0.028, -0.131)) for k in range(6)],
    ]
    config.loft_rings(bm_glass, g_rings, close_cap_start=True, close_cap_end=True)
    glass_obj = config.finalize_bmesh(bm_glass, "Lantern_Glass_Chamber", "14_LANTERN", mat_name="MAT_Glass_Lantern", smooth=False)

    bm_in = bmesh.new()
    res = bmesh.ops.create_icosphere(bm_in, subdivisions=2, radius=0.014)
    for v in res["verts"]:
        v.co.z *= 1.85
        v.co += Vector((0.0, 0.0, -0.092))
        v.co = base_xf @ v.co
    bm_in.normal_update()
    chamber_obj = config.finalize_bmesh(bm_in, "Lantern_Inner_Chamber", "14_LANTERN", mat_name="MAT_Lantern_Flame", smooth=True)

    # Subtle local fill point light inside lantern (tiny 0.35W non-magical warmth grazing left thigh only)
    light_data = bpy.data.lights.new(name="Light_Lantern_Wick", type="POINT")
    light_data.energy = 0.35
    light_data.color = (0.95, 0.58, 0.24)
    light_data.shadow_soft_size = 0.03
    light_obj = bpy.data.objects.new(name="Light_Lantern_Wick", object_data=light_data)
    light_obj.location = base_xf @ Vector((0.0, 0.0, -0.092))
    config.link_object(light_obj, "14_LANTERN")

    return {"chain": chain_obj, "housing": housing_obj, "glass": glass_obj, "chamber": chamber_obj, "light": light_obj}
