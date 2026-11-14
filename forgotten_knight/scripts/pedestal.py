"""Circular medieval cracked stone display pedestal with moss and creeping roots
for THE FORGOTTEN KNIGHT in collection 15_PEDESTAL (Section 19).
Top standing basin sits cleanly at Z = 0.000 so boots and longsword tip contact flush.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix
import config


def _build_main_plinth(segs: int) -> bpy.types.Object:
    """Stepped cylindrical medieval limestone pedestal with raised beveled outer rim,
    cracked top stone slabs, chipped edges, and shallow rainwater puddle depressions."""
    bm = bmesh.new()
    ped = config.PEDESTAL
    r_inner = ped["radius_top"]        # 0.80m standing basin edge
    r_rim = ped["radius_rim_outer"]    # 0.88m raised stone curb outer
    r_base = ped["radius_base"]        # 0.96m lower stepped plinth
    h_tot = ped["height"]              # 0.44m total thickness
    rng = config.seeded_rng(1501)

    # Radial fracture crack angles (6 main weathered stone seams)
    crack_angles = [0.22, 1.18, 2.35, 3.25, 4.42, 5.50]

    # Revolution cross section profile points from center floor -> rim -> lower base steps
    # (radius, z, chip_scale)
    profile = [
        (0.00, 0.000, 0.000),
        (0.22, -0.002, 0.001),
        (0.46, 0.000, 0.002),
        (0.70, 0.000, 0.002),
        (r_inner - 0.02, 0.002, 0.003),
        (r_inner + 0.02, ped["rim_z"], 0.005),      # Inner rim lip
        (r_rim - 0.015, ped["rim_z"] + 0.002, 0.008),
        (r_rim, ped["rim_z"] - 0.012, 0.010),       # Chipped outer rim bevel
        (r_rim + 0.005, -0.055, 0.007),             # Curb wall
        (r_rim - 0.025, -0.085, 0.004),             # Undercut groove
        (r_rim + 0.025, -0.140, 0.005),             # Middle cornice step
        (r_rim + 0.025, -0.220, 0.004),
        (r_base, -0.275, 0.005),                    # Lower flare chamfer
        (r_base, -h_tot, 0.003),                    # Bottom base skirt
    ]

    rings = []
    center_v = bm.verts.new(Vector((0.0, 0.0, 0.0)))

    for p_idx, (rad, z_base, chip_amp) in enumerate(profile[1:], start=1):
        ring = []
        for s in range(segs):
            ang = 2.0 * math.pi * s / segs
            # Chipped edge irregularity + radial fissure groove indentations
            chip = (
                math.sin(ang * 7.0 + p_idx) * 0.45
                + math.cos(ang * 13.0 - p_idx * 0.5) * 0.35
                + (rng.random() - 0.5) * 0.4
            ) * chip_amp

            # Carve real crack valleys along fracture angles across top disc & rim
            crack_drop = 0.0
            for ca in crack_angles:
                d_ang = abs((ang - ca + math.pi) % (2.0 * math.pi) - math.pi)
                if d_ang < 0.065 and z_base > -0.12:
                    crack_drop += (1.0 - d_ang / 0.065) * 0.014

            # Keep central standing region (0.14..0.52) within 2mm of Z=0.000 for crisp boot/sword contact
            in_boot_zone = rad < 0.55 and p_idx <= 3
            z_final = z_base + (chip * 0.25 if in_boot_zone else chip) - (crack_drop * (0.25 if in_boot_zone else 1.0))
            r_final = rad + chip * 0.65
            ring.append(bm.verts.new(Vector((math.cos(ang) * r_final, math.sin(ang) * r_final, z_final))))
        rings.append(ring)

    # Connect inner center triangle fan to first ring
    r0 = rings[0]
    for s in range(segs):
        s_next = (s + 1) % segs
        bm.faces.new((center_v, r0[s], r0[s_next]))

    # Connect consecutive rings
    for r_idx in range(len(rings) - 1):
        ra = rings[r_idx]
        rb = rings[r_idx + 1]
        for s in range(segs):
            s_next = (s + 1) % segs
            bm.faces.new((ra[s], rb[s], rb[s_next], ra[s_next]))

    # Close flat underside cap
    bot_c = bm.verts.new(Vector((0.0, 0.0, -h_tot)))
    rlast = rings[-1]
    for s in range(segs):
        s_next = (s + 1) % segs
        bm.faces.new((bot_c, rlast[s_next], rlast[s]))

    plinth = config.finalize_bmesh(bm, "Pedestal_Stone_Base", "15_PEDESTAL", mat_name="MAT_Stone_Weathered", smooth=True, box_uv_scale=0.8)
    return plinth


def _catmull_rom(pts, segs_per_span: int = 4):
    """Interpolate smooth organic S-curves through control points."""
    if len(pts) < 4:
        return pts
    res = []
    padded = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for s in range(segs_per_span):
            t = s / segs_per_span
            t2, t3 = t * t, t * t * t
            pt = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            res.append(pt)
    res.append(pts[-1])
    return res


def _pedestal_surface_z(r: float) -> float:
    """Approximate top height Z of pedestal curb & floor so creeping roots hug the stone cleanly."""
    r_inner = config.PEDESTAL["radius_top"]        # 0.80
    r_rim = config.PEDESTAL["radius_rim_outer"]    # 0.88
    rim_z = config.PEDESTAL["rim_z"]               # 0.036
    if r <= r_inner - 0.03:
        return 0.002
    if r <= r_inner + 0.02:
        t = (r - (r_inner - 0.03)) / 0.05
        return 0.002 + t * (rim_z - 0.002)
    if r <= r_rim - 0.01:
        return rim_z + 0.003
    if r <= r_rim + 0.02:
        t = (r - (r_rim - 0.01)) / 0.03
        return rim_z - t * 0.048
    return -0.045 - max(0.0, r - (r_rim + 0.02)) * 1.4


def _build_creeping_roots(root_count: int) -> bpy.types.Object:
    """Build organic winding gnarled root clusters draping OVER the pedestal curb lip and cracks."""
    bm = bmesh.new()
    rng = config.seeded_rng(1522)
    r_rim = config.PEDESTAL["radius_rim_outer"]

    # Group roots into 5 organic vine/root anchor clusters around perimeter instead of uniform spikes
    cluster_angles = [0.35, 1.42, 2.58, 3.82, 5.25]
    for i in range(root_count):
        c_ang = cluster_angles[i % len(cluster_angles)]
        base_ang = c_ang + (rng.random() - 0.5) * 0.55
        dir_sign = 1.0 if (i % 2 == 0) else -1.0
        ctrl = []
        ang_cur = base_ang
        # Crawl inward over the outer stone lip onto top rim & down onto floor slab (no clipping through wall!)
        r_start = r_rim + 0.028
        r_end = 0.52 + rng.random() * 0.14
        steps = 8
        for st in range(steps):
            t = st / (steps - 1)
            # Strong tangential winding along curb crest before descending onto floor
            tang_step = (0.16 if 0.15 < t < 0.65 else 0.09) * dir_sign
            ang_cur += tang_step + (rng.random() - 0.5) * 0.10
            r_cur = r_start - (t ** 1.15) * (r_start - r_end)
            rad_here = 0.011 * (1.0 - 0.80 * t)
            z_cur = _pedestal_surface_z(r_cur) + rad_here * 0.55 + math.sin(t * 7.5 + i) * 0.0025
            ctrl.append(Vector((math.cos(ang_cur) * r_cur, math.sin(ang_cur) * r_cur, z_cur)))

        smooth_pts = _catmull_rom(ctrl, segs_per_span=4)
        n_s = len(smooth_pts)
        rads = [0.011 * (1.0 - 0.82 * (k / max(1, n_s - 1))) for k in range(n_s)]
        config.tube_along_points(bm, smooth_pts, rads, radial_segs=7, cap_start=True, cap_end=True)

        # Winding secondary branch crawling along curb crest or inward toward flagstones
        if i % 2 == 0 and len(ctrl) >= 6:
            branch_idx = 3
            p_start = ctrl[branch_idx]
            b_ctrl = [p_start]
            b_ang = math.atan2(p_start.y, p_start.x)
            b_r = p_start.xy.length
            for k in range(1, 5):
                tk = k / 4.0
                b_ang += (-dir_sign) * 0.15 + (rng.random() - 0.5) * 0.12
                b_r = max(0.48, b_r - 0.048)
                rad_b = 0.0065 * (1.0 - 0.78 * tk)
                b_ctrl.append(Vector((math.cos(b_ang) * b_r, math.sin(b_ang) * b_r, _pedestal_surface_z(b_r) + rad_b * 0.5)))
            bsm = _catmull_rom(b_ctrl, segs_per_span=3)
            rads_b = [0.0065 * (1.0 - 0.82 * (k / max(1, len(bsm) - 1))) for k in range(len(bsm))]
            config.tube_along_points(bm, bsm, rads_b, radial_segs=6)

    return config.finalize_bmesh(bm, "Pedestal_Creeping_Roots", "15_PEDESTAL", mat_name="MAT_Dirt", smooth=True, box_uv_scale=2.5)


def _build_moss_patches(detail: str) -> bpy.types.Object:
    """Organic irregular low moss cushions tucked along outer rim shelf & slab cracks."""
    bm = bmesh.new()
    rng = config.seeded_rng(1544)
    count = {"LOW": 18, "MEDIUM": 32, "HIGH": 46}[detail]
    r_inner = config.PEDESTAL["radius_top"]

    for i in range(count):
        ang = rng.random() * math.pi * 2.0
        r = r_inner - 0.02 + (rng.random() - 0.35) * 0.12
        pos = Vector((math.cos(ang) * r, math.sin(ang) * r, 0.024 if r > r_inner - 0.015 else 0.002))
        rad = 0.022 + rng.random() * 0.032
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rad)
        for v in res["verts"]:
            nudge = 0.78 + rng.random() * 0.45
            v.co.x *= (1.2 + rng.random() * 0.4) * nudge
            v.co.y *= (1.0 + rng.random() * 0.4) * nudge
            v.co.z *= 0.14 + rng.random() * 0.08
            v.co += pos
    bm.normal_update()
    return config.finalize_bmesh(bm, "Pedestal_Moss_Tufts", "15_PEDESTAL", mat_name="MAT_Moss", smooth=True)


def build_pedestal(detail: str = "MEDIUM") -> dict:
    """Build cracked mossy circular medieval stone pedestal in 15_PEDESTAL."""
    ds = config.DETAIL_SETTINGS[detail]
    plinth = _build_main_plinth(ds["pedestal_segs"])
    roots = _build_creeping_roots(ds["root_count"])
    moss = _build_moss_patches(detail)
    return {"plinth": plinth, "roots": roots, "moss": moss}
