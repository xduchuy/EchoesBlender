"""Central monumental weathered stone statue reconstruction."""

import math
from typing import Dict, List, Tuple

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector, noise

from config import LAYOUT
from geometry_utils import (
    apply_coherent_stone_weathering,
    create_mesh_object,
    get_rng,
)


def _add_cylinder_tier(
    bm: bmesh.types.BMesh,
    center_xy: Tuple[float, float],
    z0: float,
    z1: float,
    r_bot: float,
    r_top: float,
    segs: int = 16,
) -> None:
    """Add a tapered cylindrical/polygonal pedestal tier."""
    cx, cy = center_xy
    bot_vs = []
    top_vs = []
    for i in range(segs):
        a = (i / segs) * math.tau
        ca, sa = math.cos(a), math.sin(a)
        bot_vs.append(bm.verts.new((cx + r_bot * ca, cy + r_bot * sa, z0)))
        top_vs.append(bm.verts.new((cx + r_top * ca, cy + r_top * sa, z1)))
    try:
        bm.faces.new(list(reversed(bot_vs)))
        bm.faces.new(top_vs)
    except ValueError:
        pass
    for i in range(segs):
        j = (i + 1) % segs
        try:
            bm.faces.new([bot_vs[i], bot_vs[j], top_vs[j], top_vs[i]])
        except ValueError:
            pass


def _build_pedestal(
    col: bpy.types.Collection,
    mat: bpy.types.Material,
    loc: Tuple[float, float, float],
    rot_z_deg: float,
    total_h: float,
) -> bpy.types.Object:
    """Build stepped octagonal Gothic stone pedestal with molded plinth, shaft, and cornice."""
    bm = bmesh.new()
    # Submerged foundation plinth
    _add_cylinder_tier(bm, (0.0, 0.0), -1.6, 0.35, 3.65, 3.45, segs=16)
    # Molded chamfered torus step above water
    _add_cylinder_tier(bm, (0.0, 0.0), 0.35, 0.72, 3.35, 2.95, segs=16)
    _add_cylinder_tier(bm, (0.0, 0.0), 0.72, 1.38, 2.88, 2.68, segs=8)
    # Recessed middle shaft + necking ring
    shaft_top = total_h - 0.62
    _add_cylinder_tier(bm, (0.0, 0.0), 1.38, 1.55, 2.52, 2.30, segs=8)
    _add_cylinder_tier(bm, (0.0, 0.0), 1.55, shaft_top, 2.28, 2.12, segs=8)
    # Carved projecting corner pilasters along octagonal shaft corners
    for ci in range(8):
        ang = (ci / 8.0) * math.tau + math.pi / 8.0
        px = math.cos(ang) * 2.18
        py = math.sin(ang) * 2.18
        _add_cylinder_tier(bm, (px, py), 1.48, shaft_top + 0.05, 0.24, 0.20, segs=6)
    # Projecting upper abacus / cornice table
    _add_cylinder_tier(bm, (0.0, 0.0), shaft_top, total_h - 0.28, 2.16, 2.52, segs=8)
    _add_cylinder_tier(bm, (0.0, 0.0), total_h - 0.28, total_h, 2.55, 2.48, segs=16)

    apply_coherent_stone_weathering(bm, amp=0.042, freq=0.70, seed_offset=(1.5, 2.5, 0.0))
    return create_mesh_object(
        "Statue_Pedestal",
        bm,
        col,
        mat=mat,
        location=loc,
        rotation_deg=(0.0, 0.0, rot_z_deg),
        sharp_angle_deg=38.0,
    )


def _sculpt_robe_and_torso(bm: bmesh.types.BMesh, base_z: float, fig_h: float) -> None:
    """Generate solemn heroic monastic robed body & layered mantle folds without bloat."""
    # Note: local -Y is front (facing camera/causeway)
    n_theta = 36
    n_rings = 30
    body_h = fig_h * 0.785  # up to base of cowl/neck

    rings: List[List[bmesh.types.BMVert]] = []
    for ri in range(n_rings + 1):
        t = ri / n_rings  # 0.0 = feet/hem, 1.0 = neck/collar
        z = base_z + t * body_h

        # Heroic sculpted silhouette: grounded skirt -> waist -> balanced monastic shoulders -> collar
        if t < 0.44:
            u = t / 0.44
            rx = 1.62 - 0.56 * (u ** 0.85)
            ry = 1.32 - 0.40 * (u ** 0.85)
        elif t < 0.82:
            u = (t - 0.44) / 0.38
            rx = 1.06 + 0.44 * math.sin(u * math.pi * 0.58)
            ry = 0.92 + 0.20 * math.sin(u * math.pi * 0.55)
        else:
            u = (t - 0.82) / 0.18
            rx = 1.50 * (1.0 - 0.58 * (u ** 1.35))
            ry = 1.12 * (1.0 - 0.50 * (u ** 1.35))

        # Dignified slight forward posture inclination at upper back/shoulders
        y_shift = -0.14 * math.sin(t * math.pi * 0.85)

        ring_vs: List[bmesh.types.BMVert] = []
        for ti in range(n_theta):
            ang = (ti / n_theta) * math.tau  # -pi/2 is front (-Y)
            ca, sa = math.cos(ang), math.sin(ang)

            # Deep sculpted architectural drapery pleats concentrated along lower hem and front tabard
            fold_amp = 0.19 * (1.0 - 0.42 * t)
            fold = (
                abs(math.sin(ang * 4.0 + t * 0.6)) * 0.55 - 0.25
                + math.cos(ang * 10.0 - t * 1.4) * 0.28
                + math.sin(ang * 3.0 + 0.4) * 0.18
            )
            # Layered mantle/cape drape curving from shoulders down chest & back
            front_tabard = 0.09 * math.exp(-((ang + math.pi * 0.5) / 0.45) ** 2) * (1.0 - 0.45 * t)
            mantle = (
                0.13 * math.sin((t - 0.42) * 6.5) * (1.0 if sa > -0.25 else 0.45)
                if t > 0.38
                else 0.0
            )

            r_mod = 1.0 + fold_amp * fold + mantle + front_tabard
            vx = rx * r_mod * ca
            vy = ry * r_mod * sa + y_shift
            ring_vs.append(bm.verts.new((vx, vy, z)))
        rings.append(ring_vs)

    try:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    except ValueError:
        pass
    for ri in range(n_rings):
        r0, r1 = rings[ri], rings[ri + 1]
        for ti in range(n_theta):
            tj = (ti + 1) % n_theta
            try:
                bm.faces.new([r0[ti], r0[tj], r1[tj], r1[ti]])
            except ValueError:
                pass


def _sculpt_arms_and_hands(bm: bmesh.types.BMesh, base_z: float, fig_h: float) -> None:
    """Sculpt draped hanging sleeves, flared cuffs, and clasped hands over center chest."""
    for side in (-1.0, 1.0):
        pts = [
            (Vector((side * 1.16, -0.06, base_z + fig_h * 0.725)), 0.38, 1.0),
            (Vector((side * 1.14, -0.32, base_z + fig_h * 0.625)), 0.44, 1.30),
            (Vector((side * 0.88, -0.72, base_z + fig_h * 0.540)), 0.48, 1.44),  # hanging sleeve elbow fold
            (Vector((side * 0.44, -0.92, base_z + fig_h * 0.575)), 0.31, 1.12),  # cuff rim
            (Vector((side * 0.13, -0.98, base_z + fig_h * 0.595)), 0.20, 0.90),  # carved wrist/palm
        ]
        n_seg = 14
        arm_rings: List[List[bmesh.types.BMVert]] = []
        for idx, (pos, rad, hang_scale) in enumerate(pts):
            if idx < len(pts) - 1:
                tangent = (pts[idx + 1][0] - pos).normalized()
            else:
                tangent = (pos - pts[idx - 1][0]).normalized()
            up_ref = Vector((0.0, 0.0, 1.0))
            if abs(tangent.dot(up_ref)) > 0.92:
                up_ref = Vector((0.0, 1.0, 0.0))
            n1 = tangent.cross(up_ref).normalized()
            n2 = tangent.cross(n1).normalized()
            ring = []
            for ti in range(n_seg):
                ang = (ti / n_seg) * math.tau
                dz_comp = n2.z * math.sin(ang) + n1.z * math.cos(ang)
                hang = hang_scale if dz_comp < -0.25 else 1.0
                pleat = 1.0 + 0.08 * math.cos(ang * 4.0) if idx in (1, 2) else 1.0
                p = pos + (n1 * math.cos(ang) + n2 * math.sin(ang)) * rad * hang * pleat
                ring.append(bm.verts.new(p))
            arm_rings.append(ring)

        try:
            bm.faces.new(list(reversed(arm_rings[0])))
            bm.faces.new(arm_rings[-1])
        except ValueError:
            pass
        for ri in range(len(arm_rings) - 1):
            r0, r1 = arm_rings[ri], arm_rings[ri + 1]
            for ti in range(n_seg):
                tj = (ti + 1) % n_seg
                try:
                    bm.faces.new([r0[ti], r0[tj], r1[tj], r1[ti]])
                except ValueError:
                    pass

    # Central clasped prayer hands & vertical stone sword/staff relief anchoring hands naturally
    clasped_center = Vector((0.0, -1.07, base_z + fig_h * 0.592))
    bmesh.ops.create_icosphere(
        bm,
        subdivisions=2,
        radius=0.25,
        matrix=Matrix.Translation(clasped_center) @ Matrix.Diagonal((1.15, 0.78, 1.18, 1.0)),
    )
    # Stone crosier / grounded ceremonial blade hilt resting down front robe centerline
    _add_cylinder_tier(
        bm,
        (0.0, -1.05),
        base_z + 0.25,
        base_z + fig_h * 0.64,
        0.13,
        0.10,
        segs=8,
    )
    _add_cylinder_tier(
        bm,
        (0.0, -1.05),
        base_z + fig_h * 0.57,
        base_z + fig_h * 0.59,
        0.38,
        0.34,
        segs=8,
    )


def _sculpt_head_and_cowl(bm: bmesh.types.BMesh, base_z: float, fig_h: float) -> None:
    """Sculpt inclined solemn head and smooth draped hood/cowl without pole pinch or cheek seams."""
    head_center = Vector((0.0, -0.22, base_z + fig_h * 0.878))
    head_h = fig_h * 0.140
    head_r = head_h * 0.36

    tilt = Euler((math.radians(11.0), 0.0, 0.0), "XYZ").to_matrix()

    n_u = 28
    n_v = 18

    # Neck collar transition bridge merging torso into chin/hood
    _add_cylinder_tier(
        bm,
        (0.0, -0.18),
        base_z + fig_h * 0.755,
        base_z + fig_h * 0.835,
        0.72,
        0.54,
        segs=16,
    )

    # Single unified bottom/top pole vertices prevent zero-area quads & subsurf pinching!
    south_pole = bm.verts.new(head_center + tilt @ Vector((0.0, -0.08, -head_h * 0.62)))
    north_pole = bm.verts.new(head_center + tilt @ Vector((0.0, 0.05, head_h * 0.64)))

    lat_rings: List[List[bmesh.types.BMVert]] = []
    for vi in range(1, n_v):
        v = vi / n_v
        phi = (v - 0.5) * math.pi
        z_base = math.sin(phi) * (head_h * 0.60)
        r_lat = math.cos(phi)
        row = []
        for ui in range(n_u):
            ang = (ui / n_u) * math.tau  # -pi/2 is front (-Y)
            ca, sa = math.cos(ang), math.sin(ang)

            rx = head_r * 0.80 * r_lat
            ry = head_r * 0.96 * r_lat
            px = rx * ca
            py = ry * sa
            z_local = z_base

            # Smooth C2 blend factor between recessed shadowed face opening (sa < -0.15) and hood (sa > +0.08)
            blend_t = max(0.0, min(1.0, (sa - (-0.28)) / 0.42))
            hood_mask = blend_t * blend_t * (3.0 - 2.0 * blend_t)
            face_mask = 1.0 - hood_mask

            if face_mask > 0.001:
                front_w = max(0.0, (-sa - 0.08) / 0.92) * face_mask
                # Heavy solemn stone brow overhang
                if 0.56 < v < 0.74:
                    py -= 0.13 * front_w * (1.0 - abs(v - 0.65) / 0.09)
                # Deep recessed eye cavities
                if 0.44 < v < 0.57 and 0.14 < abs(ca) < 0.64:
                    py += 0.11 * front_w
                # Strong aquiline stone nose bridge
                if 0.36 < v < 0.63 and abs(ca) < 0.21:
                    py -= 0.17 * face_mask * (1.0 - abs(ca) / 0.21) * (1.0 - abs(v - 0.45) / 0.24)
                # Solemn weathered beard & chin descending toward sternum
                if v < 0.42:
                    py -= 0.14 * front_w * (1.0 - v / 0.42)

            if hood_mask > 0.001:
                hood_flare = 1.0 + 0.58 * max(0.0, 1.0 - v * 1.35)
                hood_scale_x = 1.0 + 0.26 * hood_flare * hood_mask
                hood_scale_y = 1.0 + 0.22 * hood_flare * hood_mask
                px *= hood_scale_x
                py *= hood_scale_y
                # Raised hooded brim arch catching rim light over temples & crown
                brim = 0.09 * math.exp(-((blend_t - 0.45) / 0.22) ** 2) * max(0.2, 1.0 - abs(v - 0.68))
                py -= brim
                if v < 0.28:
                    z_local -= 0.34 * (0.28 - v) * hood_mask

            pt = head_center + tilt @ Vector((px, py, z_local))
            row.append(bm.verts.new(pt))
        lat_rings.append(row)

    # Bottom cap triangle fan
    first_ring = lat_rings[0]
    for ui in range(n_u):
        uj = (ui + 1) % n_u
        try:
            bm.faces.new([south_pole, first_ring[uj], first_ring[ui]])
        except ValueError:
            pass

    # Quad strips between interior latitude rings
    for ri in range(len(lat_rings) - 1):
        r0, r1 = lat_rings[ri], lat_rings[ri + 1]
        for ui in range(n_u):
            uj = (ui + 1) % n_u
            try:
                bm.faces.new([r0[ui], r0[uj], r1[uj], r1[ui]])
            except ValueError:
                pass

    # Top cap triangle fan
    last_ring = lat_rings[-1]
    for ui in range(n_u):
        uj = (ui + 1) % n_u
        try:
            bm.faces.new([last_ring[ui], last_ring[uj], north_pole])
        except ValueError:
            pass


def build_central_statue(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
    subsurf_level: int = 2,
) -> List[bpy.types.Object]:
    """Build the monumental central robed stone statue on its flooded pedestal."""
    col = cols["05_STATUE"]
    cfg = LAYOUT["statue"]
    loc = cfg["location"]
    rot_z = cfg["rotation_z_deg"]
    ped_h = cfg["pedestal_height"]
    fig_h = cfg["figure_height"]

    objs: List[bpy.types.Object] = []
    objs.append(_build_pedestal(col, mats["MAT_Statue_Weathered"], loc, rot_z, ped_h))

    bm = bmesh.new()
    _sculpt_robe_and_torso(bm, base_z=ped_h - 0.15, fig_h=fig_h)
    _sculpt_arms_and_hands(bm, base_z=ped_h - 0.15, fig_h=fig_h)
    _sculpt_head_and_cowl(bm, base_z=ped_h - 0.15, fig_h=fig_h)

    # Subtle carved limestone weathering
    apply_coherent_stone_weathering(bm, amp=0.045, freq=0.9, seed_offset=(7.0, 3.0, 9.0))
    statue_obj = create_mesh_object(
        "Statue_Central_Figure",
        bm,
        col,
        mat=mats["MAT_Statue_Weathered"],
        location=loc,
        rotation_deg=(0.0, 0.0, rot_z),
        smooth=True,
    )

    if subsurf_level > 0:
        sub = statue_obj.modifiers.new("Subsurf", "SUBSURF")
        sub.levels = 1
        sub.render_levels = subsurf_level

    objs.append(statue_obj)
    return objs
