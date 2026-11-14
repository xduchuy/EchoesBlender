"""Closed medieval helmet reconstruction (barbute/sallet hybrid) for THE FORGOTTEN KNIGHT.
Produces real layered steel geometry: pointed domed skull, longitudinal ridge crest,
projecting brow brim, slotted faceguard visor, deep pitch-black interior cavity,
flared nape guard, and riveted seam hardware in 03_HELMET.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import config


def _head_transform() -> Matrix:
    """Subtle downward-and-slightly-turned pitch/yaw centered at neck-head pivot."""
    pivot = config.JOINTS["head_pivot"]
    rot = Euler((math.radians(8.5), math.radians(-1.5), math.radians(-5.0)), "XYZ").to_matrix().to_4x4()
    return Matrix.Translation(pivot) @ rot @ Matrix.Translation(-pivot)


def _apply_matrix_to_bmesh(bm, mat: Matrix):
    for v in bm.verts:
        v.co = mat @ v.co


def _build_skull_dome(detail_segs: int, mat_xform: Matrix) -> bpy.types.Object:
    """Construct ogival-domed steel skull with flared rear neck defense."""
    bm = bmesh.new()
    cx, cy = 0.0, -0.022
    # Vertical rings from neck skirt up to pointed apex
    profile = [
        # (z, rx, ry_fwd, ry_back, y_shift)
        (1.565, 0.098, 0.112, 0.116, 0.008),  # Lower flared nape skirt
        (1.605, 0.095, 0.114, 0.112, 0.002),  # Cheekbase
        (1.660, 0.096, 0.120, 0.116, -0.004), # Temple / brow plane
        (1.720, 0.095, 0.118, 0.114, -0.005), # Upper brow dome
        (1.775, 0.084, 0.106, 0.104, -0.003), # Crown taper
        (1.815, 0.060, 0.076, 0.078, -0.002), # Upper acorn slope
        (1.842, 0.026, 0.034, 0.036, 0.000),  # Pointed keel peak
        (1.855, 0.006, 0.009, 0.009, 0.000),  # Finial tip
    ]

    rng = config.seeded_rng(101)
    rings = []
    for iz, (z, rx, ryf, ryb, ys) in enumerate(profile):
        ring = []
        for i in range(detail_segs):
            a = 2.0 * math.pi * i / detail_segs
            ca = math.cos(a)
            sa = math.sin(a)  # -1 is front (-Y), +1 is back (+Y)
            x = cx + ca * rx
            ry = ryf if sa < 0.0 else ryb
            y = cy + ys + sa * ry

            # Open front face cavity for lower 2 rings so visor slots stay separate
            if iz < 2 and sa < -0.35:
                y += 0.025 * (-sa - 0.35)

            # Hammered irregular medieval steel silhouette + central ridge lift
            ridge = 0.009 * max(0.0, 1.0 - abs(ca) * 5.0) if (z > 1.66) else 0.0
            dent = (rng.random() - 0.5) * 0.0022 if 0 < iz < len(profile) - 2 else 0.0
            if sa < 0.0 and z > 1.66:
                y -= ridge * (-sa)
            elif sa >= 0.0 and z > 1.66:
                y += ridge * 0.7 * sa
            z_off = ridge * 0.55 if iz >= len(profile) - 3 else 0.0
            ring.append(Vector((x + dent, y + dent, z + z_off)))
        rings.append(ring)

    config.loft_rings(bm, rings, close_cap_start=False, close_cap_end=True)
    _apply_matrix_to_bmesh(bm, mat_xform)
    obj = config.finalize_bmesh(bm, "Helm_Skull", "03_HELMET", mat_name="MAT_Steel_Worn", smooth=True)
    config.add_solidify(obj, thickness=0.0045, offset=1.0)
    return obj


def _build_central_crest(mat_xform: Matrix) -> bpy.types.Object:
    """Raised forged longitudinal steel comb crest along the crown ridge."""
    bm = bmesh.new()
    # Spine arc from front brow peak over apex down rear occiput
    spine = []
    steps = 18
    for i in range(steps):
        t = i / (steps - 1)
        # Angle from front brow (theta=0.32 rad) over top apex to back (theta=2.65 rad)
        ang = 0.32 + t * 2.28
        y = -0.024 - math.cos(ang) * 0.118
        z = 1.715 + math.sin(ang) * 0.145
        spine.append((Vector((0.0, y, z)), Vector((0.0, -math.cos(ang), math.sin(ang))).normalized()))

    rings = []
    for pt, norm in spine:
        half_w = 0.0075
        peak_h = 0.015
        rings.append([
            pt + Vector((-half_w, 0.0, 0.0)) - norm * 0.004,
            pt + Vector((-0.003, 0.0, 0.0)) + norm * peak_h,
            pt + Vector((0.003, 0.0, 0.0)) + norm * peak_h,
            pt + Vector((half_w, 0.0, 0.0)) - norm * 0.004,
        ])
    config.loft_rings(bm, rings, close_cap_start=True, close_cap_end=True)
    _apply_matrix_to_bmesh(bm, mat_xform)
    return config.finalize_bmesh(bm, "Helm_Crest", "03_HELMET", mat_name="MAT_Steel_Oxidized", smooth=True)


def _build_brow_brim(mat_xform: Matrix) -> bpy.types.Object:
    """Projecting armored eyebrow brim casting shadow across the eye slit."""
    bm = bmesh.new()
    steps = 16
    rings = []
    for i in range(steps):
        t = i / (steps - 1) * 2.0 - 1.0  # -1..+1 around front hemisphere
        ang = t * 1.48  # radians from front -Y axis
        x = math.sin(ang) * 0.102
        y_base = -0.025 - math.cos(ang) * 0.122
        dip = 0.012 * max(0.0, 1.0 - abs(t) * 2.4)
        proj = 0.022 * max(0.25, math.cos(ang))
        z = 1.716 - dip
        ring = [
            Vector((x * 0.94, y_base + 0.006, z + 0.008)),
            Vector((x * 1.03, y_base - proj, z - 0.003)),
            Vector((x * 1.02, y_base - proj * 0.92, z - 0.011)),
            Vector((x * 0.94, y_base + 0.008, z - 0.005)),
        ]
        rings.append(ring)
    config.loft_rings(bm, rings, close_cap_start=True, close_cap_end=True)
    _apply_matrix_to_bmesh(bm, mat_xform)
    return config.finalize_bmesh(bm, "Helm_Brow_Brim", "03_HELMET", mat_name="MAT_Steel_Dark", smooth=True)


def _build_slotted_faceguard(mat_xform: Matrix) -> bpy.types.Object:
    """Build pointed angular visor faceplate with central nasal rib & vertical slots."""
    bm = bmesh.new()
    cy = -0.024

    def _face_pt(ang: float, z: float, r_off: float = 0.0) -> Vector:
        # Pointed medieval beak profile at front center (ang near 0)
        beak = 0.022 * max(0.0, 1.0 - abs(ang) * 1.35)
        rx = 0.095 + r_off
        ry = 0.118 + beak + r_off
        return Vector((math.sin(ang) * rx, cy - math.cos(ang) * ry, z))

    def _add_bar(ang_min: float, ang_max: float, z_top: float, z_bot: float, thick: float = 0.006):
        steps_u = 4
        steps_v = 5
        front_grid = []
        back_grid = []
        for iu in range(steps_u):
            z = z_top + (z_bot - z_top) * (iu / (steps_u - 1))
            # Chin tapers narrower toward bottom
            t_z = (1.70 - z) / 0.14
            row_f = []
            row_b = []
            for iv in range(steps_v):
                a = ang_min + (ang_max - ang_min) * (iv / (steps_v - 1))
                # Slight inward chin taper
                taper = -0.008 * max(0.0, t_z)
                pf = _face_pt(a, z, r_off=taper)
                pb = _face_pt(a, z, r_off=taper - thick)
                row_f.append(bm.verts.new(pf))
                row_b.append(bm.verts.new(pb))
            front_grid.append(row_f)
            back_grid.append(row_b)

        for iu in range(steps_u - 1):
            for iv in range(steps_v - 1):
                bm.faces.new((front_grid[iu][iv], front_grid[iu][iv + 1], front_grid[iu + 1][iv + 1], front_grid[iu + 1][iv]))
                bm.faces.new((back_grid[iu][iv + 1], back_grid[iu][iv], back_grid[iu + 1][iv], back_grid[iu + 1][iv + 1]))
        # Stitch outer box border
        for iv in range(steps_v - 1):
            bm.faces.new((back_grid[0][iv], back_grid[0][iv + 1], front_grid[0][iv + 1], front_grid[0][iv]))
            bm.faces.new((front_grid[-1][iv], front_grid[-1][iv + 1], back_grid[-1][iv + 1], back_grid[-1][iv]))
        for iu in range(steps_u - 1):
            bm.faces.new((back_grid[iu][0], front_grid[iu][0], front_grid[iu + 1][0], back_grid[iu + 1][0]))
            bm.faces.new((front_grid[iu][-1], back_grid[iu][-1], back_grid[iu + 1][-1], front_grid[iu + 1][-1]))

    # Horizontal lower chin border wrapping cheek-to-cheek (leaves top eye slit OPEN!)
    _add_bar(-1.26, 1.26, 1.592, 1.568, thick=0.0065)
    # Horizontal cheek rim just beneath the dark narrow horizontal eye slit (eye gap Z ~ 1.693..1.703)
    _add_bar(-1.26, 1.26, 1.693, 1.678, thick=0.0065)
    # Bold central vertical nasal rib connecting brow to chin
    _add_bar(-0.075, 0.075, 1.710, 1.568, thick=0.0085)

    # Vertical slotted visor slats on Right (-ang) & Left (+ang) cheeks (5 slats per side)
    slat_centers = [0.22, 0.42, 0.62, 0.83, 1.06]
    for s_ang in slat_centers:
        _add_bar(s_ang - 0.048, s_ang + 0.048, 1.682, 1.588, thick=0.0055)
        _add_bar(-s_ang - 0.048, -s_ang + 0.048, 1.682, 1.588, thick=0.0055)

    # Solid side cheek plates anchoring visor cleanly into skull
    _add_bar(1.12, 1.38, 1.700, 1.582, thick=0.006)
    _add_bar(-1.38, -1.12, 1.700, 1.582, thick=0.006)

    _apply_matrix_to_bmesh(bm, mat_xform)
    return config.finalize_bmesh(bm, "Helm_Faceguard", "03_HELMET", mat_name="MAT_Steel_Dark", smooth=True)


def _build_inner_shadow_liner(mat_xform: Matrix) -> bpy.types.Object:
    """Completely closed inner matte-black cavity wall hiding 100% of interior face."""
    bm = bmesh.new()
    res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=0.088)
    for v in res["verts"]:
        v.co.x *= 0.88
        v.co.y *= 1.02
        v.co.z *= 1.28
        v.co += Vector((0.0, -0.025, 1.685))
    bm.normal_update()
    _apply_matrix_to_bmesh(bm, mat_xform)
    return config.finalize_bmesh(bm, "Helm_InnerShadow", "03_HELMET", mat_name="MAT_Helm_Void", smooth=True)


def _build_helmet_rivets(mat_xform: Matrix) -> bpy.types.Object:
    """Brass/rusted rivets lining the brow rim & lower faceguard cheeks."""
    pts = []
    cy = -0.025
    for ang in (-1.15, -0.92, -0.68, -0.44, -0.20, 0.20, 0.44, 0.68, 0.92, 1.15):
        n = Vector((math.sin(ang), -math.cos(ang), 0.15)).normalized()
        pts.append((Vector((math.sin(ang) * 0.100, cy - math.cos(ang) * 0.123, 1.725)), n))
        pts.append((Vector((math.sin(ang) * 0.092, cy - math.cos(ang) * 0.116, 1.580)), n))
    # Transform points with head rotation
    rot_m = mat_xform.to_3x3()
    x_pts = [(mat_xform @ p, (rot_m @ n).normalized()) for (p, n) in pts]
    return config.add_rivet_strip("Helm_Rivets", "03_HELMET", x_pts, radius=0.0042, mat_name="MAT_Rust")


def build_helmet(detail: str = "MEDIUM") -> dict:
    """Create the complete closed helmet assembly in collection 03_HELMET."""
    ds = config.DETAIL_SETTINGS[detail]
    segs = ds["radial_segs"]
    head_mat = _head_transform()

    skull = _build_skull_dome(segs, head_mat)
    crest = _build_central_crest(head_mat)
    brow = _build_brow_brim(head_mat)
    visor = _build_slotted_faceguard(head_mat)
    void_liner = _build_inner_shadow_liner(head_mat)
    rivets = _build_helmet_rivets(head_mat)

    return {
        "skull": skull,
        "crest": crest,
        "brow": brow,
        "visor": visor,
        "void_liner": void_liner,
        "rivets": rivets,
    }
