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
    """Build multi-tiered weathered stone pedestal standing in the shallow courtyard."""
    bm = bmesh.new()
    # Submerged broad base plinth -> octagonal drum -> upper cornice cap
    _add_cylinder_tier(bm, (0.0, 0.0), -1.6, 0.5, 3.6, 3.3, segs=20)
    _add_cylinder_tier(bm, (0.0, 0.0), 0.5, 1.4, 3.05, 2.75, segs=12)
    _add_cylinder_tier(bm, (0.0, 0.0), 1.4, total_h - 0.55, 2.35, 2.15, segs=12)
    _add_cylinder_tier(bm, (0.0, 0.0), total_h - 0.55, total_h, 2.45, 2.55, segs=16)

    apply_coherent_stone_weathering(bm, amp=0.055, freq=0.65, seed_offset=(1.5, 2.5, 0.0))
    return create_mesh_object(
        "Statue_Pedestal",
        bm,
        col,
        mat=mat,
        location=loc,
        rotation_deg=(0.0, 0.0, rot_z_deg),
        smooth=False,
    )


def _sculpt_robe_and_torso(bm: bmesh.types.BMesh, base_z: float, fig_h: float) -> None:
    """Generate a high-detail robed body & shoulders using parametric cross-sections + drapery folds."""
    # Note: local -Y is front (facing camera/causeway)
    n_theta = 32
    n_rings = 28
    body_h = fig_h * 0.78  # up to base of neck/shoulders

    rings: List[List[bmesh.types.BMVert]] = []
    for ri in range(n_rings + 1):
        t = ri / n_rings  # 0.0 = feet/hem, 1.0 = shoulders/collar
        z = base_z + t * body_h

        # Overall silhouette width (X) and depth (Y)
        if t < 0.45:
            # Flared lower robe narrowing gently toward waist
            rx = 1.95 - 0.45 * (t / 0.45)
            ry = 1.55 - 0.35 * (t / 0.45)
        elif t < 0.82:
            # Waist expanding into broad monastic shoulders
            u = (t - 0.45) / 0.37
            rx = 1.50 + 0.58 * math.sin(u * math.pi * 0.65)
            ry = 1.20 + 0.25 * math.sin(u * math.pi * 0.6)
        else:
            # Shoulder slope inward to neck/cowl collar
            u = (t - 0.82) / 0.18
            rx = 2.02 * (1.0 - 0.62 * (u ** 1.35))
            ry = 1.40 * (1.0 - 0.52 * (u ** 1.35))

        # Slight dignified forward posture lean at upper torso
        y_shift = -0.18 * math.sin(t * math.pi * 0.8)

        ring_vs: List[bmesh.types.BMVert] = []
        for ti in range(n_theta):
            ang = (ti / n_theta) * math.tau
            ca, sa = math.cos(ang), math.sin(ang)

            # Deep vertical Gothic robe folds (sharper pleated ridges along front & sides)
            fold_amp = 0.22 * (1.0 - 0.48 * t)
            fold = (
                abs(math.sin(ang * 4.5 + t * 0.8)) * 0.65 - 0.32
                + math.cos(ang * 11.0 - t * 1.8) * 0.32
                + math.sin(ang * 3.0 + 0.5) * 0.22
            )
            # Mantle/cloak ridge over shoulders (around t=0.55..0.95)
            mantle = 0.12 * math.sin((t - 0.45) * 7.0) * (1.0 if sa > -0.3 else 0.4) if t > 0.4 else 0.0

            r_mod = 1.0 + fold_amp * fold + mantle
            vx = rx * r_mod * ca
            vy = ry * r_mod * sa + y_shift
            ring_vs.append(bm.verts.new((vx, vy, z)))
        rings.append(ring_vs)

    # Cap bottom & top
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
    """Sculpt draped upper arms, folded forearms, and clasped hands across the chest."""
    for side in (-1.0, 1.0):
        # Upper arm descending from shoulder to elbow, then forearm curving inward to center chest
        pts = [
            (Vector((side * 1.68, -0.10, base_z + fig_h * 0.72)), 0.52),
            (Vector((side * 1.62, -0.45, base_z + fig_h * 0.62)), 0.58),
            (Vector((side * 1.25, -0.92, base_z + fig_h * 0.53)), 0.62),  # draped sleeve elbow
            (Vector((side * 0.65, -1.24, base_z + fig_h * 0.56)), 0.46),
            (Vector((side * 0.15, -1.32, base_z + fig_h * 0.59)), 0.38),  # clasped hands
        ]
        n_seg = 12
        arm_rings: List[List[bmesh.types.BMVert]] = []
        for idx, (pos, rad) in enumerate(pts):
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
                # Draped hanging sleeve fold downward
                hang = 1.35 if (n2.z * math.sin(ang) + n1.z * math.cos(ang)) < -0.3 else 1.0
                p = pos + (n1 * math.cos(ang) + n2 * math.sin(ang)) * rad * hang
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


def _sculpt_head_and_cowl(bm: bmesh.types.BMesh, base_z: float, fig_h: float) -> None:
    """Sculpt inclined solemn head, facial planes (brow, nose, beard), and draped hood/mantle."""
    head_center = Vector((0.0, -0.24, base_z + fig_h * 0.875))
    head_h = fig_h * 0.138
    head_r = head_h * 0.35

    # Inclined downward pitch (~12 degrees toward -Y)
    tilt = Euler((math.radians(12.0), 0.0, 0.0), "XYZ").to_matrix()

    n_u = 24
    n_v = 16
    grid: List[List[bmesh.types.BMVert]] = []
    for vi in range(n_v + 1):
        v = vi / n_v  # 0 = chin/collar, 1 = crown
        phi = (v - 0.5) * math.pi
        z_local = math.sin(phi) * (head_h * 0.62)
        r_lat = math.cos(phi)
        row = []
        for ui in range(n_u):
            ang = (ui / n_u) * math.tau  # -pi/2 is front (-Y)
            ca, sa = math.cos(ang), math.sin(ang)

            rx = head_r * 0.82 * r_lat
            ry = head_r * 0.98 * r_lat
            px = rx * ca
            py = ry * sa

            if sa < -0.10:
                front_w = (-sa - 0.10) / 0.90
                if 0.56 < v < 0.72:
                    py -= 0.12 * front_w * (1.0 - abs(v - 0.64) / 0.08)
                if 0.45 < v < 0.57 and 0.15 < abs(ca) < 0.62:
                    py += 0.11 * front_w
                if 0.36 < v < 0.62 and abs(ca) < 0.20:
                    py -= 0.18 * (1.0 - abs(ca) / 0.20) * (1.0 - abs(v - 0.44) / 0.24)
                if v < 0.42:
                    py -= 0.14 * front_w * (1.0 - v / 0.42)
            else:
                # Hooded cowl blending seamlessly downward into broad draped shoulders
                hood_flare = 1.0 + 0.55 * max(0.0, 1.0 - v * 1.4)
                px *= 1.24 * hood_flare
                py *= 1.18 * hood_flare
                if v < 0.25:
                    z_local -= 0.35 * (0.25 - v)

            pt = head_center + tilt @ Vector((px, py, z_local))
            row.append(bm.verts.new(pt))
        grid.append(row)

    for vi in range(n_v):
        r0, r1 = grid[vi], grid[vi + 1]
        for ui in range(n_u):
            uj = (ui + 1) % n_u
            try:
                bm.faces.new([r0[ui], r0[uj], r1[uj], r1[ui]])
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
