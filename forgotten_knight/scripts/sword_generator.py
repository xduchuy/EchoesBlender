"""Realistic medieval weapons generator for THE FORGOTTEN KNIGHT (Section 12 & 13).
Builds BOTH consistent weapons in collection 13_WEAPONS:
1. Sword_Main: Double-edged longsword with central fuller, weathered crossguard,
   ribbed leather grip, and brass pommel gripped squarely in Hand_R with tip touching
   pedestal stone near right foot.
2. Sword_Back & Scabbard_Back: Diagonal back-mounted leather-wrapped scabbard +
   criss-cross suspension wrap + brass chape + exposed upper sword hilt rising over the
   right shoulder ON TOP of the cape.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix
import config


def _sword_frame(pommel: Vector, tip: Vector, blade_facing: Vector) -> Matrix:
    """Construct orthonormal transform where +Z runs tip->pommel along sword spine,
    +X runs crossguard width, +Y faces blade flat."""
    z_up = (pommel - tip).normalized()
    x_side = blade_facing.cross(z_up).normalized()
    y_flat = z_up.cross(x_side).normalized()
    mat = Matrix((
        (x_side.x, y_flat.x, z_up.x, tip.x),
        (x_side.y, y_flat.y, z_up.y, tip.y),
        (x_side.z, y_flat.z, z_up.z, tip.z),
        (0.0,      0.0,      0.0,    1.0),
    ))
    return mat


def _build_blade_mesh(bm, length: float, half_w_base: float = 0.029,
                      half_w_taper: float = 0.015, thick_ridge: float = 0.0055):
    """Double-edged medieval longsword blade from tip (Z=0) up to guard (Z=length)
    with diamond profile & recessed fuller groove."""
    slices = [
        (0.000, 0.001, 0.0008, 0.0008),  # Sharp tip
        (0.065, half_w_taper * 0.72, 0.0032, 0.0028),
        (length * 0.35, half_w_taper * 0.95, thick_ridge * 0.78, thick_ridge * 0.50),
        (length * 0.72, half_w_base * 0.90, thick_ridge * 0.92, thick_ridge * 0.56),
        (length, half_w_base, thick_ridge, thick_ridge * 0.62),  # Base at crossguard
    ]
    rings = []
    for z, hw, tr, tf in slices:
        # 8-vertex fuller/ridge section around diamond blade perimeter
        ring = [
            Vector((0.0, -tf, z)),       # Front fuller valley
            Vector((hw * 0.32, -tr, z)), # Right bevel ridge front
            Vector((hw, 0.0, z)),        # Right sharp edge
            Vector((hw * 0.32, tr, z)),  # Right bevel ridge back
            Vector((0.0, tf, z)),        # Back fuller valley
            Vector((-hw * 0.32, tr, z)), # Left bevel ridge back
            Vector((-hw, 0.0, z)),       # Left sharp edge
            Vector((-hw * 0.32, -tr, z)),# Left bevel ridge front
        ]
        rings.append(ring)
    config.loft_rings(bm, rings, close_cap_start=True, close_cap_end=True)


def _build_crossguard_mesh(bm, z_guard: float, span: float = 0.255):
    """Build slightly arched forged medieval crossguard with flared ends."""
    steps = 11
    rings = []
    for i in range(steps):
        t = i / (steps - 1) * 2.0 - 1.0  # -1..+1
        x = t * (span * 0.5)
        # Subtle downward quillon droop toward blade like reference!
        z = z_guard - 0.014 * (t * t)
        rx = 0.012 if abs(t) < 0.2 else (0.014 if abs(t) > 0.85 else 0.0085)
        ry = 0.018 if abs(t) < 0.15 else 0.011
        ring = [
            Vector((x, -ry, z)),
            Vector((x, 0.0, z + rx)),
            Vector((x, ry, z)),
            Vector((x, 0.0, z - rx)),
        ]
        rings.append(ring)
    config.loft_rings(bm, rings, close_cap_start=True, close_cap_end=True)


def _build_grip_and_pommel(bm_grip, bm_pom, z_guard: float, z_pommel: float):
    """Build ribbed bound leather grip and faceted teardrop brass pommel."""
    grip_len = z_pommel - z_guard - 0.042
    pts_g = []
    radii_g = []
    steps = 9
    for i in range(steps):
        t = i / (steps - 1)
        z = z_guard + 0.008 + t * grip_len
        pts_g.append(Vector((0.0, 0.0, z)))
        # Slight waist taper + hand-swell + leather cord ribs
        swell = 0.0165 - 0.003 * math.sin(t * math.pi)
        rib = 0.0018 if i % 2 == 1 else 0.0
        radii_g.append(swell + rib)
    config.tube_along_points(bm_grip, pts_g, radii_g, radial_segs=10, elliptical=(0.82, 1.08))

    # Teardrop / scent-stopper brass pommel at z_pommel
    pom_slices = [
        (z_pommel - 0.042, 0.016, 0.014),
        (z_pommel - 0.025, 0.024, 0.020),
        (z_pommel - 0.005, 0.027, 0.022),
        (z_pommel + 0.016, 0.020, 0.016),
        (z_pommel + 0.028, 0.006, 0.006),
    ]
    rings_p = []
    for z, rx, ry in pom_slices:
        rings_p.append([Vector((math.cos(2 * math.pi * k / 10) * rx, math.sin(2 * math.pi * k / 10) * ry, z)) for k in range(10)])
    config.loft_rings(bm_pom, rings_p, close_cap_start=True, close_cap_end=True)


def build_weapons(detail: str = "MEDIUM") -> dict:
    """Create main held longsword and diagonal back-mounted sword + leather scabbard in 13_WEAPONS."""
    objs = []

    # =========================================================================
    # 1. MAIN HELD LONGSWORD (gripped in Hand_R, tip resting on pedestal Z=0.004)
    # =========================================================================
    sm = config.SWORD_MAIN
    p_tip = sm["tip_pos"]
    p_guard = sm["guard_pos"]
    p_pom = sm["pommel_pos"]
    total_len = (p_pom - p_tip).length
    z_guard = (p_guard - p_tip).length
    z_pom = total_len - 0.028

    # Blade plane faces forward-outward (-0.25, -0.96, 0.0) so wide flat reads cleanly in Front 3/4!
    mat_main = _sword_frame(p_pom, p_tip, Vector((-0.28, -0.96, 0.0)))

    bm_blade = bmesh.new()
    _build_blade_mesh(bm_blade, length=z_guard, half_w_base=0.032, half_w_taper=0.018, thick_ridge=0.006)
    for v in bm_blade.verts:
        v.co = mat_main @ v.co
    objs.append(config.finalize_bmesh(bm_blade, "Weapon_Longsword_Blade", "13_WEAPONS", mat_name="MAT_Steel_Worn", smooth=False))

    bm_guard = bmesh.new()
    _build_crossguard_mesh(bm_guard, z_guard=z_guard, span=0.255)
    for v in bm_guard.verts:
        v.co = mat_main @ v.co
    objs.append(config.finalize_bmesh(bm_guard, "Weapon_Longsword_Guard", "13_WEAPONS", mat_name="MAT_Steel_Dark", smooth=True))

    bm_grip = bmesh.new()
    bm_pom = bmesh.new()
    _build_grip_and_pommel(bm_grip, bm_pom, z_guard=z_guard, z_pommel=z_pom)
    for v in bm_grip.verts:
        v.co = mat_main @ v.co
    for v in bm_pom.verts:
        v.co = mat_main @ v.co
    objs.append(config.finalize_bmesh(bm_grip, "Weapon_Longsword_Grip", "13_WEAPONS", mat_name="MAT_Leather_Brown", smooth=True))
    objs.append(config.finalize_bmesh(bm_pom, "Weapon_Longsword_Pommel", "13_WEAPONS", mat_name="MAT_Brass_Aged", smooth=True))

    # =========================================================================
    # 2. BACK-MOUNTED SHEATHED SWORD + SCABBARD (Diagonal OVER cape)
    # =========================================================================
    sb = config.SWORD_BACK
    b_tip = sb["scabbard_tip"]
    b_top = sb["scabbard_top"]
    b_pom = sb["pommel_pos"]
    back_len = (b_pom - b_tip).length
    z_scab_top = (b_top - b_tip).length
    z_b_guard = (sb["guard_pos"] - b_tip).length
    z_b_pom = back_len - 0.025

    mat_back = _sword_frame(b_pom, b_tip, Vector((0.0, 1.0, 0.0)))

    # Tapered leather scabbard body (Z=0.06 up to z_scab_top)
    bm_scab = bmesh.new()
    scab_rings = []
    for frac, hw, th in [(0.05, 0.015, 0.008), (0.35, 0.024, 0.011), (0.75, 0.032, 0.013), (1.0, 0.036, 0.015)]:
        z = frac * z_scab_top
        ring = [
            Vector((math.cos(2 * math.pi * k / 10) * hw, math.sin(2 * math.pi * k / 10) * th, z))
            for k in range(10)
        ]
        scab_rings.append(ring)
    config.loft_rings(bm_scab, scab_rings, close_cap_start=True, close_cap_end=True)

    # Diagonal criss-cross leather suspension wrap bands around upper-mid scabbard (just like Rear 3/4 view!)
    for z_w in (z_scab_top * 0.62, z_scab_top * 0.72, z_scab_top * 0.80, z_scab_top * 0.88):
        band_pts = []
        hw_z = 0.015 + (z_w / z_scab_top) * 0.022 + 0.003
        th_z = 0.008 + (z_w / z_scab_top) * 0.008 + 0.003
        for k in range(13):
            a = 2.0 * math.pi * k / 12
            band_pts.append(Vector((math.cos(a) * hw_z, math.sin(a) * th_z, z_w + math.sin(a) * 0.012)))
        config.tube_along_points(bm_scab, band_pts, radii=0.0065, radial_segs=6, cap_start=False, cap_end=False)

    for v in bm_scab.verts:
        v.co = mat_back @ v.co
    objs.append(config.finalize_bmesh(bm_scab, "Weapon_Back_Scabbard", "13_WEAPONS", mat_name="MAT_Leather_Brown", smooth=True))

    # Scabbard steel/brass throat locket & pointed bottom chape tip
    bm_chape = bmesh.new()
    # Bottom chape cone
    chape_rings = [
        [Vector((math.cos(2 * math.pi * k / 10) * 0.004, math.sin(2 * math.pi * k / 10) * 0.003, 0.0)) for k in range(10)],
        [Vector((math.cos(2 * math.pi * k / 10) * 0.018, math.sin(2 * math.pi * k / 10) * 0.010, 0.09)) for k in range(10)],
    ]
    config.loft_rings(bm_chape, chape_rings, close_cap_start=True, close_cap_end=True)
    # Throat locket collar
    locket_rings = [
        [Vector((math.cos(2 * math.pi * k / 10) * 0.038, math.sin(2 * math.pi * k / 10) * 0.017, z_scab_top - 0.04)) for k in range(10)],
        [Vector((math.cos(2 * math.pi * k / 10) * 0.039, math.sin(2 * math.pi * k / 10) * 0.018, z_scab_top + 0.005)) for k in range(10)],
    ]
    config.loft_rings(bm_chape, locket_rings, close_cap_start=True, close_cap_end=True)
    for v in bm_chape.verts:
        v.co = mat_back @ v.co
    objs.append(config.finalize_bmesh(bm_chape, "Weapon_Back_Scabbard_Fittings", "13_WEAPONS", mat_name="MAT_Brass_Aged", smooth=True))

    # Exposed upper hilt, crossguard, grip, and brass pommel emerging cleanly from scabbard top
    bm_bg = bmesh.new()
    _build_crossguard_mesh(bm_bg, z_guard=z_b_guard, span=0.235)
    for v in bm_bg.verts:
        v.co = mat_back @ v.co
    objs.append(config.finalize_bmesh(bm_bg, "Weapon_Back_Guard", "13_WEAPONS", mat_name="MAT_Steel_Dark", smooth=True))

    bm_bh = bmesh.new()
    bm_bp = bmesh.new()
    _build_grip_and_pommel(bm_bh, bm_bp, z_guard=z_b_guard, z_pommel=z_b_pom)
    for v in bm_bh.verts:
        v.co = mat_back @ v.co
    for v in bm_bp.verts:
        v.co = mat_back @ v.co
    objs.append(config.finalize_bmesh(bm_bh, "Weapon_Back_Grip", "13_WEAPONS", mat_name="MAT_Leather_Brown", smooth=True))
    objs.append(config.finalize_bmesh(bm_bp, "Weapon_Back_Pommel", "13_WEAPONS", mat_name="MAT_Brass_Aged", smooth=True))

    return {"weapons": objs}
