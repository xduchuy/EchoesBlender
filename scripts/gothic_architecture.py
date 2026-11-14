"""Procedural Gothic architecture & coherent destruction system."""

import math
import random
from typing import Callable, Dict, List, Optional, Tuple

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector, noise

from config import LAYOUT
from geometry_utils import (
    add_box_to_bmesh,
    apply_coherent_stone_weathering,
    create_mesh_object,
    get_rng,
    gothic_arch_points,
)


def _xf_matrix(
    loc: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rot_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Matrix:
    rot = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ").to_matrix().to_4x4()
    return Matrix.Translation(loc) @ rot


def _add_local_box(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    center: Tuple[float, float, float],
    size: Tuple[float, float, float],
    rot_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    bevel_width: float = 0.0,
) -> List[bmesh.types.BMVert]:
    """Append an oriented box transformed by xf into bm."""
    sx, sy, sz = size
    local_rot = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ").to_matrix().to_4x4()
    local_m = Matrix.Translation(center) @ local_rot @ Matrix.Diagonal((sx, sy, sz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=xf @ local_m)
    verts = ret["verts"]
    if bevel_width > 0.002:
        edges = list({e for v in verts for e in v.link_edges})
        bmesh.ops.bevel(
            bm,
            geom=edges,
            offset=bevel_width,
            segments=1,
            profile=0.5,
            affect="EDGES",
            clamp_overlap=True,
        )
    return [v for v in verts if v.is_valid]


def _add_poly_extrude_y(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    pts_xz: List[Tuple[float, float]],
    y0: float,
    y1: float,
) -> None:
    """Extrude a closed 2D (x, z) polygon along local Y from y0 to y1."""
    if len(pts_xz) < 3:
        return
    front_vs = [bm.verts.new(xf @ Vector((x, y0, z))) for x, z in pts_xz]
    back_vs = [bm.verts.new(xf @ Vector((x, y1, z))) for x, z in pts_xz]
    try:
        bm.faces.new(front_vs)
    except ValueError:
        pass
    try:
        bm.faces.new(list(reversed(back_vs)))
    except ValueError:
        pass
    n = len(pts_xz)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([front_vs[i], front_vs[j], back_vs[j], back_vs[i]])
        except ValueError:
            pass


def create_pointed_arch(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    span: float,
    spring_z: float,
    apex_z: float,
    arch_thickness: float = 0.55,
    depth_y: float = 1.2,
    segments_per_side: int = 9,
    molding_protrusion: float = 0.14,
    rng: Optional[random.Random] = None,
    damage_skip_prob: float = 0.0,
) -> None:
    """Build a pointed Gothic arch ring with voussoir segments and projecting molding."""
    half_span = span * 0.5
    inner_pts = gothic_arch_points(half_span, spring_z, apex_z, segments_per_side)
    outer_pts = gothic_arch_points(
        half_span + arch_thickness,
        spring_z,
        apex_z + arch_thickness * 1.15,
        segments_per_side,
    )
    y0 = -depth_y * 0.5 - molding_protrusion
    y1 = depth_y * 0.5 + molding_protrusion

    n = min(len(inner_pts), len(outer_pts))
    for i in range(n - 1):
        if rng and damage_skip_prob > 0.0 and rng.random() < damage_skip_prob:
            continue
        p0, p1 = inner_pts[i], inner_pts[i + 1]
        q1, q0 = outer_pts[i + 1], outer_pts[i]
        # Slight voussoir relief jitter
        dy = (rng.uniform(-0.025, 0.025) if rng else 0.0)
        _add_poly_extrude_y(bm, xf, [p0, p1, q1, q0], y0 + dy, y1 - dy)


def create_stone_pier(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    cx: float,
    cy: float,
    base_z: float,
    width: float,
    depth: float,
    height: float,
    plinth_h: float = 1.2,
    capital_h: float = 0.75,
    chamfer: float = 0.06,
) -> None:
    """Build a Gothic stone pier with plinth base, shaft, and capital molding."""
    if height <= 0.1:
        return
    # Plinth
    ph = min(plinth_h, height * 0.35)
    _add_local_box(
        bm,
        xf,
        (cx, cy, base_z + ph * 0.5),
        (width + 0.28, depth + 0.28, ph),
        bevel_width=chamfer,
    )
    # Main shaft
    _add_local_box(
        bm,
        xf,
        (cx, cy, base_z + height * 0.5),
        (width, depth, height),
        bevel_width=chamfer,
    )
    # Capital if tall enough
    if height > plinth_h + capital_h + 0.8:
        ch = capital_h
        _add_local_box(
            bm,
            xf,
            (cx, cy, base_z + height - ch * 0.5),
            (width + 0.34, depth + 0.34, ch),
            bevel_width=chamfer * 1.1,
        )


def create_buttress(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    cx: float,
    cy: float,
    base_z: float,
    width: float,
    projection: float,
    height: float,
    stages: int = 3,
    direction_y: float = -1.0,
) -> None:
    """Build a multi-stage stepped Gothic buttress projecting along ±Y."""
    stage_h = height / max(1, stages)
    for i in range(stages):
        t = i / max(1, stages)
        cur_proj = projection * (1.0 - 0.32 * t)
        cur_w = width * (1.0 - 0.10 * t)
        z0 = base_z + i * stage_h
        z1 = z0 + stage_h + 0.15
        sh = z1 - z0
        off_y = cy + direction_y * (cur_proj * 0.5)
        _add_local_box(
            bm,
            xf,
            (cx, off_y, z0 + sh * 0.5),
            (cur_w, cur_proj, sh),
            bevel_width=0.04,
        )
        # Sloped/stepped cap stone
        _add_local_box(
            bm,
            xf,
            (cx, off_y - direction_y * 0.08, z1 + 0.12),
            (cur_w + 0.12, cur_proj + 0.08, 0.24),
            bevel_width=0.04,
        )


def create_cornice(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    cx: float,
    cy: float,
    z: float,
    width: float,
    depth: float,
    height: float = 0.42,
    overhang: float = 0.26,
) -> None:
    """Build a projecting horizontal stone cornice / stringcourse."""
    _add_local_box(
        bm,
        xf,
        (cx, cy, z),
        (width + overhang * 2.0, depth + overhang * 2.0, height),
        bevel_width=0.05,
    )


def create_lancet_tracery(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    span: float,
    sill_z: float,
    spring_z: float,
    apex_z: float,
    rng: random.Random,
    damage: float = 0.35,
) -> None:
    """Build slender stone mullions and Gothic sub-arch tracery inside a window opening."""
    if span < 1.3:
        return
    mullion_w = 0.16
    mullion_d = 0.22
    # Central or twin mullions
    num_mullions = 1 if span < 2.6 else 2
    for idx in range(num_mullions):
        if rng.random() < damage * 0.4:
            continue
        frac = (idx + 1) / (num_mullions + 1) - 0.5
        mx = frac * span
        # Sometimes top or bottom of mullion is broken off
        top_z = spring_z + (apex_z - spring_z) * (0.65 if num_mullions == 1 else 0.45)
        if rng.random() < damage * 0.6:
            top_z = sill_z + (top_z - sill_z) * rng.uniform(0.35, 0.85)
        mh = max(0.3, top_z - sill_z)
        _add_local_box(
            bm,
            xf,
            (mx, 0.0, sill_z + mh * 0.5),
            (mullion_w, mullion_d, mh),
            bevel_width=0.02,
        )

    # Optional horizontal transom bar (like Right Front belfry in reference!)
    if (spring_z - sill_z) > 4.5 and rng.random() > damage * 0.3:
        tz = sill_z + (spring_z - sill_z) * 0.52
        _add_local_box(
            bm,
            xf,
            (0.0, 0.0, tz),
            (span * 0.96, mullion_d * 0.9, 0.18),
            bevel_width=0.02,
        )

    # Sub-arch ring near head
    if rng.random() > damage * 0.45:
        create_pointed_arch(
            bm,
            xf,
            span=span * 0.44,
            spring_z=spring_z - 0.3,
            apex_z=apex_z - 0.6,
            arch_thickness=0.14,
            depth_y=0.20,
            segments_per_side=5,
            molding_protrusion=0.02,
            rng=rng,
            damage_skip_prob=damage * 0.5,
        )


def create_arch_frame(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    bay_width: float,
    bay_height: float,
    wall_thickness: float,
    opening_width: float,
    sill_z: float,
    spring_z: float,
    apex_z: float,
    rng: random.Random,
    top_profile_fn: Optional[Callable[[float], float]] = None,
    add_moldings: bool = True,
    add_tracery: bool = False,
    tracery_damage: float = 0.35,
    course_relief: bool = True,
) -> None:
    """
    Build a solid Gothic arched wall bay with genuine 3D open aperture,
    spandrel stonework, piers, recessed archivolts, and optional broken top skyline.
    """
    half_w = bay_width * 0.5
    half_open = min(opening_width * 0.5, half_w - 0.35)
    y0 = -wall_thickness * 0.5
    y1 = wall_thickness * 0.5

    def get_top_z(x: float) -> float:
        if top_profile_fn is None:
            return bay_height
        return max(0.0, min(bay_height, top_profile_fn(x)))

    # Left & Right piers
    pier_w = half_w - half_open
    for side in (-1.0, 1.0):
        px_center = side * (half_open + pier_w * 0.5)
        h_pier = get_top_z(px_center)
        if h_pier > 0.2:
            _add_local_box(
                bm,
                xf,
                (px_center, 0.0, h_pier * 0.5),
                (pier_w, wall_thickness, h_pier),
                bevel_width=0.03,
            )

    # Sill wall below opening (if sill_z > 0)
    if sill_z > 0.08:
        h_sill = min(sill_z, get_top_z(0.0))
        if h_sill > 0.1:
            _add_local_box(
                bm,
                xf,
                (0.0, 0.0, h_sill * 0.5),
                (half_open * 2.02, wall_thickness, h_sill),
                bevel_width=0.03,
            )
            # Projecting window sill ledge
            _add_local_box(
                bm,
                xf,
                (0.0, 0.0, h_sill),
                (half_open * 2.15, wall_thickness + 0.22, 0.24),
                bevel_width=0.03,
            )

    # Spandrel wall above pointed arch curve
    arch_pts = gothic_arch_points(half_open, spring_z, apex_z, segments_per_side=7)
    for i in range(len(arch_pts) - 1):
        x0, z0 = arch_pts[i]
        x1, z1 = arch_pts[i + 1]
        tz0 = get_top_z(x0)
        tz1 = get_top_z(x1)
        if tz0 > z0 + 0.08 and tz1 > z1 + 0.08:
            _add_poly_extrude_y(bm, xf, [(x0, z0), (x1, z1), (x1, tz1), (x0, tz0)], y0, y1)

    # Molded arch ring & capitals
    if add_moldings:
        max_top = max(get_top_z(x) for x, _ in arch_pts)
        skip_p = 0.35 if max_top < apex_z + 0.4 else 0.06
        create_pointed_arch(
            bm,
            xf,
            span=half_open * 2.0,
            spring_z=spring_z,
            apex_z=apex_z,
            arch_thickness=min(0.45, pier_w * 0.55),
            depth_y=wall_thickness * 0.88,
            segments_per_side=7,
            molding_protrusion=0.12,
            rng=rng,
            damage_skip_prob=skip_p,
        )
        # Impost / capital blocks at spring line
        for side in (-1.0, 1.0):
            if get_top_z(side * half_open) > spring_z + 0.2:
                _add_local_box(
                    bm,
                    xf,
                    (side * (half_open + 0.14), 0.0, spring_z),
                    (0.55, wall_thickness + 0.24, 0.38),
                    bevel_width=0.03,
                )

    # Optional Gothic lancet tracery
    if add_tracery and get_top_z(0.0) > spring_z + 0.5:
        create_lancet_tracery(
            bm,
            xf,
            span=half_open * 2.0,
            sill_z=max(0.0, sill_z),
            spring_z=spring_z,
            apex_z=apex_z,
            rng=rng,
            damage=tracery_damage,
        )

    # Subtle stone masonry block relief on piers so edges catch sunlit silhouette!
    if course_relief:
        num_blocks = int(bay_height / 1.4)
        for _ in range(num_blocks):
            side = rng.choice([-1.0, 1.0])
            bx = side * rng.uniform(half_open + 0.15, half_w - 0.1)
            bz = rng.uniform(0.8, max(1.0, get_top_z(bx) - 0.6))
            if bz < get_top_z(bx) - 0.4:
                bw = rng.uniform(0.55, 1.05)
                bh = rng.uniform(0.35, 0.58)
                bd = wall_thickness + rng.uniform(0.06, 0.16)
                _add_local_box(
                    bm,
                    xf,
                    (bx, rng.uniform(-0.04, 0.04), bz),
                    (bw, bd, bh),
                    bevel_width=0.025,
                )


def create_gothic_window(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    bay_width: float,
    bay_height: float,
    wall_thickness: float,
    window_width: float,
    sill_z: float,
    spring_z: float,
    apex_z: float,
    rng: random.Random,
    top_profile_fn: Optional[Callable[[float], float]] = None,
    has_tracery: bool = True,
    tracery_damage: float = 0.35,
) -> None:
    """Build a recessed Gothic lancet window bay."""
    create_arch_frame(
        bm=bm,
        xf=xf,
        bay_width=bay_width,
        bay_height=bay_height,
        wall_thickness=wall_thickness,
        opening_width=window_width,
        sill_z=sill_z,
        spring_z=spring_z,
        apex_z=apex_z,
        rng=rng,
        top_profile_fn=top_profile_fn,
        add_moldings=True,
        add_tracery=has_tracery,
        tracery_damage=tracery_damage,
        course_relief=True,
    )


def create_broken_parapet(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    width: float,
    thickness: float,
    base_z: float,
    max_height: float,
    rng: random.Random,
    damage_bias: float = 0.45,
    merlon_width: float = 1.15,
) -> None:
    """Build a jagged, partially collapsed Gothic parapet / battlement crown."""
    n_seg = max(4, int(round(width / merlon_width)))
    seg_w = width / n_seg
    # Coherent height field so missing stones cluster rather than checkerboard
    phase = rng.uniform(0.0, 10.0)
    for i in range(n_seg):
        sx = -width * 0.5 + (i + 0.5) * seg_w
        coh = 0.5 + 0.5 * math.sin(i * 0.9 + phase)
        if coh < damage_bias * 0.72 and rng.random() < 0.7:
            # Collapsed gap
            h = rng.uniform(0.15, max_height * 0.32)
        else:
            # Surviving merlon or stepped masonry tooth
            is_merlon = (i % 2 == 0)
            h = max_height * (rng.uniform(0.75, 1.05) if is_merlon else rng.uniform(0.42, 0.72))
        if h > 0.25:
            _add_local_box(
                bm,
                xf,
                (sx, 0.0, base_z + h * 0.5),
                (seg_w * 0.96, thickness, h),
                rot_deg=(rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5), 0.0),
                bevel_width=0.035,
            )


def create_arch_vault_fragment(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    span: float,
    spring_z: float,
    rise: float,
    rng: random.Random,
) -> None:
    """Create a broken Gothic rib-vault springer fragment inside an exposed hollow tower."""
    for side in (-1.0, 1.0):
        # Broken diagonal rib curving inward and stopping mid-air
        steps = 4
        for s in range(steps):
            t = s / steps
            px = side * (span * 0.5 - t * span * 0.26)
            pz = spring_z + rise * (1.0 - (1.0 - t) ** 1.7) * 0.65
            ang = side * (25.0 + t * 35.0)
            _add_local_box(
                bm,
                xf,
                (px, 0.0, pz),
                (0.45, 0.45, span * 0.18),
                rot_deg=(0.0, ang, 0.0),
                bevel_width=0.03,
            )


def create_ruined_wall(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    length: float,
    thickness: float,
    base_height: float,
    min_height: float,
    rng: random.Random,
    bays: int = 0,
    sill_z: float = 0.0,
    arch_apex_ratio: float = 0.72,
    collapse_side: str = "center",
) -> None:
    """Build a coherent ruined masonry wall with optional Gothic arch bays and stepped top."""
    phase = rng.uniform(0.0, 6.28)

    def wall_top(world_x: float) -> float:
        u = (world_x + length * 0.5) / max(0.01, length)  # 0..1
        if collapse_side == "left":
            trend = u
        elif collapse_side == "right":
            trend = 1.0 - u
        elif collapse_side == "center":
            trend = abs(u - 0.5) * 2.0
        else:
            trend = 0.65
        wave = 0.5 + 0.5 * math.sin(u * 9.0 + phase)
        h = min_height + (base_height - min_height) * (0.55 * trend + 0.45 * wave)
        return max(0.3, h)

    if bays > 0:
        bay_w = length / bays
        for i in range(bays):
            bx = -length * 0.5 + (i + 0.5) * bay_w
            bay_xf = xf @ Matrix.Translation((bx, 0.0, 0.0))

            def local_top(lx: float, offset_x: float = bx) -> float:
                return wall_top(offset_x + lx)

            create_arch_frame(
                bm=bm,
                xf=bay_xf,
                bay_width=bay_w * 1.01,
                bay_height=base_height,
                wall_thickness=thickness,
                opening_width=bay_w * 0.58,
                sill_z=sill_z,
                spring_z=sill_z + (base_height - sill_z) * 0.45,
                apex_z=base_height * arch_apex_ratio,
                rng=rng,
                top_profile_fn=local_top,
                add_moldings=True,
                add_tracery=(bay_w > 3.0 and rng.random() > 0.4),
                tracery_damage=0.45,
            )
    else:
        n_seg = max(4, int(round(length / 1.8)))
        seg_w = length / n_seg
        for i in range(n_seg):
            sx = -length * 0.5 + (i + 0.5) * seg_w
            sh = wall_top(sx)
            _add_local_box(
                bm,
                xf,
                (sx, 0.0, sh * 0.5),
                (seg_w * 1.02, thickness, sh),
                bevel_width=0.04,
            )


def create_tower_segment(
    bm: bmesh.types.BMesh,
    xf: Matrix,
    width: float,
    depth: float,
    base_z: float,
    height: float,
    wall_thickness: float,
    rng: random.Random,
    bays_per_face: int = 1,
    sill_z: float = 2.0,
    has_tracery: bool = True,
    tracery_damage: float = 0.35,
    broken_top: bool = False,
    top_corner_bias: Tuple[float, float, float, float] = (1.0, 0.85, 0.95, 0.72),
    add_buttresses: bool = True,
    add_interior_floor: bool = False,
) -> None:
    """
    Build a hollow 4-sided Gothic tower stage with corner piers, pierced arched window bays
    on all 4 faces, buttresses, cornice, and coherent roofline destruction.
    """
    hw = width * 0.5
    hd = depth * 0.5
    pier_sz = max(1.15, wall_thickness * 1.25)

    # Four corner piers (heights modulated by top_corner_bias when broken_top is True)
    corners = [
        (-hw + pier_sz * 0.5, -hd + pier_sz * 0.5, top_corner_bias[0]),  # front-left
        (hw - pier_sz * 0.5, -hd + pier_sz * 0.5, top_corner_bias[1]),   # front-right
        (-hw + pier_sz * 0.5, hd - pier_sz * 0.5, top_corner_bias[2]),   # back-left
        (hw - pier_sz * 0.5, hd - pier_sz * 0.5, top_corner_bias[3]),    # back-right
    ]
    for cx, cy, bias in corners:
        ph = height * (bias if broken_top else 1.0)
        create_stone_pier(
            bm,
            xf,
            cx,
            cy,
            base_z,
            pier_sz,
            pier_sz,
            ph,
            plinth_h=0.9 if base_z < 2.0 else 0.4,
            capital_h=0.55,
            chamfer=0.05,
        )
        if add_buttresses:
            dir_y = -1.0 if cy < 0 else 1.0
            dir_x = -1.0 if cx < 0 else 1.0
            # Outer buttresses perpendicular to faces
            create_buttress(
                bm,
                xf,
                cx,
                cy + dir_y * (pier_sz * 0.45),
                base_z,
                width=pier_sz * 0.75,
                projection=0.95,
                height=ph * 0.85,
                stages=2 if height < 15.0 else 3,
                direction_y=dir_y,
            )
            butt_xf = xf @ Matrix.Translation((cx + dir_x * (pier_sz * 0.45), cy, 0.0)) @ _xf_matrix(rot_deg=(0, 0, 90 if dir_x > 0 else -90))
            create_buttress(
                bm,
                butt_xf,
                0.0,
                0.0,
                base_z,
                width=pier_sz * 0.75,
                projection=0.95,
                height=ph * 0.85,
                stages=2 if height < 15.0 else 3,
                direction_y=-1.0,
            )

    # Four pierced Gothic walls spanning between corner piers
    # Face definitions: (center_xy, rot_z_deg, clear_span, left_corner_bias, right_corner_bias)
    faces = [
        ((0.0, -hd + wall_thickness * 0.5), 0.0, width - pier_sz * 1.9, top_corner_bias[0], top_corner_bias[1]),
        ((0.0, hd - wall_thickness * 0.5), 180.0, width - pier_sz * 1.9, top_corner_bias[3], top_corner_bias[2]),
        ((-hw + wall_thickness * 0.5, 0.0), -90.0, depth - pier_sz * 1.9, top_corner_bias[2], top_corner_bias[0]),
        ((hw - wall_thickness * 0.5, 0.0), 90.0, depth - pier_sz * 1.9, top_corner_bias[1], top_corner_bias[3]),
    ]

    for (fx, fy), frot, span_len, b_left, b_right in faces:
        bay_w = span_len / max(1, bays_per_face)
        for bi in range(bays_per_face):
            bx = -span_len * 0.5 + (bi + 0.5) * bay_w
            face_xf = xf @ _xf_matrix((fx, fy, base_z), (0.0, 0.0, frot)) @ Matrix.Translation((bx, 0.0, 0.0))
            t_mid = (bi + 0.5) / max(1, bays_per_face)
            face_bias = b_left * (1.0 - t_mid) + b_right * t_mid

            def bay_top(lx: float, fb: float = face_bias, bw: float = bay_w) -> float:
                if not broken_top:
                    return height
                u = (lx + bw * 0.5) / max(0.01, bw)
                notch = 0.16 * math.sin(u * math.pi * 2.3 + fb * 5.0)
                return max(sill_z + 1.5, height * (fb - 0.12 + notch))

            open_w = bay_w * (0.64 if bays_per_face == 1 else 0.68)
            spring_z = sill_z + (height - sill_z) * 0.52
            apex_z = min(height - 1.1, sill_z + (height - sill_z) * 0.84)
            create_gothic_window(
                bm=bm,
                xf=face_xf,
                bay_width=bay_w * 1.04,
                bay_height=height,
                wall_thickness=wall_thickness,
                window_width=open_w,
                sill_z=sill_z,
                spring_z=spring_z,
                apex_z=apex_z,
                rng=rng,
                top_profile_fn=bay_top if broken_top else None,
                has_tracery=has_tracery,
                tracery_damage=tracery_damage,
            )

            if broken_top and face_bias > 0.78:
                create_broken_parapet(
                    bm,
                    face_xf,
                    width=bay_w * 0.96,
                    thickness=wall_thickness * 0.75,
                    base_z=height * (face_bias - 0.16),
                    max_height=1.8,
                    rng=rng,
                    damage_bias=0.5,
                )

    if not broken_top:
        create_cornice(bm, xf, 0.0, 0.0, base_z + height, width, depth, height=0.45, overhang=0.28)
    else:
        # Broken vault ribs inside top of ruined tower!
        create_arch_vault_fragment(bm, xf, span=width * 0.65, spring_z=base_z + height * 0.55, rise=4.2, rng=rng)

    if add_interior_floor:
        # Partial collapsed interior stone ledge (not a full closed ceiling!)
        _add_local_box(
            bm,
            xf,
            (-width * 0.18, 0.0, base_z + 0.3),
            (width * 0.45, depth * 0.55, 0.5),
            bevel_width=0.04,
        )


def create_fallen_masonry(
    bm: bmesh.types.BMesh,
    center: Tuple[float, float, float],
    rng: random.Random,
    scale: float = 1.0,
) -> None:
    """Append a single weathered fallen stone block or broken cornice fragment."""
    sx = rng.uniform(0.7, 1.8) * scale
    sy = rng.uniform(0.6, 1.5) * scale
    sz = rng.uniform(0.4, 1.0) * scale
    rot = (rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(0.0, 6.28))
    add_box_to_bmesh(bm, center, (sx, sy, sz), rot_euler=rot, bevel_width=0.05 * scale, noise_amp=0.04 * scale, rng=rng)


def create_ruin_cluster(
    name: str,
    center: Tuple[float, float, float],
    col: bpy.types.Collection,
    mat: bpy.types.Material,
    rng: random.Random,
    count: int = 8,
    radius: float = 4.5,
    include_broken_arch: bool = False,
) -> bpy.types.Object:
    """Create a coherent rubble & broken stone cluster near a collapsed structure."""
    bm = bmesh.new()
    for _ in range(count):
        ang = rng.uniform(0.0, math.tau)
        r = (rng.random() ** 0.65) * radius
        px = center[0] + math.cos(ang) * r
        py = center[1] + math.sin(ang) * r
        pz = center[2] + rng.uniform(-0.25, 0.35)
        create_fallen_masonry(bm, (px, py, pz), rng, scale=rng.uniform(0.85, 1.45))

    if include_broken_arch:
        xf = _xf_matrix(
            (center[0], center[1], center[2] - 0.3),
            (rng.uniform(-22, 22), rng.uniform(-25, 25), rng.uniform(0, 360)),
        )
        create_pointed_arch(
            bm,
            xf,
            span=rng.uniform(2.4, 3.6),
            spring_z=0.5,
            apex_z=2.8,
            arch_thickness=0.55,
            depth_y=0.95,
            segments_per_side=6,
            rng=rng,
            damage_skip_prob=0.38,
        )

    apply_coherent_stone_weathering(bm, amp=0.05, freq=0.45, seed_offset=(center[0], center[1], 0.0))
    return create_mesh_object(name, bm, col, mat=mat)


# ==============================================================================
# MASTER SANCTUARY ARCHITECTURAL ASSEMBLY
# ==============================================================================

def _build_left_front_tower(cols, mats, preset: str) -> List[bpy.types.Object]:
    """Zone A: Left Forward Ruined Tower + Left Courtyard Flying Arch + Left Colonnade + Bastion."""
    rng = get_rng("left_front")
    col = cols["ARCH_LeftFront"]
    cfg = LAYOUT["towers"]["left_front"]
    objs: List[bpy.types.Object] = []

    bm = bmesh.new()
    xf = _xf_matrix(cfg["location"], (0.0, 0.0, cfg["rotation_z_deg"]))

    # Stage 1: Heavy lower tower with tall open pointed archways
    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"],
        depth=cfg["depth"],
        base_z=0.0,
        height=cfg["base_height"],
        wall_thickness=1.65,
        rng=rng,
        bays_per_face=1,
        sill_z=1.6,
        has_tracery=False,
        broken_top=False,
        add_buttresses=True,
        add_interior_floor=True,
    )

    # Stage 2: Damaged upper belfry with twin narrow windows & broken corner crown
    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"] * 0.88,
        depth=cfg["depth"] * 0.88,
        base_z=cfg["base_height"],
        height=cfg["belfry_height"],
        wall_thickness=1.35,
        rng=rng,
        bays_per_face=2,
        sill_z=1.4,
        has_tracery=True,
        tracery_damage=0.45,
        broken_top=True,
        top_corner_bias=(1.02, 0.72, 0.94, 0.62),
        add_buttresses=True,
    )

    # Signature bridging Gothic archway extending right toward the courtyard (u~0.35..0.41)
    bridge_xf = xf @ _xf_matrix((cfg["width"] * 0.5 + 3.4, 2.2, 0.0), (0.0, 0.0, -8.0))
    create_arch_frame(
        bm=bm,
        xf=bridge_xf,
        bay_width=7.4,
        bay_height=18.2,
        wall_thickness=1.45,
        opening_width=4.4,
        sill_z=0.0,
        spring_z=8.5,
        apex_z=14.8,
        rng=rng,
        top_profile_fn=lambda lx: 18.2 - 3.6 * ((lx + 3.7) / 7.4),
        add_moldings=True,
        add_tracery=False,
    )

    # Left-side colonnade / ruined aqueduct wing connecting toward Far-Left Bastion (-48.5, 8.5)
    wing_xf = xf @ _xf_matrix((-cfg["width"] * 0.5 - 12.2, 4.8, 0.5), (0.0, 0.0, -16.0))
    create_ruined_wall(
        bm=bm,
        xf=wing_xf,
        length=23.5,
        thickness=1.9,
        base_height=18.2,
        min_height=12.5,
        rng=rng,
        bays=6,
        sill_z=0.0,
        arch_apex_ratio=0.58,
        collapse_side="center",
    )
    # Jagged crenellated parapet on top of the left wing
    create_broken_parapet(
        bm=bm,
        xf=wing_xf,
        width=22.5,
        thickness=1.25,
        base_z=15.0,
        max_height=3.4,
        rng=rng,
        damage_bias=0.32,
    )

    apply_coherent_stone_weathering(bm, amp=0.075, freq=0.32, seed_offset=(12.0, -5.0, 3.0), z_erosion_boost=0.04)
    objs.append(create_mesh_object("Tower_LeftFront_Main", bm, col, mat=mats["MAT_Limestone_Base"]))

    # Far-left Bastion Tower perched near the left cliff
    bm_bast = bmesh.new()
    bcfg = LAYOUT["towers"]["left_bastion"]
    bxf = _xf_matrix(bcfg["location"], (0.0, 0.0, bcfg["rotation_z_deg"]))
    create_tower_segment(
        bm=bm_bast,
        xf=bxf,
        width=bcfg["width"],
        depth=bcfg["depth"],
        base_z=0.0,
        height=bcfg["height"],
        wall_thickness=1.4,
        rng=rng,
        bays_per_face=1,
        sill_z=4.5,
        has_tracery=False,
        broken_top=True,
        top_corner_bias=(0.95, 1.0, 0.88, 0.76),
        add_buttresses=True,
    )
    apply_coherent_stone_weathering(bm_bast, amp=0.08, freq=0.35, seed_offset=(-55.0, 11.0, 0.0))
    objs.append(create_mesh_object("Tower_LeftBastion", bm_bast, col, mat=mats["MAT_Limestone_Base"]))
    return objs


def _build_left_rear_tower(cols, mats, preset: str) -> List[bpy.types.Object]:
    """Zone B: Tall Slender Left Rear Belfry Tower."""
    rng = get_rng("left_rear")
    col = cols["ARCH_LeftRear"]
    cfg = LAYOUT["towers"]["left_rear"]

    bm = bmesh.new()
    xf = _xf_matrix(cfg["location"], (0.0, 0.0, cfg["rotation_z_deg"]))

    # Base tower shaft
    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"],
        depth=cfg["depth"],
        base_z=0.0,
        height=cfg["base_height"],
        wall_thickness=1.35,
        rng=rng,
        bays_per_face=1,
        sill_z=2.0,
        has_tracery=False,
        broken_top=False,
        add_buttresses=True,
    )
    # Tall open belfry crown (rises prominently above arcade)
    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"] * 0.92,
        depth=cfg["depth"] * 0.92,
        base_z=cfg["base_height"],
        height=cfg["belfry_height"],
        wall_thickness=1.15,
        rng=rng,
        bays_per_face=1,
        sill_z=1.5,
        has_tracery=True,
        tracery_damage=0.45,
        broken_top=True,
        top_corner_bias=(1.0, 0.92, 0.85, 0.96),
        add_buttresses=True,
    )
    apply_coherent_stone_weathering(bm, amp=0.07, freq=0.32, seed_offset=(-13.0, 21.0, 4.0), z_erosion_boost=0.04)
    return [create_mesh_object("Tower_LeftRear_Belfry", bm, col, mat=mats["MAT_Limestone_Light"])]


def _build_right_rear_tower(cols, mats, preset: str) -> List[bpy.types.Object]:
    """Zone C: Slender Paired Right Rear Belfry Tower."""
    rng = get_rng("right_rear")
    col = cols["ARCH_RightRear"]
    cfg = LAYOUT["towers"]["right_rear"]

    bm = bmesh.new()
    xf = _xf_matrix(cfg["location"], (0.0, 0.0, cfg["rotation_z_deg"]))

    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"],
        depth=cfg["depth"],
        base_z=0.0,
        height=cfg["base_height"],
        wall_thickness=1.35,
        rng=rng,
        bays_per_face=1,
        sill_z=2.0,
        has_tracery=False,
        broken_top=False,
        add_buttresses=True,
    )
    # Twin narrow lancet slits in belfry stage matching reference
    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"] * 0.92,
        depth=cfg["depth"] * 0.92,
        base_z=cfg["base_height"],
        height=cfg["belfry_height"],
        wall_thickness=1.15,
        rng=rng,
        bays_per_face=2,
        sill_z=1.6,
        has_tracery=True,
        tracery_damage=0.35,
        broken_top=True,
        top_corner_bias=(0.90, 1.0, 0.96, 0.82),
        add_buttresses=True,
    )
    apply_coherent_stone_weathering(bm, amp=0.07, freq=0.32, seed_offset=(13.0, 21.0, 7.0), z_erosion_boost=0.04)
    return [create_mesh_object("Tower_RightRear_Belfry", bm, col, mat=mats["MAT_Limestone_Light"])]


def _build_right_front_tower(cols, mats, preset: str) -> List[bpy.types.Object]:
    """Zone D: Monumental Right Forward Tower Group + Forward Nave Wing + Broken Courtyard Stair."""
    rng = get_rng("right_front")
    col = cols["ARCH_RightFront"]
    cfg = LAYOUT["towers"]["right_front"]
    objs: List[bpy.types.Object] = []

    bm = bmesh.new()
    xf = _xf_matrix(cfg["location"], (0.0, 0.0, cfg["rotation_z_deg"]))

    # Lower monumental stage
    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"],
        depth=cfg["depth"],
        base_z=0.0,
        height=cfg["base_height"],
        wall_thickness=1.75,
        rng=rng,
        bays_per_face=2,
        sill_z=2.2,
        has_tracery=True,
        tracery_damage=0.5,
        broken_top=False,
        add_buttresses=True,
        add_interior_floor=True,
    )
    # Upper tall open twin-lancet belfry (signature open lattice windows!)
    create_tower_segment(
        bm=bm,
        xf=xf,
        width=cfg["width"] * 0.90,
        depth=cfg["depth"] * 0.90,
        base_z=cfg["base_height"],
        height=cfg["belfry_height"],
        wall_thickness=1.35,
        rng=rng,
        bays_per_face=2,
        sill_z=1.4,
        has_tracery=True,
        tracery_damage=0.22,
        broken_top=True,
        top_corner_bias=(0.95, 1.02, 0.72, 0.90),
        add_buttresses=True,
    )

    # Forward ruined nave wing projecting toward foreground water (u~0.64..0.77)
    nave_xf = xf @ _xf_matrix((-1.8, -10.8, 0.0), (0.0, 0.0, 4.0))
    # Left (courtyard-facing) ruined wall with tall broken lancet bays
    left_wall_xf = nave_xf @ _xf_matrix((-4.2, 0.0, 0.0), (0.0, 0.0, -90.0))
    create_ruined_wall(
        bm=bm,
        xf=left_wall_xf,
        length=12.5,
        thickness=1.55,
        base_height=21.0,
        min_height=10.5,
        rng=rng,
        bays=2,
        sill_z=2.5,
        arch_apex_ratio=0.78,
        collapse_side="left",
    )
    # Right outer ruined wall of nave wing
    right_wall_xf = nave_xf @ _xf_matrix((4.4, 0.0, 0.0), (0.0, 0.0, 90.0))
    create_ruined_wall(
        bm=bm,
        xf=right_wall_xf,
        length=11.5,
        thickness=1.55,
        base_height=18.5,
        min_height=8.0,
        rng=rng,
        bays=2,
        sill_z=2.2,
        arch_apex_ratio=0.72,
        collapse_side="right",
    )
    # Front collapsed gable / archway of nave wing
    front_wall_xf = nave_xf @ _xf_matrix((0.0, -5.8, 0.0), (0.0, 0.0, 0.0))
    create_arch_frame(
        bm=bm,
        xf=front_wall_xf,
        bay_width=8.6,
        bay_height=14.5,
        wall_thickness=1.6,
        opening_width=4.4,
        sill_z=0.0,
        spring_z=5.5,
        apex_z=10.8,
        rng=rng,
        top_profile_fn=lambda lx: 13.5 - 4.0 * abs(lx / 4.3),
        add_moldings=True,
        add_tracery=False,
    )
    # Heavy corner buttresses on nave wing
    create_buttress(bm, front_wall_xf, -4.1, -0.6, 0.0, 1.5, 1.4, 15.0, stages=3, direction_y=-1.0)
    create_buttress(bm, front_wall_xf, 4.1, -0.6, 0.0, 1.5, 1.4, 13.0, stages=3, direction_y=-1.0)

    # Outer right ruined buttress / stepped ruin wing extending right toward cliff mist (no awkward floating arch loop!)
    side_xf = xf @ _xf_matrix((7.2, -2.0, 0.0), (0.0, 0.0, -8.0))
    create_ruined_wall(
        bm=bm,
        xf=side_xf,
        length=6.8,
        thickness=1.8,
        base_height=15.5,
        min_height=6.5,
        rng=rng,
        bays=0,
        sill_z=0.0,
        collapse_side="right",
    )

    # Broken stone staircase descending from Right Front nave into flooded courtyard
    stair_xf = xf @ _xf_matrix((-9.2, -3.5, 2.0), (0.0, 0.0, -28.0))
    for step_i in range(11):
        sz = 5.4 - step_i * 0.45
        sx = -step_i * 0.65
        sw = 3.2 - (0.5 if step_i in (4, 8) else 0.0)
        _add_local_box(bm, stair_xf, (sx, 0.0, sz), (0.78, sw, 0.48), bevel_width=0.03)
    # Broken parapet wall beside stair
    _add_local_box(bm, stair_xf, (-2.8, -1.6, 3.8), (6.5, 0.65, 2.6), rot_deg=(0.0, 32.0, 0.0), bevel_width=0.04)

    apply_coherent_stone_weathering(bm, amp=0.075, freq=0.32, seed_offset=(22.0, -6.0, 5.0), z_erosion_boost=0.04)
    objs.append(create_mesh_object("Tower_RightFront_Complex", bm, col, mat=mats["MAT_Limestone_Base"]))
    return objs


def _build_rear_arcade(cols, mats, preset: str) -> List[bpy.types.Object]:
    """Zone E: Curved Semicircular Ruined Gothic Arcade behind the central statue."""
    rng = get_rng("rear_arcade")
    col = cols["ARCH_RearArcade"]
    cfg = LAYOUT["rear_arcade"]

    bm = bmesh.new()
    cx, cy, cz = cfg["center"]
    rad = cfg["radius"]
    n_bays = cfg["bays"]
    a0 = math.radians(cfg["start_angle_deg"])
    a1 = math.radians(cfg["end_angle_deg"])

    # Angular span per bay
    d_ang = (a1 - a0) / n_bays
    chord = 2.0 * rad * math.sin(abs(d_ang) * 0.5)

    for i in range(n_bays):
        ang_mid = a0 + (i + 0.5) * d_ang
        bx = cx + rad * math.cos(ang_mid)
        by = cy + rad * math.sin(ang_mid)
        # Tangent orientation facing inward toward center (0, 2)
        rot_deg = math.degrees(ang_mid) - 90.0
        bay_xf = _xf_matrix((bx, by, cz), (0.0, 0.0, rot_deg))

        # Irregular broken upper wall profile per bay
        bay_max_h = cfg["wall_top_height"] - rng.uniform(0.0, 3.8)
        if i in (2, 3):  # Slightly more collapsed right behind statue for dramatic sky/silhouette contrast
            bay_max_h -= 1.5

        def arcade_top(lx: float, mh: float = bay_max_h, cw: float = chord, seed_i: int = i) -> float:
            u = (lx + cw * 0.5) / max(0.01, cw)
            return max(cfg["arch_apex_height"] + 0.6, mh - 2.2 * abs(math.sin(u * 4.5 + seed_i)))

        create_arch_frame(
            bm=bm,
            xf=bay_xf,
            bay_width=chord * 1.04,
            bay_height=cfg["wall_top_height"],
            wall_thickness=1.65,
            opening_width=chord * 0.62,
            sill_z=0.0,
            spring_z=cfg["pier_height"],
            apex_z=cfg["arch_apex_height"],
            rng=rng,
            top_profile_fn=arcade_top,
            add_moldings=True,
            add_tracery=False,
        )
        # Broken upper clerestory / battlement fragments
        if i != 3:
            create_broken_parapet(
                bm=bm,
                xf=bay_xf,
                width=chord * 0.85,
                thickness=1.1,
                base_z=bay_max_h - 1.2,
                max_height=3.6,
                rng=rng,
                damage_bias=0.45,
            )

    # Add taller clustered piers at each bay junction for monumental depth
    for i in range(n_bays + 1):
        ang = a0 + i * d_ang
        px = cx + rad * math.cos(ang)
        py = cy + rad * math.sin(ang)
        rot_deg = math.degrees(ang) - 90.0
        pxf = _xf_matrix((px, py, cz), (0.0, 0.0, rot_deg))
        ph = cfg["wall_top_height"] - rng.uniform(0.0, 3.0)
        create_stone_pier(bm, pxf, 0.0, 0.0, 0.0, 1.85, 2.25, ph, plinth_h=1.6, capital_h=0.8)

    apply_coherent_stone_weathering(bm, amp=0.065, freq=0.35, seed_offset=(0.0, 14.0, 2.0))
    return [create_mesh_object("Arcade_Rear_Apse", bm, col, mat=mats["MAT_Limestone_Base"])]


def _build_connecting_walls(cols, mats, preset: str) -> List[bpy.types.Object]:
    """Zone F: Connecting broken walls, lower courtyard wings, and distant misty spire."""
    rng = get_rng("connecting_walls")
    col = cols["ARCH_ConnectingWalls"]
    objs: List[bpy.types.Object] = []

    bm = bmesh.new()
    # Wall linking Left Front to Left Rear
    xf_lf_lr = _xf_matrix((-17.2, 9.2, -2.0), (0.0, 0.0, 74.0))
    create_ruined_wall(bm, xf_lf_lr, length=15.0, thickness=1.5, base_height=19.5, min_height=11.0, rng=rng, bays=2, sill_z=1.0, collapse_side="center")

    # Wall linking Right Rear (11.2, 22.5) to Right Front (26.5, -9.5)
    xf_rr_rf = _xf_matrix((19.5, 6.5, -2.0), (0.0, 0.0, -64.0))
    create_ruined_wall(bm, xf_rr_rf, length=23.0, thickness=1.55, base_height=20.0, min_height=11.0, rng=rng, bays=3, sill_z=1.5, collapse_side="center")

    # Left courtyard broken staircase descending into flooded basin (u~0.39..0.44)
    stair_l_xf = _xf_matrix((-12.5, -6.5, -1.5), (0.0, 0.0, -24.0))
    for i in range(9):
        _add_local_box(bm, stair_l_xf, (i * 0.65, 0.0, 3.6 - i * 0.42), (0.75, 2.8, 0.45), bevel_width=0.03)

    # Low flooded ruin wall fragments flanking courtyard entrance
    xf_ent_l = _xf_matrix((-15.0, -10.0, -1.5), (0.0, 0.0, 12.0))
    create_ruined_wall(bm, xf_ent_l, length=7.5, thickness=1.3, base_height=8.5, min_height=2.8, rng=rng, bays=1, sill_z=0.0, collapse_side="right")

    apply_coherent_stone_weathering(bm, amp=0.07, freq=0.35, seed_offset=(5.0, -10.0, 1.0))
    objs.append(create_mesh_object("Walls_Connecting_Ruins", bm, col, mat=mats["MAT_Limestone_Base"]))

    # Distant ruined Gothic spire visible through right mist (Priority C architectural silhouette)
    bm_dist = bmesh.new()
    dcfg = LAYOUT["towers"]["distant_spire"]
    dxf = _xf_matrix(dcfg["location"], (0.0, 0.0, dcfg["rotation_z_deg"]))
    create_tower_segment(
        bm=bm_dist,
        xf=dxf,
        width=dcfg["width"],
        depth=dcfg["depth"],
        base_z=0.0,
        height=dcfg["height"],
        wall_thickness=1.6,
        rng=rng,
        bays_per_face=1,
        sill_z=12.0,
        has_tracery=False,
        broken_top=True,
        top_corner_bias=(1.0, 0.65, 0.85, 0.45),
        add_buttresses=False,
    )
    objs.append(create_mesh_object("Tower_Distant_MistRuin", bm_dist, col, mat=mats["MAT_Limestone_Eroded"]))

    return objs


def build_all_architecture(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
    preset: str = "balanced",
) -> List[bpy.types.Object]:
    """Construct all Gothic sanctuary architectural zones."""
    objs: List[bpy.types.Object] = []
    objs.extend(_build_left_front_tower(cols, mats, preset))
    objs.extend(_build_left_rear_tower(cols, mats, preset))
    objs.extend(_build_right_rear_tower(cols, mats, preset))
    objs.extend(_build_right_front_tower(cols, mats, preset))
    objs.extend(_build_rear_arcade(cols, mats, preset))
    objs.extend(_build_connecting_walls(cols, mats, preset))
    return objs
