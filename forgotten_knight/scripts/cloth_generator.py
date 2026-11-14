"""Draped cloth garment generator for THE FORGOTTEN KNIGHT.
Creates multi-layered thick wrapped neck scarf & ragged chest drape,
tattered rear hood/cowl seamlessly meeting helmet skull, fitted dark tunic,
split pleated front tabard panels (with clean UV mapping on left panel for the
faded heraldic crest), and heavy flowing torn/punctured back cape.
"""

import math
import bpy
import bmesh
from mathutils import Vector
import config


def _build_neck_scarf(detail: str) -> list:
    """Smooth asymmetrically folded forest-green neck cowl/scarf mantle & flared rear hood
    seamlessly blending from helmet skull down onto shoulder cape."""
    objs = []
    segs_u = 36 if detail != "LOW" else 22
    segs_v = 14 if detail != "LOW" else 8

    # 1. Sculpted overlapping diagonal cloth wrap (asymmetrical scarf folds, not flat stacked tubes)
    for ring_idx, (z_off, r_x, r_y, tilt_slope, thick_x, thick_z, ph) in enumerate([
        (1.522, 0.122, 0.118, 0.032, 0.036, 0.024, 0.0),
        (1.472, 0.152, 0.140, -0.025, 0.044, 0.028, 1.8),
    ]):
        bm = bmesh.new()
        rings = []
        for i in range(segs_u):
            t = i / segs_u
            ang = t * math.pi * 2.0  # 0=+X Left pauldron, -pi/2=-Y Front, pi=-X Right
            ca, sa = math.cos(ang), math.sin(ang)

            front_w = max(0.0, -sa)
            right_w = max(0.0, -ca)
            left_clear = max(0.0, ca)

            # Diagonal asymmetric scarf sweep + subtle non-uniform cloth pleats
            diag = math.sin(ang - 0.6) * tilt_slope
            pleat = math.sin(ang * 5.0 + ph) * 0.008 + math.cos(ang * 9.0 - ph) * 0.005
            rx = r_x + right_w * 0.038 - left_clear * 0.024
            ry = r_y + front_w * 0.022
            z_center = z_off - front_w * 0.045 - right_w * 0.026 + left_clear * 0.030 + diag + pleat

            c = Vector((ca * rx, sa * ry - 0.012, z_center))
            tang = Vector((-sa * rx, ca * ry, 0.0)).normalized()
            out_dir = Vector((ca, sa, -0.22 * front_w)).normalized()
            up_dir = out_dir.cross(tang).normalized()

            v_ring = []
            for j in range(segs_v):
                va = 2.0 * math.pi * j / segs_v
                # Flattened draped ribbon fold profile with central crease trough
                crease = 1.0 - 0.25 * math.exp(-((va - 1.5) ** 2) * 2.5) + 0.14 * math.sin(va * 2.0 + ang * 3.0)
                pt = c + out_dir * (math.cos(va) * thick_x * crease) + up_dir * (math.sin(va) * thick_z * crease)
                v_ring.append(pt)
            rings.append(v_ring)

        vert_rings = [[bm.verts.new(p) for p in r] for r in rings]
        for i in range(segs_u):
            inext = (i + 1) % segs_u
            for j in range(segs_v):
                jnext = (j + 1) % segs_v
                bm.faces.new((vert_rings[i][j], vert_rings[inext][j], vert_rings[inext][jnext], vert_rings[i][jnext]))
        objs.append(config.finalize_bmesh(bm, f"Hood_Scarf_Wrap_{ring_idx+1}", "04_HOOD", mat_name="MAT_Fabric_ForestGreen", smooth=True))

    # 2. Asymmetric ragged scarf drape cascading across Right shoulder (-X) while revealing Chest Heraldry
    bm_ap = bmesh.new()
    nu = 20
    nv = 28
    grid = []
    for iu in range(nu):
        tu = iu / (nu - 1)  # 0 inner neck collar (Z=1.505) -> 1 torn shawl hem
        row = []
        for iv in range(nv):
            tv = iv / (nv - 1)
            # Wrap from rear-right (-4.00 rad) over Right shoulder (-pi) to upper-chest center (-1.28 rad)
            ang = -4.00 + tv * 2.72
            ca, sa = math.cos(ang), math.sin(ang)

            # Long ragged cascade over Right shoulder/pec (tv ~ 0.28..0.55), lifted neatly over central chest cross!
            chest_lift = max(0.0, (tv - 0.58) / 0.42) ** 1.35
            drape_len = (0.28 + 0.07 * math.sin(tv * math.pi * 1.1)) * (1.0 - 0.46 * chest_lift)
            rag = (math.sin(tv * 24.0) * 0.020 + math.cos(tv * 39.0) * 0.012) * (tu ** 1.7)
            z = 1.505 - tu * drape_len + rag

            rad_x = 0.144 + tu * (0.178 * max(0.0, -ca) + 0.044)
            rad_y = 0.148 + tu * (0.048 * max(0.0, -sa) + 0.018 * max(0.0, sa))
            fold = (math.sin(tv * 16.0 - tu * 3.0) * 0.012 + math.cos(tv * 8.5) * 0.007) * (0.20 + 0.80 * tu)
            x = ca * (rad_x + fold)
            y = sa * (rad_y + fold) - 0.014
            row.append(bm_ap.verts.new(Vector((x, y, z))))
        grid.append(row)

    for iu in range(nu - 1):
        for iv in range(nv - 1):
            bm_ap.faces.new((grid[iu][iv], grid[iu][iv+1], grid[iu+1][iv+1], grid[iu+1][iv]))
    apron = config.finalize_bmesh(bm_ap, "Hood_Scarf_Drape", "04_HOOD", mat_name="MAT_Fabric_ForestGreen", smooth=True)
    config.add_solidify(apron, thickness=0.0045, offset=1.0)
    objs.append(apron)

    # 3. Clean rear hood/nape mantle wrapping outside upper cape collar (zero clipping!)
    bm_hd = bmesh.new()
    h_u, h_v = 18, 24
    grid_h = []
    for iu in range(h_u):
        tu = iu / (h_u - 1)  # 0 tucked along nape behind Helm_Skull (Z~1.64) -> 1 shoulder mantle hem (Z~1.39)
        row = []
        for iv in range(h_v):
            tv = iv / (h_v - 1) * 2.0 - 1.0  # -1 Right (-X) .. +1 Left (+X)
            ang = math.pi * 0.5 + tv * (1.06 + 0.44 * tu)
            ca, sa = math.cos(ang), math.sin(ang)

            shoulder_flare = 0.154 * (max(0.0, tu - 0.25) / 0.75) ** 1.25
            rx = 0.118 + tu * 0.032 + shoulder_flare
            ry = 0.138 + tu * 0.044 + shoulder_flare * 0.22

            crown_arch = -0.048 * (tv * tv) * (1.0 - tu * 0.50)
            rag = (math.sin(tv * 19.0 + 0.9) * 0.018 + math.cos(tv * 31.0 - 0.5) * 0.011 + 0.014 * (-tv)) * (tu ** 2.4)
            fold = (math.sin(tv * 14.0 + tu * 2.5) * 0.007 + math.cos(tv * 7.0) * 0.005) * min(1.0, tu * 1.4)

            z = 1.635 + crown_arch - tu * 0.235 - 0.024 * (tv * tv) * tu + rag
            x = ca * (rx + fold)
            y = 0.002 + sa * (ry + fold) + tu * 0.030
            row.append(bm_hd.verts.new(Vector((x, y, z))))
        grid_h.append(row)

    for iu in range(h_u - 1):
        for iv in range(h_v - 1):
            bm_hd.faces.new((grid_h[iu][iv], grid_h[iu][iv+1], grid_h[iu+1][iv+1], grid_h[iu+1][iv]))

    hood_obj = config.finalize_bmesh(bm_hd, "Hood_Rear_Cowl", "04_HOOD", mat_name="MAT_Fabric_Cape", smooth=True)
    config.add_solidify(hood_obj, thickness=0.0045, offset=1.0)
    objs.append(hood_obj)

    return objs


def _build_tunic_and_tabard(detail: str) -> list:
    """Build upper dark surcoat liner and split heavy pleated front tabard panels."""
    objs = []

    # Upper surcoat strictly slim inside Armor_Cuirass except waist/underarm edges
    bm_u = bmesh.new()
    rings = []
    for z, rx, ry in [(0.95, 0.154, 0.108), (1.08, 0.148, 0.100), (1.26, 0.172, 0.112), (1.39, 0.168, 0.100)]:
        rings.append([Vector((math.cos(2 * math.pi * i / 16) * rx, math.sin(2 * math.pi * i / 16) * ry - 0.006, z)) for i in range(16)])
    config.loft_rings(bm_u, rings, close_cap_start=False, close_cap_end=False)
    objs.append(config.finalize_bmesh(bm_u, "Tunic_Upper_Surcoat", "09_TUNIC", mat_name="MAT_Fabric_ForestGreen", smooth=True))

    nu = 18 if detail != "LOW" else 12
    nv = 14 if detail != "LOW" else 9

    for side in ("R", "L"):
        s = -1.0 if side == "R" else 1.0
        bm = bmesh.new()
        uv_layer = bm.loops.layers.uv.verify()
        grid = []
        for iu in range(nu):
            tu = iu / (nu - 1)  # 0 below waist belt (Z=0.95) -> 1 jagged torn hem (Z~0.35)
            row = []
            for iv in range(nv):
                tv = iv / (nv - 1)
                inner_gap = 0.020 + tu * 0.075 if side == "R" else 0.008 + tu * 0.048
                ang = -math.pi * 0.5 + s * (0.04 + inner_gap * 1.35 + tv * 1.02)
                rx = 0.178 + tu * 0.095
                ry = 0.136 + tu * 0.062

                pleat_freq = 15.0 if side == "R" else 13.0
                fold = (math.sin(tv * pleat_freq + tu * 1.6) * 0.015 + math.cos(tv * 7.5) * 0.008) * (0.25 + 0.75 * tu)
                rag_wave = math.sin(tv * 25.0 + (0.0 if side == "L" else 1.8)) * 0.038 + math.cos(tv * 41.0) * 0.022
                z_end = 0.35 + (0.04 if side == "R" else 0.0)
                z = 0.95 - tu * (0.95 - z_end) + rag_wave * (tu ** 2.2)

                pt_x = math.cos(ang) * (rx + fold)
                pt_y = math.sin(ang) * (ry + fold) - 0.016 - tu * 0.068 * (1.0 if side == "L" else 0.85)
                row.append(bm.verts.new(Vector((pt_x, pt_y, z))))
            grid.append(row)

        for iu in range(nu - 1):
            for iv in range(nv - 1):
                if iu == nu - 2 and iv in (3, 8):
                    continue
                v00, v01 = grid[iu][iv], grid[iu][iv + 1]
                v11, v10 = grid[iu + 1][iv + 1], grid[iu + 1][iv]
                if side == "R":
                    face = bm.faces.new((v00, v10, v11, v01))
                else:
                    face = bm.faces.new((v00, v01, v11, v10))

                for loop in face.loops:
                    co = loop.vert.co
                    if side == "L":
                        u_c = (co.x - 0.070) / 0.160
                        v_c = (co.z - 0.41) / 0.23
                        loop[uv_layer].uv = (u_c, v_c)
                    else:
                        loop[uv_layer].uv = (co.x * 2.0 + 3.0, co.z * 2.0 + 3.0)

        mat_name = "MAT_Fabric_Tabard" if side == "L" else "MAT_Fabric_ForestGreen"
        tab_obj = config.finalize_bmesh(bm, f"Tabard_Front_{side}", "09_TUNIC", mat_name=mat_name, smooth=True)
        config.add_solidify(tab_obj, thickness=0.0045, offset=1.0)
        objs.append(tab_obj)

    return objs


def _build_back_cape(detail: str) -> list:
    """Build long heavy broad-shouldered dark green cloak (Z=1.48 -> 0.22) with deep
    drapery folds, punctured tears, jagged trailing strips, resting cleanly UNDER scabbard."""
    bm = bmesh.new()
    nu = 28 if detail != "LOW" else 18
    nv = 24 if detail != "LOW" else 14

    sb = config.SWORD_BACK
    scab_top = sb["scabbard_top"]
    scab_tip = sb["scabbard_tip"]
    nu = 24
    nv = 30
    grid = []
    for iu in range(nu):
        tu = iu / (nu - 1)
        row = []
        for iv in range(nv):
            tv = iv / (nv - 1) * 2.0 - 1.0  # -1 Right (-X) .. +1 Left (+X)

            # Broader curved shoulder collar tucked strictly inside Hood_Rear_Cowl top -> draped tattered cloak
            if tu < 0.22:
                half_w = 0.215 + 0.038 * math.sin((tu / 0.22) * math.pi * 0.5)
            else:
                half_w = 0.245 + 0.068 * math.sin((tu - 0.22) * 1.4) - 0.038 * ((tu - 0.22) ** 1.35)

            asym_shift = -0.026 * (tu ** 1.05)
            x_base = tv * half_w + asym_shift
            wrap_curve = 0.062 * (1.0 - tv * tv)
            # Stay tucked cleanly inside Hood_Rear_Cowl near top collar (tu < 0.16), drape back gracefully below
            collar_tuck = 0.068 * max(0.0, 1.0 - tu / 0.18)
            y_base = 0.088 + 0.072 * min(1.0, tu * 2.2) + wrap_curve - collar_tuck

            z_raw = 1.485 - tu * 1.255 - 0.026 * (tv * tv) * (1.0 - tu)
            scab_t = max(0.0, min(1.0, (scab_top.z - z_raw) / max(0.01, scab_top.z - scab_tip.z)))
            scab_pos = scab_top.lerp(scab_tip, scab_t)
            dist_scab = abs(x_base - scab_pos.x)
            # Smooth wide Gaussian cinch under diagonal back scabbard (zero sharp polygonal creases!)
            cinch_gauss = math.exp(-((dist_scab / 0.115) ** 2))
            cinch = 0.030 * cinch_gauss * (1.0 if 0.08 < tu < 0.86 else 0.35)

            pleat = (
                math.sin(tv * 16.5 + tu * 2.0) * (0.009 + 0.022 * tu)
                + math.cos(tv * 9.0 - tu * 1.4) * (0.005 + 0.014 * tu)
            ) * (0.30 + 0.70 * (1.0 - cinch_gauss * 0.45))

            left_retract = 0.065 * max(0.0, tv - 0.30) * (tu ** 0.95) if tu > 0.22 else 0.0
            rag = (
                math.sin(tv * 22.0 + 0.7) * 0.048
                + math.cos(tv * 37.0 - 0.4) * 0.028
                + (0.072 if tv > 0.35 else -0.024)
            ) * (tu ** 2.4)

            z = z_raw + left_retract * 1.4 + rag
            y = y_base + pleat - cinch - left_retract * 0.4

            # Smoothly depress cape surface behind SWORD_BACK & baldric with soft falloff instead of hard min() step
            max_y_allowed = scab_pos.y - 0.032
            if y > max_y_allowed and 0.06 < tu < 0.94:
                y = y * (1.0 - cinch_gauss) + max_y_allowed * cinch_gauss

            row.append(bm.verts.new(Vector((x_base, y, z))))
        grid.append(row)

    holes = {
        (nu - 7, 20), (nu - 6, 20), (nu - 6, 21),
        (nu - 10, 11), (nu - 9, 11),
        (nu - 5, 7), (nu - 4, 7),
        (nu - 4, 24), (nu - 3, 24),
    }

    for iu in range(nu - 1):
        for iv in range(nv - 1):
            if (iu, iv) in holes:
                continue
            if iu >= nu - 3 and iv in (5, 13, 21, 26):
                continue
            bm.faces.new((grid[iu][iv], grid[iu][iv+1], grid[iu+1][iv+1], grid[iu+1][iv]))

    cape = config.finalize_bmesh(bm, "Cape_Back_Cloak", "10_CAPE", mat_name="MAT_Fabric_Cape", smooth=True)
    config.add_solidify(cape, thickness=0.0045, offset=1.0)
    return [cape]


def build_cloth(detail: str = "MEDIUM") -> dict:
    """Build neck scarf, hood cowl, tunic, split crest tabard, and tattered rear cape."""
    hood = _build_neck_scarf(detail)
    tunic = _build_tunic_and_tabard(detail)
    cape = _build_back_cape(detail)
    return {
        "hood": hood,
        "tunic": tunic,
        "cape": cape,
    }
