"""Belts, leather pouches, suspension hardware, and chest baldric strap
for THE FORGOTTEN KNIGHT in collection 12_BELTS.
Wraps anatomically around waist and torso armor with real strap thickness,
forged buckles, hanging leather tail, steel belt ring, hip satchel, and
diagonal back-scabbard baldric strap.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix
import config


def _wrap_waist_belt(bm, z_front: float, z_side: float, z_back: float,
                     rx: float, ry: float, width: float = 0.042,
                     thick: float = 0.009, segs: int = 28):
    """Add a contoured, buckled leather belt ring hugging the waist/fauld geometry."""
    outer_top, outer_bot = [], []
    inner_top, inner_bot = [], []
    for i in range(segs):
        ang = 2.0 * math.pi * i / segs  # 0=+X (Left), -pi/2=-Y (Front), +pi/2=+Y (Back)
        ca, sa = math.cos(ang), math.sin(ang)
        if sa < 0.0:
            z_c = z_front * (-sa) + z_side * (1.0 + sa)
        else:
            z_c = z_back * sa + z_side * (1.0 - sa)
        y_off = -0.008
        p_in = Vector((ca * rx, sa * ry + y_off, z_c))
        out_n = Vector((ca, sa, 0.0)).normalized()
        p_out = p_in + out_n * thick
        half_w = Vector((0.0, 0.0, width * 0.5))

        outer_top.append(bm.verts.new(p_out + half_w))
        outer_bot.append(bm.verts.new(p_out - half_w))
        inner_top.append(bm.verts.new(p_in + half_w))
        inner_bot.append(bm.verts.new(p_in - half_w))

    for i in range(segs):
        inext = (i + 1) % segs
        bm.faces.new((outer_bot[i], outer_bot[inext], outer_top[inext], outer_top[i]))
        bm.faces.new((inner_top[i], inner_top[inext], inner_bot[inext], inner_bot[i]))
        bm.faces.new((outer_top[i], outer_top[inext], inner_top[inext], inner_top[i]))
        bm.faces.new((inner_bot[i], inner_bot[inext], outer_bot[inext], outer_bot[i]))


def _add_buckle(bm, center: Vector, normal: Vector, width: float = 0.052, height: float = 0.056):
    """Build a solid rectangular beveled medieval belt buckle + prong."""
    n = normal.normalized()
    up = Vector((0.0, 0.0, 1.0))
    side = up.cross(n).normalized()
    up = n.cross(side).normalized()
    hw, hh = width * 0.5, height * 0.5
    bar = 0.0065
    # Four frame bars around perimeter
    corners = [
        center - side * hw - up * hh,
        center + side * hw - up * hh,
        center + side * hw + up * hh,
        center - side * hw + up * hh,
        center - side * hw - up * hh,
    ]
    config.tube_along_points(bm, corners, radii=bar, radial_segs=6, cap_start=False, cap_end=False)
    # Crossbar tongue
    config.tube_along_points(bm, [center - side * hw, center + side * hw * 0.3], radii=bar * 0.7, radial_segs=6)


def _add_pouch(bm, center: Vector, yaw_deg: float, tilt_out: float, size: tuple[float, float, float]):
    """Sculpted weathered leather belt satchel/pouch with overlapping curved flap & strap."""
    sx, sy, sz = size
    rot = Matrix.Rotation(math.radians(yaw_deg), 4, "Z") @ Matrix.Rotation(math.radians(tilt_out), 4, "Y")
    # Subdivide in isolated BMesh so subdivide_edges cannot invalidate shared verts
    bm_sub = bmesh.new()
    res = bmesh.ops.create_cube(bm_sub, size=1.0)
    bmesh.ops.subdivide_edges(bm_sub, edges=list(bm_sub.edges), cuts=2, use_grid_fill=True)
    xform = Matrix.Translation(center) @ rot
    v_map = {}
    for v in bm_sub.verts:
        co = v.co
        bulge = 1.0 + 0.18 * math.cos(co.z * math.pi)
        pt = Vector((co.x * sx * bulge, co.y * sy * bulge, co.z * sz))
        v_map[v] = bm.verts.new(xform @ pt)
    for f in bm_sub.faces:
        try:
            bm.faces.new([v_map[v] for v in f.verts])
        except ValueError:
            pass
    bm_sub.free()

    # Overlapping front flap curved cleanly down front face
    flap_pts = [
        Vector((0.0, 0.0, sz * 0.52)),
        Vector((0.0, -sy * 0.62, sz * 0.45)),
        Vector((0.0, -sy * 0.68, sz * 0.02)),
        Vector((0.0, -sy * 0.62, -sz * 0.25)),
    ]
    x_flap = [Matrix.Translation(center) @ rot @ p for p in flap_pts]
    rings = []
    for p in x_flap:
        right = (rot.to_3x3() @ Vector((sx * 0.54, 0.0, 0.0)))
        fwd = (rot.to_3x3() @ Vector((0.0, -0.008, 0.0)))
        rings.append([p - right, p - right + fwd, p + right + fwd, p + right])
    config.loft_rings(bm, rings, close_cap_start=True, close_cap_end=True)


def _build_belts_and_pouches() -> list:
    objs = []

    # 1. Primary & Crossed Diagonal Waist Belts hugging the torso waist (Z~0.94..1.05)
    bm_belt = bmesh.new()
    _wrap_waist_belt(bm_belt, z_front=1.03, z_side=1.04, z_back=1.05, rx=0.174, ry=0.125, width=0.044, thick=0.009)
    _wrap_waist_belt(bm_belt, z_front=0.955, z_side=1.005, z_back=0.995, rx=0.184, ry=0.134, width=0.036, thick=0.008)

    # Hanging leather belt tongue dangling down front-right center (per reference!)
    hang_pts = [
        Vector((-0.055, -0.145, 0.96)),
        Vector((-0.062, -0.158, 0.82)),
        Vector((-0.066, -0.172, 0.66)),
        Vector((-0.070, -0.185, 0.54)),
    ]
    rings_h = []
    for p in hang_pts:
        rings_h.append([
            p + Vector((-0.016, 0.0, 0.0)),
            p + Vector((-0.016, -0.007, 0.0)),
            p + Vector((0.016, -0.007, 0.0)),
            p + Vector((0.016, 0.0, 0.0)),
        ])
    config.loft_rings(bm_belt, rings_h, close_cap_start=True, close_cap_end=True)
    objs.append(config.finalize_bmesh(bm_belt, "Belts_Waist_Assembly", "12_BELTS", mat_name="MAT_Leather_Brown", smooth=True))

    # 2. Metal Buckles & Hanging Side Utility Ring
    bm_hw = bmesh.new()
    _add_buckle(bm_hw, Vector((-0.052, -0.140, 1.030)), Vector((-0.25, -0.96, 0.0)), width=0.052, height=0.054)
    _add_buckle(bm_hw, Vector((0.060, -0.144, 0.962)), Vector((0.25, -0.96, 0.0)), width=0.044, height=0.046)
    # Small hanging iron loop/ring on Right hip (-X) seen clearly in Front 3/4!
    ring_c = Vector((-0.175, -0.065, 0.895))
    config.tube_along_points(
        bm_hw,
        [ring_c + Vector((0.0, math.cos(2 * math.pi * k / 14) * 0.024, math.sin(2 * math.pi * k / 14) * 0.024)) for k in range(15)],
        radii=0.0042,
        radial_segs=6,
        cap_start=False,
        cap_end=False,
    )
    objs.append(config.finalize_bmesh(bm_hw, "Belts_Buckles_Hardware", "12_BELTS", mat_name="MAT_Brass_Aged", smooth=True))

    # 3. Hip & Front Pouches
    bm_p = bmesh.new()
    # Front-left small utility pouch
    _add_pouch(bm_p, Vector((0.088, -0.135, 0.970)), yaw_deg=-25.0, tilt_out=10.0, size=(0.072, 0.045, 0.078))
    # Right hip trailing satchel/pouch (-X side seen in Front 3/4)
    _add_pouch(bm_p, Vector((-0.200, -0.020, 0.880)), yaw_deg=85.0, tilt_out=-14.0, size=(0.115, 0.058, 0.135))
    # Prominent Rear-Left battered leather pouch (+X, +Y side seen in Rear 3/4 near left hand!)
    _add_pouch(bm_p, Vector((0.185, 0.115, 0.865)), yaw_deg=-135.0, tilt_out=14.0, size=(0.145, 0.062, 0.160))
    objs.append(config.finalize_bmesh(bm_p, "Belts_Leather_Pouches", "12_BELTS", mat_name="MAT_Leather_Brown", smooth=True))

    # 4. Diagonal Chest/Back Baldric Suspension Strap holding the Back Scabbard
    # Runs cleanly from upper-right shoulder (-0.19, Z=1.36) diagonally across torso/cape to lower-left hip (+0.23, Z=0.98)
    bm_bal = bmesh.new()
    # Back pass sits strictly OUTSIDE Cape_Back_Cloak (+Y = 0.235..0.262) so cape never clips through leather!
    bal_loop = [
        Vector((-0.205, 0.252, 1.385)),  # Back right shoulder top (meets scabbard locket)
        Vector((-0.055, 0.262, 1.245)),  # Mid back cleanly outside cape drape
        Vector((0.105, 0.250, 1.095)),   # Lower left back cleanly outside cape
        Vector((0.228, 0.145, 0.995)),   # Left hip rear (meets lower scabbard mount)
        Vector((0.194, -0.058, 1.010)),  # Left waist front
        Vector((0.120, -0.155, 1.090)),  # Lower-left rib curve
        Vector((0.000, -0.180, 1.185)),  # Across lower chest/ribs leaving upper heraldic cross clear
        Vector((-0.120, -0.158, 1.300)), # Up right rib toward shoulder
        Vector((-0.198, -0.058, 1.425)), # Right collarbone crest
        Vector((-0.210, 0.095, 1.445)),  # Over top right shoulder under scarf
    ]
    rings_bal = []
    n_pts = len(bal_loop)
    for idx in range(n_pts):
        p = bal_loop[idx]
        p_next = bal_loop[(idx + 1) % n_pts]
        p_prev = bal_loop[(idx - 1) % n_pts]
        tan = (p_next - p_prev).normalized()
        out = Vector((p.x, p.y, 0.0)).normalized()
        perp = tan.cross(out).normalized()
        if perp.length < 1e-4:
            perp = Vector((0.0, 0.0, 1.0))
        hw = 0.022
        ht = 0.008
        rings_bal.append([
            p - perp * hw,
            p - perp * hw + out * ht,
            p + perp * hw + out * ht,
            p + perp * hw,
        ])
    vert_bal = [[bm_bal.verts.new(v) for v in r] for r in rings_bal]
    for i in range(n_pts):
        inext = (i + 1) % n_pts
        for j in range(4):
            jnext = (j + 1) % 4
            bm_bal.faces.new((vert_bal[i][j], vert_bal[inext][j], vert_bal[inext][jnext], vert_bal[i][jnext]))

    objs.append(config.finalize_bmesh(bm_bal, "Belts_Chest_Baldric", "12_BELTS", mat_name="MAT_Leather_Dark", smooth=True))

    return objs


def build_equipment(detail: str = "MEDIUM") -> dict:
    """Build belts, buckles, pouches, rings, and diagonal baldric strap in 12_BELTS."""
    items = _build_belts_and_pouches()
    return {"belts": items}
