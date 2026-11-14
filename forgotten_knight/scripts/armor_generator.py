"""Layered medieval plate armor & articulated gauntlet/boot generator
for THE FORGOTTEN KNIGHT.
Builds asymmetric torso cuirass, heraldry cross, tassets, pauldrons with brass rims
and overlapping lames, winged couters, vambraces, fingered gauntlets, thigh cuisses,
knee poleyns, greaves with leather rear straps, and grounded armored boots.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix
import config


def _build_cuirass(segs: int) -> list:
    """Build articulated steel breastplate, backplate, waist fauld, and chest cross."""
    objs = []
    # Main torso cuirass tube sculpted cleanly over upper torso (Z=1.07..1.44)
    bm = bmesh.new()
    slices = [
        # (z, rx, ry_fwd, ry_back, y_off, keel_fwd)
        (1.06, 0.162, 0.114, 0.106, 0.000, 0.005),  # Waist base
        (1.14, 0.174, 0.128, 0.116, -0.005, 0.012), # Lower rib
        (1.25, 0.200, 0.146, 0.128, -0.010, 0.018), # Chest globose bulge
        (1.36, 0.214, 0.140, 0.124, -0.012, 0.014), # Upper pectorals
        (1.43, 0.186, 0.112, 0.108, -0.010, 0.004), # Neck collar bevel
    ]
    rings = []
    for z, rx, ryf, ryb, y_off, keel in slices:
        ring = []
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ca = math.cos(a)
            sa = math.sin(a)
            x = ca * rx
            ry = ryf if sa < 0.0 else ryb
            y = y_off + sa * ry
            if sa < 0.0:
                y -= keel * max(0.0, 1.0 - abs(ca) * 2.6)
            ring.append(Vector((x, y, z)))
        rings.append(ring)

    config.loft_rings(bm, rings, close_cap_start=False, close_cap_end=False)
    cuirass = config.finalize_bmesh(bm, "Armor_Cuirass", "05_TORSO_ARMOR", mat_name="MAT_Steel_Oxidized", smooth=True)
    config.add_solidify(cuirass, thickness=0.0055, offset=1.0)
    objs.append(cuirass)

    # Subtle weathered tarnished brass cross pattée flush onto exposed chest cuirass beside scarf
    bm_h = bmesh.new()
    for diag in (1.0, -1.0):
        pts = []
        widths = []
        for k in range(7):
            t = k / 6.0 * 2.0 - 1.0
            x = 0.048 + t * 0.042
            z = 1.280 + diag * t * 0.044
            y_surf = -0.010 - 0.145 * math.sqrt(max(0.15, 1.0 - (x / 0.210) ** 2)) - 0.016 * max(0.0, 1.0 - abs(x) / 0.08)
            pts.append(Vector((x, y_surf - 0.0075, z)))
            widths.append(0.0075 + 0.0055 * (abs(t) ** 1.4))
        r_pts = []
        for idx, p in enumerate(pts):
            tan = (pts[min(len(pts)-1, idx+1)] - pts[max(0, idx-1)]).normalized()
            side = tan.cross(Vector((0.0, -1.0, 0.0))).normalized() * widths[idx]
            fwd = Vector((0.0, -0.0038, 0.0))
            r_pts.append([p - side, p - side + fwd, p + side + fwd, p + side])
        config.loft_rings(bm_h, r_pts, close_cap_start=True, close_cap_end=True)

    heraldry = config.finalize_bmesh(bm_h, "Armor_Chest_Heraldry", "05_TORSO_ARMOR", mat_name="MAT_Brass_Aged", smooth=True)
    objs.append(heraldry)

    # Segmented waist fauld lames (Z=1.06 -> 0.94)
    for idx, (z0, z1, r_scale) in enumerate([(1.06, 0.99, 1.02), (1.00, 0.93, 1.07)]):
        p0 = Vector((0.0, 0.00, z0))
        p1 = Vector((0.0, -0.01, z1))
        fauld = config.create_curved_plate_patch(
            f"Armor_Fauld_{idx+1}", "05_TORSO_ARMOR",
            [p0, p1], [0.165 * r_scale, 0.175 * r_scale], [2.45, 2.55],
            radial_steps=14, thickness=0.004, mat_name="MAT_Steel_Dark", subdiv=1,
        )
        objs.append(fauld)

    # Hip Tassets (prominently visible on Left +X under belts, plus symmetrical Right -X)
    for side in ("L", "R"):
        s = 1.0 if side == "L" else -1.0
        bm_t = bmesh.new()
        bm_trim = bmesh.new()
        rows_u = 5
        rows_v = 7
        grid = []
        for iu in range(rows_u):
            tu = iu / (rows_u - 1)
            z = 0.96 - tu * 0.22  # 0.96 down to 0.74
            half_arc = 0.72 * (1.0 - tu * 0.22)
            row = []
            for iv in range(rows_v):
                tv = iv / (rows_v - 1) * 2.0 - 1.0
                # Center angle wraps front-lateral hip around +/-48 deg from -Y
                center_ang = s * 0.78
                ang = center_ang + tv * half_arc
                rx = 0.175 + tu * 0.032
                ry = 0.132 + tu * 0.024
                x = math.sin(ang) * rx
                y = -math.cos(ang) * ry - 0.005
                # Slight ridged flute down middle of tasset
                flute = 0.006 * max(0.0, 1.0 - abs(tv) * 2.0)
                pt = Vector((x + s * flute * 0.5, y - flute, z))
                row.append(bm_t.verts.new(pt))
            grid.append(row)
        for iu in range(rows_u - 1):
            for iv in range(rows_v - 1):
                bm_t.faces.new((grid[iu][iv], grid[iu][iv+1], grid[iu+1][iv+1], grid[iu+1][iv]))

        # Copy lower border coordinates BEFORE finalize_bmesh frees bm_t
        pts_trim = [grid[-1][iv].co.copy() + Vector((s * 0.003, -0.004, 0.0)) for iv in range(rows_v)]
        tasset = config.finalize_bmesh(bm_t, f"Armor_Tasset_{side}", "05_TORSO_ARMOR", mat_name="MAT_Steel_Worn", smooth=True)
        config.add_solidify(tasset, thickness=0.0045, offset=1.0)
        objs.append(tasset)

        # Aged brass lower border edge trim on tasset
        config.tube_along_points(bm_trim, pts_trim, radii=0.0055, radial_segs=8)
        trim_obj = config.finalize_bmesh(bm_trim, f"Armor_Tasset_Trim_{side}", "05_TORSO_ARMOR", mat_name="MAT_Brass_Aged", smooth=True)
        objs.append(trim_obj)

    return objs


def _orient_from_segment(p0: Vector, p1: Vector, fwd_hint: Vector = Vector((0.0, -1.0, 0.0))) -> Matrix:
    """Create right-handed orthonormal 4x4 transform matrix: +Z=up along p1->p0, +X=Left(+X), -Y=Front(-Y)."""
    z_axis = (p0 - p1).normalized()  # Up along bone
    if abs(z_axis.dot(fwd_hint)) > 0.94:
        fwd_hint = Vector((1.0, 0.0, 0.0))
    x_axis = z_axis.cross(fwd_hint).normalized()
    y_axis = z_axis.cross(x_axis).normalized()
    mat = Matrix((
        (x_axis.x, y_axis.x, z_axis.x, p0.x),
        (x_axis.y, y_axis.y, z_axis.y, p0.y),
        (x_axis.z, y_axis.z, z_axis.z, p0.z),
        (0.0,      0.0,      0.0,      1.0),
    ))
    return mat


def _build_joint_cop_plate(name: str, collection: str, center: Vector,
                           fwd_dir: Vector, side_sign: float,
                           radius: float = 0.056, height: float = 0.088,
                           wing_extend: float = 0.030, mat_name: str = "MAT_Steel_Worn") -> bpy.types.Object:
    """Build articulated Gothic elbow couter or knee poleyn shield with sculpted wing fin & median ridge."""
    bm = bmesh.new()
    rows_u, rows_v = 9, 13
    fwd = fwd_dir.normalized()
    up = Vector((0.0, 0.0, 1.0))
    out_side = Vector((side_sign, 0.0, 0.0))
    # Ensure orthogonal tangent basis around joint exterior
    side_axis = up.cross(fwd).normalized()
    if side_axis.dot(out_side) < 0.0:
        side_axis = -side_axis

    grid = []
    for iu in range(rows_u):
        tu = iu / (rows_u - 1)  # 0 top lame -> 1 bottom lame
        pitch = (tu - 0.5) * 1.65
        row = []
        for iv in range(rows_v):
            tv = iv / (rows_v - 1) * 2.0 - 1.0  # -1 inner -> +1 outer wing
            az = tv * 1.42
            # Sculpted almond-shaped shell pinching slightly inward at upper/lower articulated borders
            pinch_u = 1.0 - 0.16 * (abs(tu - 0.5) * 2.0) ** 1.6
            wing = wing_extend * max(0.0, tv - 0.18) ** 1.2 * math.sin(tu * math.pi)
            keel = 0.011 * max(0.0, 1.0 - abs(tv) * 3.0) * math.sin(tu * math.pi)
            local_f = (math.cos(pitch) * math.cos(az) * radius * pinch_u + keel)
            local_s = (math.sin(az) * (radius * 1.04 * pinch_u) + wing)
            local_z = -math.sin(pitch) * (height * 0.52)
            pt = center + fwd * local_f + side_axis * local_s + up * local_z
            row.append(bm.verts.new(pt))
        grid.append(row)

    for iu in range(rows_u - 1):
        for iv in range(rows_v - 1):
            bm.faces.new((grid[iu][iv], grid[iu][iv + 1], grid[iu + 1][iv + 1], grid[iu + 1][iv]))

    obj = config.finalize_bmesh(bm, name, collection, mat_name=mat_name, smooth=True)
    config.add_solidify(obj, thickness=0.0038, offset=1.0)
    return obj


def _build_left_hero_arm() -> list:
    """Build large asymmetric multi-plate Left (+X) pauldron seating flush over shoulder lames,
    4 shoulder lames, winged gothic couter, and vambrace with brass wrist band."""
    objs = []
    j = config.JOINTS
    sh = j["shoulder_L"]
    el = j["elbow_L"]
    wr = j["wrist_L"]

    # 1. Hero Left Pauldron Dome seated tightly onto deltoid & cuirass collar (zero floating gap)
    bm = bmesh.new()
    bm_brass = bmesh.new()
    rivet_pts = []
    rows_u = 12
    rows_v = 16
    grid = []
    dome_center = sh + Vector((-0.036, -0.004, -0.034))
    for iu in range(rows_u):
        tu = iu / (rows_u - 1)  # 0 inner collar haute-piece near cuirass -> 1 lower outer rim over first lame
        polar = -0.08 + tu * 1.98
        row = []
        for iv in range(rows_v):
            tv = iv / (rows_v - 1) * 2.0 - 1.0  # -1 front -> +1 rear
            az = tv * 1.56
            haute = 0.018 * max(0.0, 1.0 - tu * 4.2) * max(0.25, math.cos(tv * 0.95))
            skirt_flare = 1.0 + 0.12 * max(0.0, tu - 0.55) / 0.45
            rad_x = 0.130 * skirt_flare
            rad_y = (0.122 if tu > 0.20 else 0.106) * skirt_flare
            rad_z = 0.094
            local_x = math.sin(polar) * math.cos(az * 0.38) * rad_x
            local_y = math.sin(az) * rad_y
            local_z = math.cos(polar) * rad_z + haute
            ridge = 0.007 * max(0.0, 1.0 - abs(tv) * 3.2) * math.sin(tu * math.pi)
            pt = dome_center + Vector((local_x + ridge, local_y, local_z))
            row.append(bm.verts.new(pt))
            if iu == rows_u - 1 and iv % 2 == 1:
                rivet_pts.append((pt + Vector((0.003, 0.0, 0.002)), Vector((1.0, math.sin(az) * 0.5, 0.05)).normalized()))
        grid.append(row)

    for iu in range(rows_u - 1):
        for iv in range(rows_v - 1):
            bm.faces.new((grid[iu][iv], grid[iu][iv+1], grid[iu+1][iv+1], grid[iu+1][iv]))

    # Aged brass edging flush along pauldron borders
    top_edge = [grid[0][iv].co.copy() + Vector((0.001, 0.0, 0.002)) for iv in range(rows_v)]
    bot_edge = [grid[-1][iv].co.copy() + Vector((0.002, 0.0, -0.001)) for iv in range(rows_v)]
    mid_scroll = [grid[rows_u - 3][iv].co.copy() + Vector((0.003, 0.0, 0.001)) for iv in range(2, rows_v - 2)]
    config.tube_along_points(bm_brass, top_edge, radii=0.0046, radial_segs=8)
    config.tube_along_points(bm_brass, bot_edge, radii=0.0040, radial_segs=8)
    config.tube_along_points(bm_brass, mid_scroll, radii=0.0028, radial_segs=6)

    pauldron = config.finalize_bmesh(bm, "Armor_Pauldron_L", "06_ARM_ARMOR", mat_name="MAT_Steel_Worn", smooth=True)
    config.add_solidify(pauldron, thickness=0.0045, offset=1.0)
    objs.append(pauldron)
    objs.append(config.finalize_bmesh(bm_brass, "Armor_Pauldron_Rim_L", "06_ARM_ARMOR", mat_name="MAT_Brass_Aged", smooth=True))

    # 2. Four overlapping articulated shoulder/bicep lames tucking flush UP inside pauldron skirt
    bm_lames = bmesh.new()
    for l_idx in range(4):
        t0 = -0.02 + l_idx * 0.132
        t1 = t0 + 0.118
        c0 = sh.lerp(el, t0)
        c1 = sh.lerp(el, t1)
        bm_sub_grid = []
        for iz, c_pt in enumerate((c0, c1)):
            rad = 0.080 - l_idx * 0.005 - iz * 0.003
            row = []
            for iv in range(11):
                tv = iv / 10.0 * 2.0 - 1.0
                ang = tv * 1.56
                x = c_pt.x + math.cos(ang) * rad * 0.86 + (0.005 if iz == 1 else 0.0)
                y = c_pt.y + math.sin(ang) * rad
                row.append(bm_lames.verts.new(Vector((x, y, c_pt.z))))
            bm_sub_grid.append(row)
        for iv in range(10):
            bm_lames.faces.new((bm_sub_grid[0][iv], bm_sub_grid[0][iv+1], bm_sub_grid[1][iv+1], bm_sub_grid[1][iv]))
        rivet_pts.append((Vector(bm_sub_grid[0][1].co) + Vector((0.005, -0.004, 0.0)), Vector((0.7, -0.7, 0.0))))
        rivet_pts.append((Vector(bm_sub_grid[0][-2].co) + Vector((0.005, 0.004, 0.0)), Vector((0.7, 0.7, 0.0))))

    lames_obj = config.finalize_bmesh(bm_lames, "Armor_ShoulderLames_L", "06_ARM_ARMOR", mat_name="MAT_Steel_Oxidized", smooth=True)
    config.add_solidify(lames_obj, thickness=0.0038, offset=1.0)
    objs.append(lames_obj)
    objs.append(config.add_rivet_strip("Armor_Rivets_Arm_L", "06_ARM_ARMOR", rivet_pts, radius=0.0038, mat_name="MAT_Brass_Aged"))

    # 3. Winged Gothic elbow couter (Couter_L)
    objs.append(_build_joint_cop_plate(
        "Armor_Couter_L",
        "06_ARM_ARMOR",
        center=el + Vector((0.010, 0.010, 0.0)),
        fwd_dir=Vector((0.68, 0.72, 0.0)),
        side_sign=1.0,
        radius=0.056,
        height=0.094,
        wing_extend=0.032,
        mat_name="MAT_Steel_Worn",
    ))

    # 4. Forearm Vambrace + Brass Wrist Band (Vambrace_L)
    arm_len = (el - wr).length
    mat_fa = _orient_from_segment(el, wr)
    bm_v = bmesh.new()
    rings = []
    for k, (frac, rx, ry) in enumerate([(0.16, 0.064, 0.062), (0.48, 0.056, 0.054), (0.86, 0.045, 0.044)]):
        z_local = -frac * arm_len
        ring = []
        for i in range(12):
            a = 2.0 * math.pi * i / 12
            p_local = Vector((math.cos(a) * rx, math.sin(a) * ry, z_local))
            ring.append(mat_fa @ p_local)
        rings.append(ring)
    config.loft_rings(bm_v, rings, close_cap_start=False, close_cap_end=False)
    vamb_l = config.finalize_bmesh(bm_v, "Armor_Vambrace_L", "06_ARM_ARMOR", mat_name="MAT_Steel_Oxidized", smooth=True)
    config.add_solidify(vamb_l, thickness=0.004, offset=1.0)
    objs.append(vamb_l)

    # Brass wrist collar ring matching Left forearm highlight in reference
    bm_cb = bmesh.new()
    cuff_pts = [mat_fa @ Vector((math.cos(2 * math.pi * i / 14) * 0.048, math.sin(2 * math.pi * i / 14) * 0.047, -0.84 * arm_len)) for i in range(15)]
    config.tube_along_points(bm_cb, cuff_pts, radii=0.006, radial_segs=8, cap_start=False, cap_end=False)
    objs.append(config.finalize_bmesh(bm_cb, "Armor_Cuff_Brass_L", "06_ARM_ARMOR", mat_name="MAT_Brass_Aged", smooth=True))

    return objs


def _build_right_sword_arm() -> list:
    """Build Right (-X) upper arm lames (emerging from under green scarf), couter, and vambrace."""
    objs = []
    j = config.JOINTS
    sh = j["shoulder_R"]
    el = j["elbow_R"]
    wr = j["wrist_R"]

    # Compact rounded shoulder dome tucked cleanly underneath right hanging cowl scarf
    bm_pr = bmesh.new()
    grid_pr = []
    dome_r_c = sh + Vector((0.020, 0.0, -0.022))
    for iu in range(7):
        tu = iu / 6.0
        polar = -0.10 + tu * 1.72
        row = []
        for iv in range(9):
            tv = iv / 8.0 * 2.0 - 1.0
            az = tv * 1.32
            r_s = 0.088
            pt = dome_r_c + Vector((-math.sin(polar) * math.cos(az * 0.35) * r_s, math.sin(az) * 0.088, math.cos(polar) * r_s * 0.85))
            row.append(bm_pr.verts.new(pt))
        grid_pr.append(row)
    for iu in range(6):
        for iv in range(8):
            bm_pr.faces.new((grid_pr[iu][iv], grid_pr[iu][iv+1], grid_pr[iu+1][iv+1], grid_pr[iu+1][iv]))
    pdr_r = config.finalize_bmesh(bm_pr, "Armor_Pauldron_R", "06_ARM_ARMOR", mat_name="MAT_Steel_Oxidized", smooth=True)
    config.add_solidify(pdr_r, thickness=0.004, offset=1.0)
    objs.append(pdr_r)

    # Smaller upper-arm lames tucked neatly inside Right pauldron
    bm_lames = bmesh.new()
    for l_idx in range(3):
        t0 = 0.08 + l_idx * 0.16
        t1 = t0 + 0.125
        c0 = sh.lerp(el, t0)
        c1 = sh.lerp(el, t1)
        sub_grid = []
        for iz, c_pt in enumerate((c0, c1)):
            rad = 0.078 - l_idx * 0.006 - iz * 0.003
            row = []
            for iv in range(9):
                tv = iv / 8.0 * 2.0 - 1.0
                ang = tv * 1.38
                x = c_pt.x - math.cos(ang) * rad * 0.90 - (0.006 if iz == 1 else 0.0)
                y = c_pt.y + math.sin(ang) * rad
                row.append(bm_lames.verts.new(Vector((x, y, c_pt.z))))
            sub_grid.append(row)
        for iv in range(8):
            bm_lames.faces.new((sub_grid[0][iv], sub_grid[0][iv+1], sub_grid[1][iv+1], sub_grid[1][iv]))
    lames_r = config.finalize_bmesh(bm_lames, "Armor_ShoulderLames_R", "06_ARM_ARMOR", mat_name="MAT_Steel_Oxidized", smooth=True)
    config.add_solidify(lames_r, thickness=0.0038, offset=1.0)
    objs.append(lames_r)

    # Right elbow couter (articulated winged plate)
    objs.append(_build_joint_cop_plate(
        "Armor_Couter_R",
        "06_ARM_ARMOR",
        center=el + Vector((-0.008, 0.008, 0.0)),
        fwd_dir=Vector((-0.68, 0.72, 0.0)),
        side_sign=-1.0,
        radius=0.052,
        height=0.088,
        wing_extend=0.026,
        mat_name="MAT_Steel_Worn",
    ))

    # Right vambrace along elbow->wrist (with wrist brass accent strip)
    arm_len = (el - wr).length
    mat_fa = _orient_from_segment(el, wr)
    bm_v = bmesh.new()
    rings = []
    for frac, rx, ry in [(0.16, 0.060, 0.058), (0.50, 0.054, 0.052), (0.88, 0.044, 0.042)]:
        zl = -frac * arm_len
        rings.append([mat_fa @ Vector((math.cos(2 * math.pi * i / 12) * rx, math.sin(2 * math.pi * i / 12) * ry, zl)) for i in range(12)])
    config.loft_rings(bm_v, rings, close_cap_start=False, close_cap_end=False)
    vamb_r = config.finalize_bmesh(bm_v, "Armor_Vambrace_R", "06_ARM_ARMOR", mat_name="MAT_Steel_Worn", smooth=True)
    config.add_solidify(vamb_r, thickness=0.004, offset=1.0)
    objs.append(vamb_r)

    bm_cb = bmesh.new()
    cuff_pts = [mat_fa @ Vector((math.cos(2 * math.pi * i / 14) * 0.046, math.sin(2 * math.pi * i / 14) * 0.045, -0.84 * arm_len)) for i in range(15)]
    config.tube_along_points(bm_cb, cuff_pts, radii=0.0055, radial_segs=8, cap_start=False, cap_end=False)
    objs.append(config.finalize_bmesh(bm_cb, "Armor_Cuff_Brass_R", "06_ARM_ARMOR", mat_name="MAT_Brass_Aged", smooth=True))

    return objs


def _build_gauntlets() -> list:
    """Build articulated multi-finger steel gauntlets in 07_HANDS wrapping sword grip (R) and relaxed (L)."""
    objs = []
    j = config.JOINTS

    # RIGHT GAUNTLET wrapping vertical longsword handle cleanly
    wr_r, hd_r = j["wrist_R"], j["hand_R"]
    grip = config.SWORD_MAIN["grip_center"]
    bm_gr = bmesh.new()
    # Flared cuff + arched metacarpal dorsal plate
    cuff_pts = [
        wr_r + Vector((-0.025, 0.015, 0.042)),
        wr_r + Vector((-0.012, -0.005, 0.010)),
        hd_r + Vector((-0.014, -0.018, -0.005)),
    ]
    config.tube_along_points(bm_gr, cuff_pts, [0.050, 0.046, 0.044], radial_segs=10, elliptical=(0.82, 1.0))
    # Individual segmented armored finger tubes curled tightly around leather grip
    for f_idx, dz in enumerate((-0.024, -0.008, 0.008, 0.024)):
        k = hd_r + Vector((-0.002, -0.018, dz))
        m = Vector((grip.x - 0.022, grip.y - 0.018, grip.z + dz))
        e = Vector((grip.x + 0.002, grip.y - 0.024, grip.z + dz))
        t = Vector((grip.x + 0.020, grip.y - 0.006, grip.z + dz))
        config.tube_along_points(bm_gr, [k, m, e, t], [0.0115, 0.0110, 0.010, 0.0085], radial_segs=8)
    # Thumb locking over top index knuckle
    config.tube_along_points(
        bm_gr,
        [hd_r + Vector((0.012, -0.020, 0.032)), grip + Vector((0.020, -0.016, 0.040)), grip + Vector((-0.004, -0.024, 0.034))],
        [0.0125, 0.011, 0.0095],
        radial_segs=8,
    )
    objs.append(config.finalize_bmesh(bm_gr, "Armor_Gauntlet_R", "07_HANDS", mat_name="MAT_Steel_Worn", smooth=True))

    # LEFT GAUNTLET relaxed beside hip/lantern
    wr_l, hd_l = j["wrist_L"], j["hand_L"]
    bm_gl = bmesh.new()
    config.tube_along_points(
        bm_gl,
        [wr_l + Vector((0.006, 0.010, 0.040)), wr_l, hd_l + Vector((0.006, -0.004, 0.002))],
        [0.048, 0.044, 0.042],
        radial_segs=10,
        elliptical=(0.75, 1.05),
    )
    for f_idx in range(4):
        oy = -0.026 + f_idx * 0.017
        flen = 0.075 - abs(f_idx - 1.2) * 0.010
        k = hd_l + Vector((0.010, oy, -0.012))
        m = k + Vector((-0.008, oy * 0.1, -flen * 0.55))
        t = m + Vector((-0.024, oy * 0.1, -flen * 0.45))
        config.tube_along_points(bm_gl, [k, m, t], [0.011, 0.010, 0.008], radial_segs=8)
    tk = hd_l + Vector((0.006, -0.038, 0.008))
    tm = tk + Vector((-0.014, -0.014, -0.028))
    tt = tm + Vector((-0.014, -0.004, -0.022))
    config.tube_along_points(bm_gl, [tk, tm, tt], [0.012, 0.0105, 0.0085], radial_segs=8)
    objs.append(config.finalize_bmesh(bm_gl, "Armor_Gauntlet_L", "07_HANDS", mat_name="MAT_Steel_Worn", smooth=True))

    return objs


def _build_leg_armor(segs: int) -> list:
    """Build thigh cuisses, winged knee poleyns, greaves with rear leather calf straps,
    and grounded layered steel/leather boots (Z >= 0.0)."""
    objs = []
    j = config.JOINTS

    for side in ("R", "L"):
        s = -1.0 if side == "R" else 1.0
        hip = j[f"hip_{side}"]
        knee = j[f"knee_{side}"]
        ankle = j[f"ankle_{side}"]
        ball = j[f"foot_ball_{side}"]
        toe = j[f"foot_toe_{side}"]

        # 1. Thigh Cuisse (sleek steel plate tucked neatly behind tabard/tassets, clear of left wrist)
        mat_th = _orient_from_segment(hip, knee)
        th_len = (hip - knee).length
        bm_q = bmesh.new()
        rings_q = []
        for frac, rx, ry in [(0.22, 0.080, 0.084), (0.52, 0.074, 0.078), (0.86, 0.066, 0.070)]:
            zl = -frac * th_len
            row = []
            for iv in range(9):
                tv = iv / 8.0 * 2.0 - 1.0
                ang = tv * 1.24 - math.pi * 0.5  # Centered smoothly on front (-Y)
                row.append(mat_th @ Vector((math.cos(ang) * rx, math.sin(ang) * ry, zl)))
            rings_q.append(row)
        config.loft_rings(bm_q, rings_q, close_cap_start=False, close_cap_end=False)
        cuisse = config.finalize_bmesh(bm_q, f"Armor_Cuisse_{side}", "11_LEG_ARMOR", mat_name="MAT_Steel_Oxidized", smooth=True)
        config.add_solidify(cuisse, thickness=0.004, offset=1.0)
        objs.append(cuisse)

        # 2. Knee Poleyn (articulated fluted Gothic knee cop with outer wing fin)
        objs.append(_build_joint_cop_plate(
            f"Armor_Poleyn_{side}",
            "11_LEG_ARMOR",
            center=knee + Vector((0.0, -0.012, 0.0)),
            fwd_dir=Vector((s * 0.14, -0.99, 0.0)),
            side_sign=s,
            radius=0.054,
            height=0.104,
            wing_extend=0.024,
            mat_name="MAT_Steel_Oxidized",
        ))

        # 3. Front Steel Greave flaring gently OVER boot ankle cuff + Rear Leather Calf Guard & Straps
        sh_len = (knee - ankle).length
        mat_sh = _orient_from_segment(knee, ankle)
        bm_g = bmesh.new()
        rings_g = []
        for frac, rx, ry, ridge in [(0.08, 0.068, 0.072, 0.008), (0.48, 0.064, 0.068, 0.009), (0.86, 0.056, 0.060, 0.006), (1.03, 0.060, 0.065, 0.005)]:
            zl = -frac * sh_len
            row = []
            for iv in range(11):
                tv = iv / 10.0 * 2.0 - 1.0
                ang = tv * 1.54 - math.pi * 0.5
                flute = ridge * max(0.0, 1.0 - abs(tv) * 2.6)
                row.append(mat_sh @ Vector((math.cos(ang) * rx, math.sin(ang) * ry - flute, zl)))
            rings_g.append(row)
        config.loft_rings(bm_g, rings_g, close_cap_start=False, close_cap_end=False)
        greave = config.finalize_bmesh(bm_g, f"Armor_Greave_Front_{side}", "11_LEG_ARMOR", mat_name="MAT_Steel_Worn", smooth=True)
        config.add_solidify(greave, thickness=0.004, offset=1.0)
        objs.append(greave)

        # Brass collar below knee matching Front 3/4 reference
        bm_gb = bmesh.new()
        gb_pts = [mat_sh @ Vector((math.cos(tv * 1.4 - math.pi * 0.5) * 0.070, math.sin(tv * 1.4 - math.pi * 0.5) * 0.076 - 0.006 * max(0.0, 1.0 - abs(tv) * 2.5), -0.13 * sh_len))
                  for tv in [k / 8.0 * 2.0 - 1.0 for k in range(9)]]
        config.tube_along_points(bm_gb, gb_pts, radii=0.0050, radial_segs=8)
        objs.append(config.finalize_bmesh(bm_gb, f"Armor_Greave_Trim_{side}", "11_LEG_ARMOR", mat_name="MAT_Brass_Aged", smooth=True))

        # Rear leather calf sleeve + 2 horizontal brown straps extending snugly into boot top
        bm_lc = bmesh.new()
        rings_lc = []
        for frac, rx, ry in [(0.12, 0.064, 0.068), (0.48, 0.061, 0.065), (0.98, 0.054, 0.057)]:
            zl = -frac * sh_len
            row = [mat_sh @ Vector((math.cos(a) * rx, math.sin(a) * ry, zl)) for a in [math.pi * 2.0 * i / 14 for i in range(14)]]
            rings_lc.append(row)
        config.loft_rings(bm_lc, rings_lc, close_cap_start=False, close_cap_end=False)
        objs.append(config.finalize_bmesh(bm_lc, f"Armor_Greave_Leather_{side}", "11_LEG_ARMOR", mat_name="MAT_Leather_Dark", smooth=True))

        bm_st = bmesh.new()
        for frac, rx, ry in [(0.26, 0.067, 0.071), (0.64, 0.060, 0.064)]:
            zl = -frac * sh_len
            s_pts = [mat_sh @ Vector((math.cos(a) * rx, math.sin(a) * ry, zl)) for a in [math.pi * 2.0 * i / 16 for i in range(17)]]
            config.tube_along_points(bm_st, s_pts, radii=0.0065, radial_segs=8, cap_start=False, cap_end=False)
        objs.append(config.finalize_bmesh(bm_st, f"Armor_Calf_Straps_{side}", "11_LEG_ARMOR", mat_name="MAT_Leather_Brown", smooth=True))

        # 4. Grounded Medieval Armored Boot (flat sole strictly at Z = 0.000, tall cuff tucked seamlessly under greave)
        bm_b = bmesh.new()
        foot_dir = Vector((toe.x - ankle.x, toe.y - ankle.y, 0.0)).normalized()
        foot_side = foot_dir.cross(Vector((0.0, 0.0, 1.0))).normalized()
        heel = Vector((ankle.x, ankle.y, 0.0)) - foot_dir * 0.050
        boot_len = (Vector((toe.x, toe.y, 0.0)) - heel).length + 0.024
        b_profiles = [
            (0.00, 0.050, 0.115),
            (0.24, 0.056, 0.118),  # Tall cuff extending cleanly inside flared front greave
            (0.55, 0.058, 0.072),  # Instep
            (0.80, 0.056, 0.048),  # Ball
            (0.95, 0.040, 0.030),  # Toe cap
            (1.00, 0.018, 0.016),  # Toe tip
        ]
        rings_b = []
        for frac, hw, hh in b_profiles:
            base_c = heel + foot_dir * (frac * boot_len)
            ring = []
            for iv in range(14):
                a = 2.0 * math.pi * iv / 14
                lx = math.cos(a) * hw
                lz = math.sin(a) * hh * 0.5 + hh * 0.5
                if lz < 0.008:
                    lz = 0.0  # Flat planted sole bottom strictly at Z=0.000
                ring.append(base_c + foot_side * lx + Vector((0.0, 0.0, lz)))
            rings_b.append(ring)
        config.loft_rings(bm_b, rings_b, close_cap_start=True, close_cap_end=True)
        objs.append(config.finalize_bmesh(bm_b, f"Armor_Boot_{side}", "11_LEG_ARMOR", mat_name="MAT_Leather_Dark", smooth=True))

        # Sculpted overlapping laminar sabaton plates arched flush across boot instep & toe cap
        bm_sab = bmesh.new()
        for f0, f1, h0, h1 in [(0.36, 0.52, 0.078, 0.068), (0.50, 0.68, 0.068, 0.054), (0.66, 0.85, 0.054, 0.038)]:
            r_sab = []
            for ff, hh_arc in ((f0, h0), (f1, h1)):
                base_c = heel + foot_dir * (ff * boot_len)
                arc_r = 0.060 if ff < 0.72 else 0.050
                r_sab.append([
                    base_c + foot_side * (math.sin(a) * arc_r) + Vector((0.0, 0.0, 0.008 + math.cos(a) * hh_arc))
                    for a in [-1.25 + 2.50 * k / 8.0 for k in range(9)]
                ])
            config.loft_rings(bm_sab, r_sab, close_cap_start=False, close_cap_end=False)
        sab_obj = config.finalize_bmesh(bm_sab, f"Armor_Sabaton_Plates_{side}", "11_LEG_ARMOR", mat_name="MAT_Steel_Dark", smooth=True)
        config.add_solidify(sab_obj, thickness=0.003, offset=1.0)
        objs.append(sab_obj)

    return objs


def build_armor(detail: str = "MEDIUM") -> dict:
    """Create all plate armor, gauntlets, tassets, and grounded boots."""
    ds = config.DETAIL_SETTINGS[detail]
    segs = ds["radial_segs"]
    torso = _build_cuirass(segs)
    arm_l = _build_left_hero_arm()
    arm_r = _build_right_sword_arm()
    hands = _build_gauntlets()
    legs = _build_leg_armor(segs)
    return {
        "torso": torso,
        "arms": arm_l + arm_r,
        "hands": hands,
        "legs": legs,
    }
