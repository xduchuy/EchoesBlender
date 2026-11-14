"""Terrain, stratified limestone cliffs, courtyard, diagonal causeway, rubble, and reeds."""

import math
import random
from typing import Dict, List, Tuple

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector, noise

from config import LAYOUT
from geometry_utils import (
    add_box_to_bmesh,
    apply_coherent_stone_weathering,
    create_mesh_object,
    get_rng,
    instance_mesh_object,
)
from gothic_architecture import create_pointed_arch, create_ruin_cluster


def _fbm(p: Vector, octaves: int = 4, lacunarity: float = 2.05, gain: float = 0.5) -> float:
    """Deterministic multi-octave Perlin noise using mathutils.noise."""
    val = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        val += noise.noise(p * freq) * amp
        norm += amp
        amp *= gain
        freq *= lacunarity
    return val / max(1e-5, norm)


def _ridge_fbm(p: Vector, octaves: int = 4) -> float:
    """Ridged multifractal noise for sharp rocky limestone cliffs."""
    val = 0.0
    amp = 0.55
    freq = 1.0
    for _ in range(octaves):
        n = 1.0 - abs(noise.noise(p * freq))
        val += (n * n) * amp
        amp *= 0.5
        freq *= 2.1
    return val


def _build_cliff_mass(
    name: str,
    col: bpy.types.Collection,
    mat: bpy.types.Material,
    bounds_x: Tuple[float, float],
    bounds_y: Tuple[float, float],
    grid_n: int,
    height_fn,
    seed_off: Tuple[float, float, float],
    smooth: bool = False,
) -> bpy.types.Object:
    """Generate a stratified rocky cliff mesh from a grid with sharp stepped limestone ledges."""
    bm = bmesh.new()
    x0, x1 = bounds_x
    y0, y1 = bounds_y
    nx = grid_n
    ny = grid_n

    grid: List[List[bmesh.types.BMVert]] = []
    off = Vector(seed_off)
    for iy in range(ny + 1):
        ty = iy / ny
        y = y0 + (y1 - y0) * ty
        row = []
        for ix in range(nx + 1):
            tx = ix / nx
            x = x0 + (x1 - x0) * tx
            z_raw = height_fn(x, y, tx, ty)
            if z_raw > -2.5:
                p = Vector((x * 0.055, y * 0.055, 0.0)) + off
                broad = _fbm(p, octaves=4) * 3.8
                ridge = _ridge_fbm(p * 1.65 + Vector((4.2, -3.1, 1.0)), octaves=4) * 6.4
                z = z_raw + broad + ridge
                # Sharp stepped limestone strata ledges (finer 1.4m geological benches)
                if z > 0.6:
                    step = 1.45
                    terr = math.floor(z / step) * step
                    frac = (z - terr) / step
                    sharp = frac ** 2.6
                    z = terr + step * (0.14 * frac + 0.86 * sharp)
            else:
                z = z_raw
            # Horizontal angular rock overhang / crag perturbation
            dx = noise.noise(Vector((x * 0.11, y * 0.11, z * 0.14)) + off) * 1.5
            dy = noise.noise(Vector((x * 0.11 + 7.1, y * 0.11, z * 0.14)) + off) * 1.5
            row.append(bm.verts.new((x + dx, y + dy, z)))
        grid.append(row)

    for iy in range(ny):
        for ix in range(nx):
            v00 = grid[iy][ix]
            v10 = grid[iy][ix + 1]
            v11 = grid[iy + 1][ix + 1]
            v01 = grid[iy + 1][ix]
            try:
                bm.faces.new([v00, v10, v11, v01])
            except ValueError:
                pass

    return create_mesh_object(name, bm, col, mat=mat, smooth=smooth)


def build_terrain_and_cliffs(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
    terrain_subdiv: int = 80,
    cliff_subdiv: int = 44,
) -> List[bpy.types.Object]:
    """Build basin floor, asymmetrical left/right foreground cliffs, midground crags, and distant mountains."""
    objs: List[bpy.types.Object] = []

    # 1. Underwater seabed floor (keeps water murky and creates shallow edges near courtyard)
    bm_bed = bmesh.new()
    nx, ny = max(24, terrain_subdiv // 2), max(24, terrain_subdiv // 2)
    x0, x1 = -160.0, 160.0
    y0, y1 = -130.0, 220.0
    bed_grid = []
    for iy in range(ny + 1):
        y = y0 + (y1 - y0) * (iy / ny)
        row = []
        for ix in range(nx + 1):
            x = x0 + (x1 - x0) * (ix / nx)
            d_center = math.hypot(x, y - 2.0)
            # Shallow near courtyard (-0.8m), deeper in channels (-4.5m)
            base_z = -0.9 - 3.6 * min(1.0, max(0.0, (d_center - 16.0) / 35.0))
            z = base_z + _fbm(Vector((x * 0.05, y * 0.05, 0.0)), 3) * 0.7
            row.append(bm_bed.verts.new((x, y, z)))
        bed_grid.append(row)
    for iy in range(ny):
        for ix in range(nx):
            bm_bed.faces.new([bed_grid[iy][ix], bed_grid[iy][ix + 1], bed_grid[iy + 1][ix + 1], bed_grid[iy + 1][ix]])
    objs.append(create_mesh_object("Terrain_Seabed", bm_bed, cols["01_TERRAIN"], mat=mats["MAT_Ground_Mud"], smooth=True))

    # 2. Left Foreground Stratified Cliff (frames u=0.00..0.24, v=0.45..1.00 without blocking Left Colonnade!)
    def left_cliff_h(x: float, y: float, tx: float, ty: float) -> float:
        # Shoreline runs diagonally from (-13, -60) back to (-25, -22)
        shore_x = -12.5 - 15.0 * (ty ** 1.05) - 3.5 * math.sin(y * 0.11)
        if x > shore_x + 2.5 or y > -14.0:
            return -4.5
        t_in = max(0.0, min(1.0, (shore_x + 2.5 - x) / 22.0))
        y_fade = max(0.0, min(1.0, (-14.0 - y) / 28.0))
        return -4.5 + (23.5 * (t_in ** 0.72) + 4.5 * (1.0 - ty)) * (y_fade ** 0.75)

    objs.append(
        _build_cliff_mass(
            "Cliff_Left_Foreground",
            cols["02_CLIFFS"],
            mats["MAT_Rock_Cliff"],
            (-64.0, -10.0),
            (-82.0, -12.0),
            cliff_subdiv,
            left_cliff_h,
            (10.0, 20.0, 0.0),
            smooth=True,
        )
    )

    # 3. Right Foreground Stratified Cliff (frames u=0.80..1.00, v=0.35..1.00)
    def right_cliff_h(x: float, y: float, tx: float, ty: float) -> float:
        shore_x = 32.0 + 18.0 * (ty ** 0.95) + 4.5 * math.cos(y * 0.08)
        if x < shore_x - 2.5:
            return -4.5
        t_in = max(0.0, min(1.0, (x - (shore_x - 2.5)) / 24.0))
        edge_y = min(1.0, (1.0 - ty) * 2.4)
        return -4.5 + (25.0 * (t_in ** 0.76) + 3.0 * (1.0 - ty)) * edge_y

    objs.append(
        _build_cliff_mass(
            "Cliff_Right_Foreground",
            cols["02_CLIFFS"],
            mats["MAT_Rock_Cliff"],
            (28.0, 92.0),
            (-78.0, 24.0),
            cliff_subdiv,
            right_cliff_h,
            (45.0, -15.0, 3.0),
            smooth=True,
        )
    )

    # 4. Left Midground Jagged Crags (multi-peaked dark coastal ridge behind Left Bastion u~0.02..0.18)
    def left_crag_h(x: float, y: float, tx: float, ty: float) -> float:
        d1 = math.hypot((x - (-78.0)) * 0.95, (y - 46.0) * 1.15)
        d2 = math.hypot((x - (-60.0)) * 1.25, (y - 40.0) * 1.25)
        d3 = math.hypot((x - (-88.0)) * 1.0, (y - 54.0) * 1.1)
        p1 = max(0.0, 1.0 - d1 / 24.0) ** 1.2
        p2 = max(0.0, 1.0 - d2 / 16.0) ** 1.3
        p3 = max(0.0, 1.0 - d3 / 22.0) ** 1.15
        return -4.2 + 24.0 * p1 + 17.5 * p2 + 21.0 * p3

    objs.append(
        _build_cliff_mass(
            "Cliff_Left_MidCrags",
            cols["02_CLIFFS"],
            mats["MAT_Rock_Dark"],
            (-112.0, -40.0),
            (22.0, 78.0),
            max(48, cliff_subdiv - 8),
            left_crag_h,
            (-30.0, 42.0, 5.0),
            smooth=False,
        )
    )

    # 5. Distant Mountains & Coastal Headlands (Left & far-Right, keeping central sea & LeftRear skyline open)
    def dist_left_h(x: float, y: float, tx: float, ty: float) -> float:
        rx = max(0.0, min(1.0, (-x - 54.0) / 95.0))
        ry = math.sin(ty * math.pi)
        return -3.0 + 26.0 * (rx ** 0.78) * ry

    objs.append(
        _build_cliff_mass(
            "Mountains_Distant_Left",
            cols["01_TERRAIN"],
            mats["MAT_Rock_Dark"],
            (-245.0, -52.0),
            (105.0, 245.0),
            max(28, terrain_subdiv // 3),
            dist_left_h,
            (-90.0, 130.0, 0.0),
            smooth=True,
        )
    )

    def dist_right_h(x: float, y: float, tx: float, ty: float) -> float:
        rx = max(0.0, min(1.0, (x - 88.0) / 110.0))
        ry = math.sin(ty * math.pi)
        return -3.0 + 18.0 * (rx ** 0.85) * ry

    objs.append(
        _build_cliff_mass(
            "Mountains_Distant_Right",
            cols["01_TERRAIN"],
            mats["MAT_Rock_Dark"],
            (84.0, 250.0),
            (125.0, 250.0),
            max(26, terrain_subdiv // 3),
            dist_right_h,
            (120.0, 140.0, 2.0),
            smooth=True,
        )
    )

    # 6. Sculpted jagged limestone boulders along cliff bases (proper normal_update + multi-octave crag displacement!)
    rng = get_rng("cliff_outcrops")
    bm_out = bmesh.new()
    boulder_spots = [
        (-15.5, -52.5, 0.2, 2.4),
        (-20.0, -45.5, 0.9, 2.9),
        (-23.5, -36.5, 1.5, 2.7),
        (35.5, -39.0, 0.4, 2.5),
        (40.5, -27.0, 1.3, 3.0),
        (45.5, -14.0, 2.0, 3.3),
    ]
    for bi, (bx, by, bz, brad) in enumerate(boulder_spots):
        ret = bmesh.ops.create_icosphere(
            bm_out,
            subdivisions=3,
            radius=brad,
            matrix=Matrix.Translation((bx, by, bz)) @ Matrix.Diagonal((1.4, 1.1, 0.68, 1.0)),
        )
        bm_out.normal_update()
        off_b = Vector((bi * 7.3, -bi * 3.1, 1.9))
        for v in ret["verts"]:
            p = Vector((v.co.x * 0.42, v.co.y * 0.42, v.co.z * 0.85)) + off_b
            disp = (_ridge_fbm(p, octaves=3) - 0.32) * (brad * 0.95)
            v.co += v.normal * disp
    objs.append(create_mesh_object("Cliffs_Foreground_Outcrops", bm_out, cols["02_CLIFFS"], mat=mats["MAT_Rock_Cliff"], smooth=False))

    return objs


def build_courtyard_and_causeway(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
) -> List[bpy.types.Object]:
    """Build circular flooded courtyard, central statue island, diagonal stone causeway, and scale figure."""
    rng = get_rng("courtyard_causeway")
    col = cols["04_COURTYARD"]
    objs: List[bpy.types.Object] = []

    ccfg = LAYOUT["courtyard"]
    cx, cy, _ = ccfg["center"]
    ring_r = ccfg["ring_radius"]
    ring_w = ccfg["ring_width"]
    ring_h = ccfg["ring_height"]

    # 1. Courtyard stone ring & broken inner rim slabs
    bm_ring = bmesh.new()
    n_arcs = 44
    for i in range(n_arcs):
        a0 = (i / n_arcs) * math.tau
        a1 = ((i + 0.92) / n_arcs) * math.tau
        am = 0.5 * (a0 + a1)
        px = cx + ring_r * math.cos(am)
        py = cy + ring_r * math.sin(am)
        # Break opening where causeway enters around -90 deg (3*pi/2) and side drainage channels
        ang_deg = math.degrees(am) % 360.0
        if 263.0 < ang_deg < 277.0:
            continue
        if rng.random() < 0.12:
            # Sunken / missing stone rim block
            z_top = rng.uniform(-0.25, 0.08)
        else:
            z_top = ring_h + rng.uniform(-0.08, 0.08)
        seg_len = (math.tau * ring_r / n_arcs) * 0.96
        z_bot = -1.4
        h = z_top - z_bot
        add_box_to_bmesh(
            bm_ring,
            (px, py, z_bot + h * 0.5),
            (seg_len, ring_w + rng.uniform(-0.1, 0.15), h),
            rot_euler=(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), am + math.pi * 0.5),
            bevel_width=0.04,
        )

    # Central statue island platform
    n_isl = 24
    ir = ccfg["island_radius"]
    for i in range(n_isl):
        am = (i / n_isl) * math.tau
        px = cx + (ir * 0.72) * math.cos(am)
        py = cy + (ir * 0.72) * math.sin(am)
        z_top = ccfg["island_height"] + rng.uniform(-0.12, 0.06)
        add_box_to_bmesh(
            bm_ring,
            (px, py, (z_top - 1.5) * 0.5),
            (1.6, 2.2, z_top + 1.5),
            rot_euler=(0.0, 0.0, am),
            bevel_width=0.05,
        )

    # Submerged courtyard flagstones visible just beneath shallow water
    for _ in range(75):
        a = rng.uniform(0.0, math.tau)
        r = rng.uniform(4.5, ring_r - 1.2)
        px = cx + r * math.cos(a)
        py = cy + r * math.sin(a)
        pz = rng.uniform(-0.32, 0.04)
        add_box_to_bmesh(
            bm_ring,
            (px, py, pz),
            (rng.uniform(1.0, 2.1), rng.uniform(0.9, 1.8), 0.32),
            rot_euler=(rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04), rng.uniform(0.0, math.tau)),
            bevel_width=0.03,
        )

    apply_coherent_stone_weathering(bm_ring, amp=0.035, freq=0.6)
    objs.append(create_mesh_object("Courtyard_Stone_Plaza", bm_ring, col, mat=mats["MAT_Limestone_Wet"]))

    # 2. Foreground Diagonal Causeway (runs from Y=-76 to Y=-11.4 along X=0)
    cw_cfg = LAYOUT["causeway"]
    y_start = cw_cfg["start_xy"][1]
    y_end = cw_cfg["end_xy"][1]
    cw_w = cw_cfg["width"]
    bm_cw = bmesh.new()

    # Solid submerged core foundation so no floating gap ever appears under cracks
    total_len = y_end - y_start
    add_box_to_bmesh(
        bm_cw,
        (0.0, 0.5 * (y_start + y_end), -1.45),
        (cw_w * 0.92, total_len, 2.4),
        bevel_width=0.05,
    )

    # Worn stone block paving courses with subtle flooded dip in middle (Y=-34..-22)
    cur_y = y_start
    while cur_y < y_end:
        step_y = rng.uniform(1.15, 1.85)
        ym = cur_y + step_y * 0.5
        # Shallow water dip toward courtyard junction
        dip = 0.34 * math.exp(-((ym + 25.0) / 9.5) ** 2)
        top_z = cw_cfg["top_z"] - dip + rng.uniform(-0.04, 0.04)

        # Two or three slabs across width
        n_across = rng.choice([2, 3])
        slab_w = cw_w / n_across
        for si in range(n_across):
            if rng.random() < 0.06 and abs(ym + 41.5) > 3.0:
                # Missing damaged slab edge!
                continue
            sx = -cw_w * 0.5 + (si + 0.5) * slab_w + rng.uniform(-0.04, 0.04)
            w_adj = slab_w * rng.uniform(0.92, 1.03)
            l_adj = step_y * rng.uniform(0.92, 0.98)
            h_slab = top_z + 1.0
            add_box_to_bmesh(
                bm_cw,
                (sx, ym, top_z - h_slab * 0.5),
                (w_adj, l_adj, h_slab),
                rot_euler=(rng.uniform(-0.025, 0.025), rng.uniform(-0.025, 0.025), rng.uniform(-0.03, 0.03)),
                bevel_width=0.04,
            )

        # Occasional low stone kerb block along causeway outer edge
        for side in (-1.0, 1.0):
            if rng.random() < 0.55:
                kx = side * (cw_w * 0.5 + 0.16)
                kz = top_z + rng.uniform(0.05, 0.18)
                add_box_to_bmesh(
                    bm_cw,
                    (kx, ym, kz - 0.35),
                    (0.42, step_y * 0.85, 0.72),
                    rot_euler=(rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)),
                    bevel_width=0.035,
                )
        cur_y += step_y

    apply_coherent_stone_weathering(bm_cw, amp=0.028, freq=0.85, seed_offset=(0.0, -40.0, 0.0))
    objs.append(create_mesh_object("Causeway_Stone_Bridge", bm_cw, col, mat=mats["MAT_Limestone_Base"]))

    # 3. Subtle human-scale cloaked pilgrim figure on the causeway (1.75m tall)
    fig_y = cw_cfg["figure_y"]
    bm_fig = bmesh.new()
    # Cloak cone + torso + hooded head
    bmesh.ops.create_cone(
        bm_fig,
        cap_ends=True,
        cap_tris=False,
        segments=12,
        radius1=0.34,
        radius2=0.18,
        depth=1.35,
        matrix=Matrix.Translation((0.0, 0.0, 0.68)),
    )
    bmesh.ops.create_uvsphere(
        bm_fig,
        u_segments=10,
        v_segments=8,
        radius=0.16,
        matrix=Matrix.Translation((0.0, 0.03, 1.52)),
    )
    objs.append(
        create_mesh_object(
            "Causeway_Scale_Figure",
            bm_fig,
            col,
            mat=mats["MAT_Dark_Silhouette"],
            location=(-0.15, fig_y, 0.42),
            rotation_deg=(0.0, 0.0, 8.0),
            smooth=True,
        )
    )

    return objs


def build_flooded_rubble_and_reeds(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
    rubble_scale: float = 1.0,
) -> List[bpy.types.Object]:
    """Populate foreground water & cliff shorelines with ruined shrines, tilted slabs, and reed tufts."""
    rng = get_rng("rubble_reeds")
    col_rub = cols["08_RUBBLE"]
    col_veg = cols["09_VEGETATION"]
    objs: List[bpy.types.Object] = []

    # 1. Left foreground miniature ruined shrines / crypts embedded along left cliff shoreline (u~0.14..0.22)
    shrine_spots = [
        ((-15.0, -43.0, -0.35), 35.0, 0.90),
        ((-20.0, -35.5, 0.35), 24.0, 0.80),
    ]
    for idx, (loc, rot_z, sc) in enumerate(shrine_spots):
        bm_sh = bmesh.new()
        add_box_to_bmesh(bm_sh, (0.0, 0.0, 1.2 * sc), (3.0 * sc, 2.6 * sc, 2.4 * sc), bevel_width=0.05)
        add_box_to_bmesh(
            bm_sh,
            (0.0, 0.0, 2.75 * sc),
            (2.2 * sc, 2.8 * sc, 1.6 * sc),
            rot_euler=(0.0, math.radians(45.0), 0.0),
            bevel_width=0.04,
        )
        create_pointed_arch(
            bm_sh,
            Matrix.Translation((0.0, -1.45 * sc, 0.0)),
            span=1.5 * sc,
            spring_z=0.9 * sc,
            apex_z=2.05 * sc,
            arch_thickness=0.42 * sc,
            depth_y=0.55 * sc,
            segments_per_side=5,
            rng=rng,
        )
        apply_coherent_stone_weathering(bm_sh, amp=0.07, freq=0.7)
        objs.append(
            create_mesh_object(
                f"Ruin_Shore_Shrine_{idx+1}",
                bm_sh,
                col_rub,
                mat=mats["MAT_Limestone_Wet"],
                location=loc,
                rotation_deg=(rng.uniform(-6, 6), rng.uniform(-8, 8), rot_z),
            )
        )

    # 2. Prominent tilted broken pediment/cornice & column fragments in foreground water (u~0.52..0.88, v~0.76..0.96)
    tilted_blocks = [
        ((13.5, -39.5, -0.25), (14.0, -18.0, 28.0), (4.2, 3.6, 1.6)),
        ((23.0, -37.5, -0.35), (-10.0, 16.0, -18.0), (3.8, 3.0, 1.4)),
        ((28.5, -30.0, -0.20), (8.0, -12.0, 42.0), (3.8, 2.8, 1.5)),
        ((-9.5, -43.0, -0.25), (-12.0, 10.0, 15.0), (3.4, 2.5, 1.3)),
        ((-15.0, -29.0, -0.20), (6.0, 14.0, -25.0), (3.6, 2.6, 1.4)),
    ]
    for idx, (loc, rot_d, sz) in enumerate(tilted_blocks):
        bm_tb = bmesh.new()
        add_box_to_bmesh(bm_tb, (0.0, 0.0, 0.0), sz, bevel_width=0.06)
        # Stepped entablature moldings & broken stone ribs
        add_box_to_bmesh(bm_tb, (0.0, 0.0, sz[2] * 0.42), (sz[0] * 1.14, sz[1] * 1.14, 0.34), bevel_width=0.04)
        add_box_to_bmesh(bm_tb, (0.0, 0.0, sz[2] * 0.65), (sz[0] * 0.90, sz[1] * 0.90, 0.28), bevel_width=0.04)
        # Ribbed cornice teeth along top
        for ri in range(-2, 3):
            add_box_to_bmesh(bm_tb, (ri * sz[0] * 0.2, 0.0, sz[2] * 0.85), (0.35, sz[1] * 0.85, 0.32), bevel_width=0.03)
        apply_coherent_stone_weathering(bm_tb, amp=0.06, freq=0.65, seed_offset=(idx * 5.0, 0.0, 0.0))
        objs.append(
            create_mesh_object(
                f"Ruin_Submerged_Slab_{idx+1}",
                bm_tb,
                col_rub,
                mat=mats["MAT_Submerged_Stone"],
                location=loc,
                rotation_deg=rot_d,
            )
        )

    # Toppled broken column drums protruding from water
    for ci, (cx_col, cy_col, cz_col, r_col, rot_c) in enumerate([
        (16.0, -42.5, -0.2, 0.68, (76.0, 12.0, 35.0)),
        (-11.0, -37.0, -0.25, 0.62, (82.0, -8.0, -40.0)),
        (26.0, -33.5, -0.2, 0.65, (72.0, 15.0, 15.0)),
    ]):
        bm_col = bmesh.new()
        bmesh.ops.create_cone(bm_col, cap_ends=True, cap_tris=False, segments=14, radius1=r_col, radius2=r_col * 0.94, depth=3.2)
        apply_coherent_stone_weathering(bm_col, amp=0.04, freq=1.2, seed_offset=(ci * 3.0, 1.0, 0.0))
        objs.append(
            create_mesh_object(
                f"Ruin_Fallen_Column_{ci+1}",
                bm_col,
                col_rub,
                mat=mats["MAT_Submerged_Stone"],
                location=(cx_col, cy_col, cz_col),
                rotation_deg=rot_c,
                smooth=True,
            )
        )

    # 3. Coherent rubble clusters near tower foundations and collapsed walls
    cluster_spots = [
        ("Rubble_LeftFront_Base", (-18.0, -10.5, -0.2), 10, 5.5, True),
        ("Rubble_RightFront_Base", (17.0, -17.0, -0.2), 12, 6.0, True),
        ("Rubble_Courtyard_Left", (-11.0, -3.5, -0.2), 7, 3.8, False),
        ("Rubble_Courtyard_Right", (11.5, -4.5, -0.2), 7, 3.8, False),
        ("Rubble_Channel_Left", (-16.0, -24.0, -0.3), 8, 5.0, True),
        ("Rubble_Channel_Right", (25.0, -28.0, -0.3), 8, 5.0, False),
    ]
    for cname, cloc, cnt, rad, has_arch in cluster_spots:
        c_adj = max(3, int(round(cnt * rubble_scale)))
        objs.append(
            create_ruin_cluster(
                cname,
                cloc,
                col_rub,
                mats["MAT_Submerged_Stone"],
                rng,
                count=c_adj,
                radius=rad,
                include_broken_arch=has_arch,
            )
        )

    # 4. Instanced reed / tall grass tufts along flooded edges & foreground shoreline
    bm_tuft = bmesh.new()
    for bi in range(7):
        ang = (bi / 7.0) * math.tau + rng.uniform(-0.2, 0.2)
        tilt = rng.uniform(0.18, 0.45)
        h = rng.uniform(0.7, 1.35)
        bx = math.cos(ang) * 0.14
        by = math.sin(ang) * 0.14
        v0 = bm_tuft.verts.new((bx - 0.04, by, 0.0))
        v1 = bm_tuft.verts.new((bx + 0.04, by, 0.0))
        v2 = bm_tuft.verts.new((bx + math.cos(ang) * tilt, by + math.sin(ang) * tilt, h))
        bm_tuft.faces.new([v0, v1, v2])
    tuft_mesh = bpy.data.meshes.new("Reed_Tuft_Mesh")
    bm_tuft.to_mesh(tuft_mesh)
    bm_tuft.free()
    tuft_mesh.materials.append(mats["MAT_Ground_Grass"])

    reed_zones = [
        (-8.5, -16.0, 5.0),
        (-15.0, -30.0, 6.0),
        (-22.0, -48.0, 5.0),
        (8.5, -18.0, 5.0),
        (16.0, -34.0, 6.0),
        (-2.5, -38.0, 3.0),
        (2.5, -28.0, 3.0),
    ]
    n_tufts = max(4, int(round(12 * rubble_scale)))
    for zi, (zx, zy, zrad) in enumerate(reed_zones):
        for ti in range(n_tufts):
            px = zx + rng.uniform(-zrad, zrad)
            py = zy + rng.uniform(-zrad, zrad)
            pz = rng.uniform(-0.2, 0.05)
            sc = rng.uniform(0.8, 1.5)
            objs.append(
                instance_mesh_object(
                    f"Reed_{zi}_{ti}",
                    tuft_mesh,
                    col_veg,
                    location=(px, py, pz),
                    rotation_deg=(0.0, 0.0, rng.uniform(0.0, 360.0)),
                    scale=(sc, sc, sc),
                )
            )

    return objs
