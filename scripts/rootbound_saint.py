"""The Rootbound Saint — Monumental Gothic Statue Complex for EchoesBlender V3.

Builds a 5-layer dark-fantasy Gothic monument in Blender 5.3+:
  Layer 1 (SAINT_STATUE)   : Saint_Head, Saint_Face, Saint_Hood, Saint_Torso,
                             Saint_Hands, Saint_Robe, Saint_Halo
  Layer 2 (SAINT_PEDESTAL) : Pedestal_Base, Pedestal_Panels, Pedestal_Cornices
  Layer 3 (SAINT_STAIRS)   : Stairs_Left, Stairs_Right, Stairs_Landings
  Layer 4 (SAINT_TERRACE)  : Terrace_Floor, Terrace_OuterWall, Terrace_Balustrades
  Layer 5 (SAINT_ROOTS / SAINT_DEBRIS / SAINT_COLLISION):
                             Root_Primary, Root_Secondary, Root_Tendrils,
                             Rubble, Broken_Stone, Fallen_Parapets,
                             Collision_Terrace, Collision_Stairs, Collision_Pedestal
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector, noise

SCRIPTS_DIR = str(Path(__file__).resolve().parent)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from config import LAYOUT, QUALITY_PRESETS
from geometry_utils import (
    add_box_to_bmesh,
    apply_coherent_stone_weathering,
    apply_sharp_edge_shading,
    assign_material,
    create_mesh_object,
    get_or_create_collection,
    get_rng,
    reset_scene,
    setup_collections,
)
from materials import create_all_materials


SAINT_SUBCOLLECTIONS = (
    "SAINT_STATUE",
    "SAINT_PEDESTAL",
    "SAINT_STAIRS",
    "SAINT_TERRACE",
    "SAINT_ROOTS",
    "SAINT_DEBRIS",
    "SAINT_COLLISION",
)


def clear_existing_rootbound_saint(include_legacy_statue: bool = True) -> None:
    """Idempotently remove any prior Rootbound Saint (and optional legacy statue) objects."""
    col_names = ["05_ROOTBOUND_SAINT", *SAINT_SUBCOLLECTIONS]
    if include_legacy_statue:
        col_names.append("05_STATUE")

    to_delete = set()
    for cname in col_names:
        col = bpy.data.collections.get(cname)
        if col:
            for obj in list(col.all_objects):
                to_delete.add(obj)

    for obj_name in ("ROOTBOUND_SAINT_ROOT", "Statue_Pedestal", "Statue_Central_Figure"):
        if not include_legacy_statue and obj_name.startswith("Statue_"):
            continue
        obj = bpy.data.objects.get(obj_name)
        if obj:
            to_delete.add(obj)

    for obj in list(to_delete):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass


def _make_group_empty(
    name: str,
    parent: Optional[bpy.types.Object],
    col: bpy.types.Collection,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 1.2
    empty.location = location
    empty.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    col.objects.link(empty)
    if parent is not None:
        empty.parent = parent
    return empty


def _finalize_part(
    name: str,
    bm: bmesh.types.BMesh,
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mat: Optional[bpy.types.Material],
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    smooth: bool = True,
    sharp_angle_deg: Optional[float] = 42.0,
    subsurf_level: int = 0,
) -> bpy.types.Object:
    obj = create_mesh_object(
        name=name,
        bm=bm,
        col=col,
        mat=mat,
        location=location,
        rotation_deg=rotation_deg,
        smooth=smooth,
        sharp_angle_deg=sharp_angle_deg,
    )
    obj.parent = parent
    if subsurf_level > 0:
        mod = obj.modifiers.new(name="Subsurf", type="SUBSURF")
        mod.levels = subsurf_level
        mod.render_levels = subsurf_level
    return obj


def _add_polygonal_frustum(
    bm: bmesh.types.BMesh,
    z0: float,
    z1: float,
    r0: float,
    r1: float,
    segs: int = 8,
    phase_rad: float = 0.0,
    center_xy: Tuple[float, float] = (0.0, 0.0),
    cap_bottom: bool = True,
    cap_top: bool = True,
) -> None:
    cx, cy = center_xy
    bot_vs = []
    top_vs = []
    for i in range(segs):
        ang = (i / segs) * math.tau + phase_rad
        ca, sa = math.cos(ang), math.sin(ang)
        bot_vs.append(bm.verts.new((cx + r0 * ca, cy + r0 * sa, z0)))
        top_vs.append(bm.verts.new((cx + r1 * ca, cy + r1 * sa, z1)))
    if cap_bottom:
        try:
            bm.faces.new(list(reversed(bot_vs)))
        except ValueError:
            pass
    if cap_top:
        try:
            bm.faces.new(top_vs)
        except ValueError:
            pass
    for i in range(segs):
        j = (i + 1) % segs
        try:
            bm.faces.new([bot_vs[i], bot_vs[j], top_vs[j], top_vs[i]])
        except ValueError:
            pass


def _add_tapered_capsule_segment(
    bm: bmesh.types.BMesh,
    p0: Vector,
    p1: Vector,
    r0: float,
    r1: float,
    segs: int = 10,
) -> None:
    """Create a smooth tapered rounded cylinder segment (for fingers/joints)."""
    axis = p1 - p0
    length = axis.length
    if length < 1e-5:
        return
    t = axis / length
    ref = Vector((0.0, 0.0, 1.0)) if abs(t.z) < 0.92 else Vector((1.0, 0.0, 0.0))
    u = t.cross(ref).normalized()
    v = u.cross(t).normalized()

    steps = 5
    rings: List[List[bmesh.types.BMVert]] = []
    for is_i in range(steps + 1):
        f = is_i / steps
        c = p0.lerp(p1, f)
        r = r0 * (1.0 - f) + r1 * f
        if is_i == 0:
            r *= 0.72
        elif is_i == steps:
            r *= 0.62
        ring = []
        for k in range(segs):
            ang = (k / segs) * math.tau
            off = (u * math.cos(ang) + v * math.sin(ang)) * r
            ring.append(bm.verts.new(c + off))
        rings.append(ring)

    for is_i in range(steps):
        for k in range(segs):
            kn = (k + 1) % segs
            bm.faces.new([rings[is_i][k], rings[is_i][kn], rings[is_i + 1][kn], rings[is_i + 1][k]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


# ==============================================================================
# LAYER 1: HOLY WOMAN STATUE (SAINT_STATUE)
# ==============================================================================

def _build_saint_face_and_head(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mat_stone: bpy.types.Material,
    ped_top_z: float,
    fig_h: float,
    subsurf_level: int,
) -> Tuple[bpy.types.Object, bpy.types.Object]:
    """Build Saint_Head (draped wimple gorget & recessed skull) and Saint_Face (carved forward-lit face)."""
    head_base_z = ped_top_z + fig_h * 0.640  # Anchors smoothly inside upper chest
    head_center_z = ped_top_z + fig_h * 0.782  # Classical 7.5-head proportion tucked cleanly under hood arch

    # 1. Saint_Head: Recessed anatomical neck + delicate catenary chest wimple pleats -> rounded skull core.
    bm_head = bmesh.new()
    n_u = 44
    n_v = 40
    rings: List[List[bmesh.types.BMVert]] = []
    skull_top_z = head_center_z + 0.60  # Stays cleanly INSIDE Saint_Hood crown dome
    for iv in range(n_v + 1):
        tv = iv / n_v
        z = head_base_z + tv * (skull_top_z - head_base_z)
        t_cb = max(0.0, min(1.0, (tv - 0.42) / 0.18))
        cran_blend = t_cb * t_cb * (3.0 - 2.0 * t_cb)

        # Narrow anatomical throat recessed BEHIND the chin so the jawline casts clean sculptural under-chin relief!
        u_w = min(1.0, tv / 0.48)
        wimple_rx = 0.62 - 0.34 * (u_w ** 0.72)
        wimple_ry = 0.42 - 0.18 * (u_w ** 0.72)

        u_cr = max(0.0, (tv - 0.42) / 0.58)
        # Dome closes smoothly down to 0.05m apex so zero top-disk edge ever pokes out through Saint_Hood
        skull_env = math.sin(min(1.0, 0.22 + u_cr * 0.78) * math.pi * 0.92)
        top_close = 1.0 - 0.85 * (max(0.0, (u_cr - 0.75) / 0.25) ** 1.4)
        cran_rx = (0.28 + 0.16 * skull_env) * top_close
        cran_ry = (0.26 + 0.16 * skull_env) * top_close

        rx = wimple_rx * (1.0 - cran_blend) + cran_rx * cran_blend
        ry = wimple_ry * (1.0 - cran_blend) + cran_ry * cran_blend
        y_off = -0.06 * (1.0 - cran_blend) - 0.16 * cran_blend

        t_we = max(0.0, min(1.0, (tv - 0.32) / 0.14))
        wimple_env = max(0.0, 1.0 - (t_we * t_we * (3.0 - 2.0 * t_we)))
        wimple_wave = 0.11 * abs(math.sin(u_w * math.pi * 4.5)) * (1.0 - 0.35 * u_w) * wimple_env

        ring = []
        for iu in range(n_u):
            ang = (iu / n_u) * math.tau
            ca, sa = math.cos(ang), math.sin(ang)
            front_mask = max(0.0, -sa)
            u_dip = -0.22 * (front_mask ** 1.6) * (1.0 - 0.35 * u_w) * wimple_env
            r_mod = 1.0 + wimple_wave * (0.20 + 0.80 * front_mask)
            px = ca * rx * r_mod
            py = sa * ry * r_mod + y_off
            pz = z + u_dip
            ring.append(bm_head.verts.new((px, py, pz)))
        rings.append(ring)

    for iv in range(n_v):
        for iu in range(n_u):
            ju = (iu + 1) % n_u
            bm_head.faces.new([rings[iv][iu], rings[iv][ju], rings[iv + 1][ju], rings[iv + 1][iu]])
    bm_head.faces.new(list(reversed(rings[0])))
    bm_head.faces.new(rings[-1])

    bmesh.ops.recalc_face_normals(bm_head, faces=bm_head.faces[:])
    apply_coherent_stone_weathering(bm_head, amp=0.004, freq=2.0, seed_offset=(1.1, 2.2, 3.3))
    obj_head = _finalize_part(
        "Saint_Head",
        bm_head,
        col,
        parent,
        mat_stone,
        smooth=True,
        sharp_angle_deg=55.0,
        subsurf_level=max(1, subsurf_level),
    )

    # 2. Saint_Face: Full-scale classical face tightly cupped by hood brow & temple cheeks (no tall gap!).
    bm_face = bmesh.new()
    cols_u = 42
    rows_v = 44
    face_grid: List[List[bmesh.types.BMVert]] = []
    pitch = math.radians(10.0)
    cos_p, sin_p = math.cos(pitch), math.sin(pitch)

    for iv in range(rows_v + 1):
        v = (iv / rows_v) * 2.0 - 1.0  # -1.0 = chin/jaw -> +1.0 = upper forehead tucked under hood arch
        row = []
        for iu in range(cols_u + 1):
            u = (iu / cols_u) * 2.0 - 1.0
            abs_u = abs(u)

            jaw_taper = 0.28 * (max(0.0, -v) ** 1.40)
            temple_taper = 0.24 * (max(0.0, v) ** 1.35)
            width_env = 0.56 * (1.0 - jaw_taper - temple_taper)
            x = u * width_env
            z_local = v * 0.58

            rad2 = 0.82 * (u ** 2) + 0.72 * (v ** 2)
            dome = math.sqrt(max(0.0, 1.0 - min(1.0, rad2)))
            forehead_tuck = 0.28 * ((max(0.0, v - 0.18) / 0.82) ** 1.35)
            chin_tuck = 0.14 * ((max(0.0, -v - 0.55) / 0.45) ** 1.4)
            temple_tuck = 0.13 * (u ** 2)
            # Curve forehead, chin & temple rims smoothly back into hood/wimple while projecting nose/brow forward
            y_depth = 0.48 * dome - 0.12 * (1.0 - dome) - forehead_tuck - chin_tuck - temple_tuck
            edge_fade = max(0.0, 1.0 - 0.85 * (u ** 2)) * max(0.0, 1.0 - 0.85 * (v ** 2))

            relief = 0.0

            # Forehead & supraorbital brow ridge (v ~ 0.22..0.56)
            brow_band = math.exp(-((v - 0.28) / 0.11) ** 2) * math.exp(-((abs_u - 0.22) / 0.34) ** 2)
            glabella = math.exp(-((v - 0.24) / 0.10) ** 2) * math.exp(-(u / 0.14) ** 2)
            forehead_dome = 0.048 * math.exp(-((v - 0.54) / 0.26) ** 2) * (1.0 - 0.5 * u * u)
            relief += 0.070 * brow_band + 0.054 * glabella + forehead_dome

            # Orbital eye sockets & serene downcast eyelids (abs_u ~ 0.28, v ~ 0.10)
            eye_dx = (abs_u - 0.28) / 0.14
            eye_dv = (v - 0.10) / 0.10
            eye_r2 = eye_dx * eye_dx + eye_dv * eye_dv
            socket_depth = -0.092 * math.exp(-eye_r2 * 1.4)
            upper_lid = 0.068 * math.exp(-((v - 0.125 + 0.015 * eye_dx) / 0.036) ** 2) * math.exp(-(eye_dx ** 2) * 1.4)
            lower_lid = 0.036 * math.exp(-((v - 0.055) / 0.030) ** 2) * math.exp(-(eye_dx ** 2) * 1.5)
            lid_crease = -0.034 * math.exp(-((v - 0.082) / 0.014) ** 2) * math.exp(-(eye_dx ** 2) * 1.6)
            relief += socket_depth + upper_lid + lower_lid + lid_crease

            # Classical straight slender nose bridge, tip, and nostril wings (v ~ -0.22..0.24)
            if -0.28 <= v <= 0.30:
                tn = (0.24 - v) / 0.44
                tn_c = min(1.0, max(0.0, tn))
                bridge_w = 0.078 + 0.052 * (tn_c ** 1.5)
                bridge_prof = math.sin(min(1.0, tn_c * 0.92) * math.pi * 0.58)
                nose_spine = (
                    (0.195 * bridge_prof + 0.036)
                    * math.exp(-((u / bridge_w) ** 2))
                    * math.exp(-max(0.0, v - 0.22) * 18.0)
                    * math.exp(-max(0.0, -0.21 - v) * 24.0)
                )
                ala = 0.066 * math.exp(-(((abs_u - 0.115) / 0.048) ** 2 + ((v + 0.175) / 0.044) ** 2))
                nostril_cut = -0.036 * math.exp(-(((abs_u - 0.078) / 0.032) ** 2 + ((v + 0.215) / 0.026) ** 2))
                relief += nose_spine + ala + nostril_cut

            # Malar cheekbone planes & gentle sub-malar contour
            cheek_bone = 0.068 * math.exp(-(((abs_u - 0.42) / 0.22) ** 2 + ((v + 0.08) / 0.18) ** 2))
            cheek_hollow = -0.038 * math.exp(-(((abs_u - 0.38) / 0.18) ** 2 + ((v + 0.36) / 0.16) ** 2))
            relief += cheek_bone + cheek_hollow

            # Philtrum & solemn closed lips (v ~ -0.38..-0.52)
            philtrum = -0.018 * math.exp(-(u / 0.042) ** 2) * math.exp(-((v + 0.29) / 0.055) ** 2)
            mouth_env = math.exp(-(u / 0.21) ** 2)
            cupid_dip = 0.015 * math.exp(-(u / 0.045) ** 2)
            upper_lip = 0.062 * mouth_env * math.exp(-((v + 0.385 + cupid_dip) / 0.032) ** 2)
            lower_lip = 0.068 * math.exp(-(u / 0.18) ** 2) * math.exp(-((v + 0.455) / 0.036) ** 2)
            mouth_line = -0.040 * mouth_env * math.exp(-((v + 0.418 - 0.016 * (u ** 2)) / 0.013) ** 2)
            relief += philtrum + upper_lip + lower_lip + mouth_line

            # Labiomental groove & rounded chin
            mentolabial = -0.032 * math.exp(-(u / 0.16) ** 2) * math.exp(-((v + 0.54) / 0.042) ** 2)
            chin_boss = 0.076 * math.exp(-(u / 0.21) ** 2) * math.exp(-((v + 0.68) / 0.13) ** 2)
            relief += mentolabial + chin_boss

            erode = 0.0025 * noise.noise(Vector((x * 5.0, v * 5.0, 1.7)))
            y_raw = -(y_depth + relief * edge_fade + erode)
            py = y_raw * cos_p - z_local * sin_p - 0.37
            pz = head_center_z + y_raw * sin_p + z_local * cos_p

            row.append(bm_face.verts.new((x, py, pz)))
        face_grid.append(row)

    for iv in range(rows_v):
        for iu in range(cols_u):
            bm_face.faces.new([
                face_grid[iv][iu],
                face_grid[iv][iu + 1],
                face_grid[iv + 1][iu + 1],
                face_grid[iv + 1][iu],
            ])

    back_grid: List[List[bmesh.types.BMVert]] = []
    for iv in range(rows_v + 1):
        row_b = []
        for iu in range(cols_u + 1):
            vf = face_grid[iv][iu].co
            row_b.append(bm_face.verts.new((vf.x * 0.72, 0.02, vf.z)))
        back_grid.append(row_b)

    for iv in range(rows_v):
        for iu in range(cols_u):
            bm_face.faces.new([
                back_grid[iv][iu],
                back_grid[iv + 1][iu],
                back_grid[iv + 1][iu + 1],
                back_grid[iv][iu + 1],
            ])

    for iu in range(cols_u):
        bm_face.faces.new([face_grid[0][iu], back_grid[0][iu], back_grid[0][iu + 1], face_grid[0][iu + 1]])
        bm_face.faces.new([face_grid[rows_v][iu], face_grid[rows_v][iu + 1], back_grid[rows_v][iu + 1], back_grid[rows_v][iu]])
    for iv in range(rows_v):
        bm_face.faces.new([face_grid[iv][0], face_grid[iv + 1][0], back_grid[iv + 1][0], back_grid[iv][0]])
        bm_face.faces.new([face_grid[iv][cols_u], back_grid[iv][cols_u], back_grid[iv + 1][cols_u], face_grid[iv + 1][cols_u]])

    bmesh.ops.recalc_face_normals(bm_face, faces=bm_face.faces[:])
    obj_face = _finalize_part(
        "Saint_Face",
        bm_face,
        col,
        parent,
        mat_stone,
        smooth=True,
        sharp_angle_deg=58.0,
        subsurf_level=max(1, subsurf_level),
    )
    return obj_head, obj_face


def _build_saint_hood(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mat_stone: bpy.types.Material,
    ped_top_z: float,
    fig_h: float,
    subsurf_level: int,
) -> bpy.types.Object:
    """Build close-fitting Gothic hood/mantle with broad draped shoulder shawl and smooth rounded crown dome."""
    hood_bot_z = ped_top_z + fig_h * 0.548
    hood_collar_z = ped_top_z + fig_h * 0.715
    hood_top_z = ped_top_z + fig_h * 0.848

    bm = bmesh.new()
    n_u = 48
    n_v = 48

    grid: List[List[bmesh.types.BMVert]] = []
    for iv in range(n_v + 1):
        tv = iv / n_v
        row = []

        # Almond-shaped face opening framing cheeks cleanly and closing gently over upper brow (tv=0.90)
        if tv < 0.36:
            u_low = tv / 0.36
            open_half_deg = 8.0 + 27.0 * (u_low ** 0.85)
        elif tv < 0.90:
            u_arch = (tv - 0.36) / 0.54
            open_half_deg = 35.0 * math.sqrt(max(0.0, 1.0 - (u_arch ** 1.85))) + 0.25
        else:
            open_half_deg = 0.25

        ang_start = math.radians(-90.0 + open_half_deg)
        ang_end = math.radians(270.0 - open_half_deg)

        if tv < 0.48:
            u_sh = tv / 0.48
            # Full curved bell-cape shoulders (stays 1.34m..0.88m over deltoids so torso never pokes through!)
            rx = 1.34 * math.cos(u_sh * math.pi * 0.27)
            ry = 0.84 * math.cos(u_sh * math.pi * 0.16)
            z_base = hood_bot_z + (hood_collar_z - hood_bot_z) * u_sh
        elif tv < 0.74:
            # Side cowl cradling cheeks, temples & brow with full protective depth OUTSIDE Saint_Face
            u_h = (tv - 0.48) / 0.26
            rx = 0.88 - 0.18 * (u_h ** 0.9)
            ry = 0.74 - 0.12 * (u_h ** 0.9)
            z_head_rim = hood_collar_z + (hood_top_z - hood_collar_z) * 0.72
            z_base = hood_collar_z + (z_head_rim - hood_collar_z) * u_h
        else:
            # Smooth rounded Gothic dome curving cleanly OVER the top of the forehead hairline to apex
            u_cr = (tv - 0.74) / 0.26
            dome_lat = u_cr * math.pi * 0.50
            dome_rad = math.cos(dome_lat) ** 0.95
            rx = 0.70 * dome_rad
            ry = 0.62 * dome_rad
            z_head_rim = hood_collar_z + (hood_top_z - hood_collar_z) * 0.72
            z_base = z_head_rim + (hood_top_z - z_head_rim) * math.sin(dome_lat)

        face_open_mask = max(0.0, min(1.0, (0.88 - tv) / 0.14))

        for iu in range(n_u + 1):
            tu = iu / n_u
            ang = ang_start + tu * (ang_end - ang_start)
            ca, sa = math.cos(ang), math.sin(ang)
            edge_prox = math.exp(-min(tu, 1.0 - tu) * 9.0) * face_open_mask
            front_fac = max(0.0, -sa)
            front_center = front_fac ** 2.8

            # Central chest cleft rises gently above hands; shoulder sides sweep smoothly over deltoids
            front_cut_z = 0.72 * front_center * ((1.0 - min(1.0, tv / 0.48)) ** 1.25)
            rear_cape_drop = -0.34 * max(0.0, sa) * ((1.0 - tv) ** 1.35)

            dome_damp = 1.0 - 0.85 * max(0.0, (tv - 0.72) / 0.28)
            fold_wave = 0.038 * math.sin(tu * math.pi * 8.0 + tv * 2.2) * (1.0 - 0.45 * tv) * dome_damp
            cowl_rim_roll = 0.028 * edge_prox * math.sin(tv * math.pi * 0.9) * dome_damp

            r_mod = 1.0 + fold_wave + cowl_rim_roll
            px = ca * rx * r_mod
            brow_overhang = -0.075 * edge_prox * (max(0.0, (tv - 0.46) / 0.54) ** 0.85)
            mantle_hug_y = 0.14 * front_fac * ((1.0 - min(1.0, tv / 0.48)) ** 1.2)
            arch_peak = 0.03 * math.exp(-((tv - 0.85) / 0.12) ** 2) * front_fac
            py = sa * ry * r_mod - 0.22 + brow_overhang + mantle_hug_y
            pz = z_base + front_cut_z + rear_cape_drop + arch_peak

            row.append(bm.verts.new((px, py, pz)))
        grid.append(row)

    for iv in range(n_v):
        for iu in range(n_u):
            bm.faces.new([grid[iv][iu], grid[iv][iu + 1], grid[iv + 1][iu + 1], grid[iv + 1][iu]])

    # Close forehead apex seam (tv >= 0.90) and stitch top ring smoothly to a rounded crown pole vertex
    for iv in range(int(n_v * 0.90), n_v):
        bm.faces.new([grid[iv][n_u], grid[iv][0], grid[iv + 1][0], grid[iv + 1][n_u]])
    pole_v = bm.verts.new((0.0, -0.22, hood_top_z + 0.02))
    for iu in range(n_u):
        bm.faces.new([grid[-1][iu], grid[-1][iu + 1], pole_v])
    bm.faces.new([grid[-1][n_u], grid[-1][0], pole_v])

    apply_coherent_stone_weathering(bm, amp=0.008, freq=1.4, seed_offset=(2.4, -1.2, 5.0))
    bmesh.ops.solidify(bm, geom=bm.faces[:], thickness=0.085)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = _finalize_part(
        "Saint_Hood",
        bm,
        col,
        parent,
        mat_stone,
        smooth=True,
        sharp_angle_deg=48.0,
        subsurf_level=max(1, subsurf_level),
    )
    return obj


def _build_saint_torso_and_sleeves(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mat_stone: bpy.types.Material,
    ped_top_z: float,
    fig_h: float,
    subsurf_level: int,
) -> bpy.types.Object:
    """Build Saint_Torso: broad Gothic mantle torso with draped chest scarf folds and flowing bell sleeves."""
    bm = bmesh.new()
    waist_z = ped_top_z + fig_h * 0.49   # ~10.42m
    sh_z = ped_top_z + fig_h * 0.715     # Anchors cleanly inside Saint_Head wimple collar

    n_u = 48
    n_v = 28
    t_rings: List[List[bmesh.types.BMVert]] = []
    for iv in range(n_v + 1):
        tv = iv / n_v
        z = waist_z + tv * (sh_z - waist_z)
        # Smooth anatomical taper from waist (0.94m) into narrow neck core (0.38m) — stays well INSIDE Saint_Hood!
        rx = 0.94 - 0.56 * (tv ** 1.22)
        ry = 0.66 - 0.30 * (tv ** 1.22)
        ring = []
        for iu in range(n_u):
            ang = (iu / n_u) * math.tau
            ca, sa = math.cos(ang), math.sin(ang)
            front_fac = max(0.0, -sa)
            pleat = 0.040 * math.sin(ang * 12.0) * front_fac * (1.0 - 0.35 * tv)
            # Soft diagonal U-shawl fold draping across upper chest just above hands
            chest_shawl = 0.052 * math.exp(-((tv - (0.62 - 0.14 * ca)) / 0.09) ** 2) * front_fac
            ring.append(bm.verts.new((ca * (rx + pleat + chest_shawl), sa * (ry + pleat + chest_shawl) - 0.06 * tv, z)))
        t_rings.append(ring)

    for iv in range(n_v):
        for iu in range(n_u):
            ju = (iu + 1) % n_u
            bm.faces.new([t_rings[iv][iu], t_rings[iv][ju], t_rings[iv + 1][ju], t_rings[iv + 1][iu]])
    bm.faces.new(list(reversed(t_rings[0])))
    bm.faces.new(t_rings[-1])

    # Left & Right bent arms with heavy cathedral bell sleeves emerging seamlessly from UNDER hood shoulder drape
    for side in (-1.0, 1.0):
        p_sh = Vector((side * 0.64, -0.06, ped_top_z + fig_h * 0.618))
        p_elb = Vector((side * 1.06, -0.34, ped_top_z + fig_h * 0.532))
        p_wr = Vector((
            side * 0.36,
            -0.78 if side < 0 else -0.84,
            ped_top_z + fig_h * (0.616 if side < 0 else 0.592),
        ))

        arm_steps = 28
        seg_u = 30
        arm_rings: List[List[bmesh.types.BMVert]] = []
        for ia in range(arm_steps + 1):
            ta = ia / arm_steps
            u0 = 1.0 - ta
            center = (u0 * u0) * p_sh + (2.0 * u0 * ta) * p_elb + (ta * ta) * p_wr
            tangent = (2.0 * u0 * (p_elb - p_sh) + 2.0 * ta * (p_wr - p_elb)).normalized()
            up_vec = Vector((0.0, 0.0, 1.0))
            side_vec = tangent.cross(up_vec).normalized()
            norm_up = side_vec.cross(tangent).normalized()

            sh_blend = 0.72 + 0.28 * min(1.0, ta / 0.20)
            r_horiz = (0.24 + 0.06 * math.sin(ta * math.pi * 0.85)) * sh_blend
            r_up = (0.21 - 0.03 * ta) * sh_blend
            r_down_drape = 0.26 + 0.40 * (math.sin(max(0.0, ta - 0.12) / 0.88 * math.pi) ** 1.15)
            cuff_taper = 1.0 - 0.08 * (max(0.0, (ta - 0.86) / 0.14) ** 1.2)

            a_ring = []
            for iu in range(seg_u):
                ang = (iu / seg_u) * math.tau
                ca, sa = math.cos(ang), math.sin(ang)
                r_vert = r_up if sa >= 0.0 else r_down_drape
                fold = 0.032 * math.sin(ang * 6.0 + ta * 5.0 * side)
                offset = side_vec * (ca * (r_horiz + fold) * cuff_taper) + norm_up * (sa * (r_vert + fold) * cuff_taper)
                a_ring.append(bm.verts.new(center + offset))
            arm_rings.append(a_ring)

        for ia in range(arm_steps):
            for iu in range(seg_u):
                ju = (iu + 1) % seg_u
                bm.faces.new([arm_rings[ia][iu], arm_rings[ia][ju], arm_rings[ia + 1][ju], arm_rings[ia + 1][iu]])
        bm.faces.new(list(reversed(arm_rings[0])))
        bm.faces.new(arm_rings[-1])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    apply_coherent_stone_weathering(bm, amp=0.010, freq=1.4, seed_offset=(3.1, 0.7, 2.0))
    return _finalize_part(
        "Saint_Torso",
        bm,
        col,
        parent,
        mat_stone,
        smooth=True,
        sharp_angle_deg=44.0,
        subsurf_level=max(1, subsurf_level),
    )


def _build_saint_hands(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mat_stone: bpy.types.Material,
    ped_top_z: float,
    fig_h: float,
    subsurf_level: int,
) -> bpy.types.Object:
    """Build two graceful sculpted stone hands resting cleanly layered over the chest."""
    bm = bmesh.new()
    chest_z = ped_top_z + fig_h * 0.625

    def _loft_tube(
        centers: List[Vector],
        u_dirs: List[Vector],
        v_dirs: List[Vector],
        rx_list: List[float],
        ry_list: List[float],
        segs: int = 12,
    ) -> None:
        rings = []
        for idx, ctr in enumerate(centers):
            ring = []
            for iu in range(segs):
                ang = (iu / segs) * math.tau
                pt = ctr + u_dirs[idx] * (math.cos(ang) * rx_list[idx]) + v_dirs[idx] * (math.sin(ang) * ry_list[idx])
                ring.append(bm.verts.new(pt))
            rings.append(ring)
        for idx in range(len(rings) - 1):
            for iu in range(segs):
                ju = (iu + 1) % segs
                bm.faces.new([rings[idx][iu], rings[idx][ju], rings[idx + 1][ju], rings[idx + 1][iu]])
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])

    # Statue's right hand (-1) lies flatter and HIGHER on upper sternum;
    # Left hand (+1) lies cleanly LOWER and slightly FORWARD in front of right wrist (zero interpenetration).
    hand_specs = [
        # side, cuff_src, palm_center, w_dir_raw, v_out_raw
        (
            -1.0,
            Vector((-0.36, -0.78, ped_top_z + fig_h * 0.616)),
            Vector((-0.02, -0.86, chest_z + 0.14)),
            Vector((0.76, 0.16, 0.63)),
            Vector((-0.10, -0.98, 0.16)),
        ),
        (
            1.0,
            Vector((0.36, -0.84, ped_top_z + fig_h * 0.592)),
            Vector((0.02, -0.93, chest_z - 0.10)),
            Vector((-0.78, 0.14, 0.61)),
            Vector((0.08, -0.98, 0.16)),
        ),
    ]

    for side, cuff_src, palm_center, w_raw, v_raw in hand_specs:
        w_dir = w_raw.normalized()
        v_out = (v_raw - w_dir * v_raw.dot(w_dir)).normalized()
        u_across = v_out.cross(w_dir).normalized()
        thumb_dir = -side * u_across  # Points UPWARD toward chin on both right & left hands

        wrist_base = cuff_src - w_dir * 0.22
        wrist_join = palm_center - w_dir * 0.22
        knuckle_line = palm_center + w_dir * 0.18

        # Continuous lofted forearm -> flattened wrist -> broad metacarpal palm (NO spherical wrist knob!)
        palm_stations = [
            (wrist_base, 0.15, 0.11),
            (wrist_base.lerp(wrist_join, 0.55), 0.14, 0.085),
            (wrist_join, 0.145, 0.072),
            (wrist_join.lerp(palm_center, 0.6), 0.17, 0.062),
            (palm_center, 0.185, 0.056),
            (knuckle_line, 0.175, 0.048),
            (knuckle_line + w_dir * 0.03, 0.12, 0.028),
        ]
        _loft_tube(
            [p for p, _, _ in palm_stations],
            [u_across] * len(palm_stations),
            [v_out] * len(palm_stations),
            [rx for _, rx, _ in palm_stations],
            [ry for _, _, ry in palm_stations],
            segs=16,
        )

        # 4 sculpted tapered fingers curving softly inward along the chest slope
        finger_layout = [
            (0.76, 0.34, 0.041),   # Index
            (0.25, 0.39, 0.044),   # Middle
            (-0.25, 0.35, 0.041),  # Ring
            (-0.73, 0.28, 0.036),  # Little
        ]
        for f_u, f_len, f_rad in finger_layout:
            f_axis = (w_dir + v_out * 0.08 + u_across * (side * -0.02 * f_u)).normalized()
            f_n = (v_out - f_axis * v_out.dot(f_axis)).normalized()
            f_u_vec = f_n.cross(f_axis).normalized()
            p0 = knuckle_line - w_dir * 0.03 + thumb_dir * (0.17 * f_u) + v_out * 0.004
            p1 = p0 + f_axis * (f_len * 0.48) - v_out * 0.015
            p2 = p1 + f_axis * (f_len * 0.52) - v_out * 0.032
            _loft_tube(
                [p0, p1, p2, p2 + f_axis * 0.02],
                [f_u_vec] * 4,
                [f_n] * 4,
                [f_rad, f_rad * 0.86, f_rad * 0.65, f_rad * 0.32],
                [f_rad * 0.90, f_rad * 0.78, f_rad * 0.60, f_rad * 0.30],
                segs=10,
            )

        # Opposable thumb resting gently along the upper radial margin
        th_dir = (w_dir * 0.80 + thumb_dir * 0.58 - v_out * 0.08).normalized()
        th_n = (v_out - th_dir * v_out.dot(th_dir)).normalized()
        th_u = th_n.cross(th_dir).normalized()
        th0 = palm_center - w_dir * 0.11 + thumb_dir * 0.13 + v_out * 0.012
        th1 = th0 + th_dir * 0.13 - v_out * 0.010
        th2 = th1 + th_dir * 0.12 - v_out * 0.018
        _loft_tube(
            [th0, th1, th2, th2 + th_dir * 0.02],
            [th_u] * 4,
            [th_n] * 4,
            [0.052, 0.044, 0.036, 0.020],
            [0.046, 0.040, 0.032, 0.018],
            segs=10,
        )

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    apply_coherent_stone_weathering(bm, amp=0.0022, freq=3.0, seed_offset=(0.5, 4.2, 8.1))
    return _finalize_part(
        "Saint_Hands",
        bm,
        col,
        parent,
        mat_stone,
        smooth=True,
        sharp_angle_deg=50.0,
        subsurf_level=max(1, subsurf_level),
    )


def _build_saint_robe(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mat_stone: bpy.types.Material,
    ped_top_z: float,
    fig_h: float,
    subsurf_level: int,
) -> bpy.types.Object:
    """Build hierarchical 3-tier sculptural robe with monumental proportions, fluted folds, and diagonal mantle wrap."""
    bm = bmesh.new()
    robe_h = fig_h * 0.565  # ~7.60m (from pedestal top 3.85m up to ~11.45m, tapering cleanly INSIDE Saint_Torso!)
    n_u = 92
    n_v = 80

    rings: List[List[bmesh.types.BMVert]] = []
    for iv in range(n_v + 1):
        tv = iv / n_v
        z = ped_top_z + tv * robe_h

        # Monumental Gothic silhouette: broad weighted hem (rx=1.64) -> pinched waist -> tucks smoothly INSIDE Saint_Torso
        if tv < 0.12:
            hem_flare = (1.0 - tv / 0.12) ** 1.5
            rx = 1.64 + 0.24 * hem_flare
            ry = 1.34 + 0.20 * hem_flare
        elif tv < 0.78:
            u = (tv - 0.12) / 0.66
            rx = 1.64 - 0.66 * (u ** 0.88)
            ry = 1.34 - 0.62 * (u ** 0.88)
        else:
            u = (tv - 0.78) / 0.22
            rx = 0.98 - 0.34 * (u ** 1.15)
            ry = 0.72 - 0.24 * (u ** 1.15)

        waist_tuck = -0.07 * math.exp(-((tv - 0.80) / 0.045) ** 2)
        overfold_bulge = 0.075 * math.exp(-((tv - 0.74) / 0.045) ** 2)

        ring = []
        for iu in range(n_u):
            ang = (iu / n_u) * math.tau
            ca, sa = math.cos(ang), math.sin(ang)
            front_fac = max(0.0, -sa)

            warped_ang = ang + 0.15 * math.sin(ang * 3.0 + 0.6) + 0.08 * math.cos(ang * 5.0 - 0.4)
            pipe_primary = 0.145 * (0.52 + 0.48 * math.cos(warped_ang * 7.0 + 0.32 * tv)) * (1.0 - 0.62 * tv)

            # Bold asymmetric Baroque/Gothic diagonal mantle swags draped across abdomen & thighs
            catenary_z = 0.48 + 0.22 * ca - 0.12 * (ca ** 2)
            diag_swag = 0.135 * math.exp(-((tv - catenary_z) / 0.082) ** 2) * front_fac
            diag_swag2 = 0.105 * math.exp(-((tv - (catenary_z + 0.14)) / 0.068) ** 2) * front_fac

            v_chest = 0.068 * math.sin((abs(ca) * 6.5 + (tv - 0.66) * 9.0) * math.pi) * math.exp(-((tv - 0.68) / 0.16) ** 2) * front_fac
            side_mantle = 0.092 * math.cos(ang * 13.0 - tv * 3.2) * (abs(ca) ** 1.2) * (1.0 - 0.45 * tv)
            tert_crinkle = 0.024 * math.sin(ang * 23.0 + tv * 18.0) * math.exp(-((tv - 0.76) / 0.14) ** 2)
            stone_grain = 0.015 * noise.noise(Vector((ca * 2.8, sa * 2.8, tv * 5.5)))

            top_tuck = max(0.0, 1.0 - max(0.0, (tv - 0.80) / 0.20) * 0.85)
            r_delta = (waist_tuck + overfold_bulge * front_fac + pipe_primary + diag_swag + diag_swag2 + v_chest + side_mantle + tert_crinkle + stone_grain) * top_tuck

            px = ca * (rx + r_delta)
            py = sa * (ry + r_delta) - 0.06 * math.sin(tv * math.pi * 0.8)
            pz = z
            if tv < 0.08:
                pz = max(ped_top_z - 0.02, z + 0.048 * math.cos(warped_ang * 7.0) * (1.0 - tv / 0.08))

            ring.append(bm.verts.new((px, py, pz)))
        rings.append(ring)

    for iv in range(n_v):
        for iu in range(n_u):
            ju = (iu + 1) % n_u
            bm.faces.new([rings[iv][iu], rings[iv][ju], rings[iv + 1][ju], rings[iv + 1][iu]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    return _finalize_part(
        "Saint_Robe",
        bm,
        col,
        parent,
        mat_stone,
        smooth=True,
        sharp_angle_deg=46.0,
        subsurf_level=max(1, subsurf_level),
    )


def _build_saint_halo(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mat_stone: bpy.types.Material,
    ped_top_z: float,
    fig_h: float,
) -> bpy.types.Object:
    """Build thick carved circular stone halo cradling the hooded head directly from behind."""
    rng = get_rng("saint_halo")
    halo_center = Vector((0.0, 0.34, ped_top_z + fig_h * 0.784))  # Concentric behind hooded head
    r_outer = 1.58
    r_inner = 1.00
    half_thick = 0.15
    segs = 80

    bm = bmesh.new()
    tilt_m = Matrix.Rotation(math.radians(8.0), 4, "X")

    # Build 4 profile rings (inner back, inner bevel, outer bevel, outer back) on both front & back faces
    # Profile in (radial r, depth y):
    profile = [
        (r_inner, -half_thick * 0.72),
        (r_inner + 0.08, -half_thick),
        (r_outer - 0.10, -half_thick),
        (r_outer, -half_thick * 0.65),
        (r_outer, half_thick * 0.65),
        (r_outer - 0.10, half_thick),
        (r_inner + 0.08, half_thick),
        (r_inner, half_thick * 0.72),
    ]
    n_p = len(profile)
    ring_loops: List[List[bmesh.types.BMVert]] = []

    for i in range(segs):
        ang = (i / segs) * math.tau
        ca, sa = math.cos(ang), math.sin(ang)
        # Subtle localized stone chips only at two asymmetric weathering spots (preserves crisp Gothic arch circle)
        chip = -0.045 * (math.exp(-((ang - 1.05) / 0.12) ** 2) + 0.8 * math.exp(-((ang - 2.35) / 0.10) ** 2))
        radial_groove = -0.012 * (0.5 + 0.5 * math.cos(ang * 24.0))

        loop = []
        for pi, (pr, py) in enumerate(profile):
            r_adj = pr + (chip if pr > (r_inner + r_outer) * 0.5 else 0.0)
            y_adj = py + (radial_groove if abs(py) > half_thick * 0.85 else 0.0)
            local_pt = Vector((ca * r_adj, y_adj, sa * r_adj))
            world_pt = halo_center + (tilt_m @ local_pt)
            loop.append(bm.verts.new(world_pt))
        ring_loops.append(loop)

    for i in range(segs):
        j = (i + 1) % segs
        for pi in range(n_p):
            pj = (pi + 1) % n_p
            bm.faces.new([ring_loops[i][pi], ring_loops[j][pi], ring_loops[j][pj], ring_loops[i][pj]])

    apply_coherent_stone_weathering(bm, amp=0.005, freq=1.6, seed_offset=(0.0, 5.0, 16.5))
    return _finalize_part(
        "Saint_Halo",
        bm,
        col,
        parent,
        mat_stone,
        smooth=False,
        sharp_angle_deg=36.0,
    )


# ==============================================================================
# LAYER 2: CENTRAL GOTHIC PEDESTAL (SAINT_PEDESTAL)
# ==============================================================================

def _build_saint_pedestal(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mats: Dict[str, bpy.types.Material],
    ped_top_z: float,
) -> List[bpy.types.Object]:
    """Build Pedestal_Base, Pedestal_Panels, and Pedestal_Cornices."""
    rng = get_rng("saint_pedestal")
    mat_ped = mats["MAT_Rootbound_PedestalStone"]
    mat_wet = mats["MAT_Rootbound_WetStone"]

    # 1. Pedestal_Base: Submerged & water-stained stepped octagonal/circular plinth (Z = -0.65 .. +1.22m)
    bm_base = bmesh.new()
    _add_polygonal_frustum(bm_base, -0.65, 0.18, 2.78, 2.62, segs=16, phase_rad=math.pi / 16.0)
    _add_polygonal_frustum(bm_base, 0.18, 0.58, 2.56, 2.34, segs=16, phase_rad=math.pi / 16.0)
    _add_polygonal_frustum(bm_base, 0.58, 0.96, 2.30, 2.12, segs=8, phase_rad=math.pi / 8.0)
    _add_polygonal_frustum(bm_base, 0.96, 1.24, 2.16, 1.98, segs=8, phase_rad=math.pi / 8.0)
    apply_coherent_stone_weathering(bm_base, amp=0.032, freq=0.95, seed_offset=(1.0, 1.0, 0.2))
    obj_base = _finalize_part("Pedestal_Base", bm_base, col, parent, mat_wet, sharp_angle_deg=38.0)

    # 2. Pedestal_Panels: Octagonal Gothic drum (Z = 1.24 .. 3.28m) with 8 recessed pointed-arch niches & corner colonnettes
    bm_pan = bmesh.new()
    z_bot = 1.24
    z_top = ped_top_z - 0.57  # 3.28m
    r_core = 1.82
    _add_polygonal_frustum(bm_pan, z_bot, z_top, r_core, r_core, segs=8, phase_rad=math.pi / 8.0)

    # 8 faceted Gothic blind-tracery frames + corner colonnette shafts
    for fi in range(8):
        ang = (fi / 8.0) * math.tau
        ca, sa = math.cos(ang), math.sin(ang)
        perp_x, perp_y = -sa, ca
        face_r = r_core * math.cos(math.pi / 8.0) + 0.06  # ~1.74m
        face_w = 2.0 * r_core * math.sin(math.pi / 8.0)   # ~1.39m

        # Left & right jamb colonnettes framing the recessed panel
        for s_side in (-1.0, 1.0):
            jx = ca * face_r + perp_x * (s_side * face_w * 0.40)
            jy = sa * face_r + perp_y * (s_side * face_w * 0.40)
            add_box_to_bmesh(
                bm_pan,
                (jx, jy, 0.5 * (z_bot + z_top)),
                (0.22, 0.22, z_top - z_bot),
                rot_euler=(0.0, 0.0, ang),
                bevel_width=0.025,
            )

        # Pointed Gothic blind-arch hood molding at top of each facet
        n_arch = 7
        span = face_w * 0.68
        spring_z = z_bot + (z_top - z_bot) * 0.60
        apex_z = z_top - 0.14
        for ai in range(n_arch):
            t0 = ai / n_arch
            t1 = (ai + 1) / n_arch
            tm = 0.5 * (t0 + t1)
            for s_side in (-1.0, 1.0):
                u_off = s_side * span * 0.5 * (1.0 - tm)
                z_m = spring_z + (apex_z - spring_z) * math.sin(tm * math.pi * 0.5)
                ax = ca * (face_r + 0.05) + perp_x * u_off
                ay = sa * (face_r + 0.05) + perp_y * u_off
                pitch_a = s_side * math.radians(38.0 * (1.0 - 0.4 * tm))
                add_box_to_bmesh(
                    bm_pan,
                    (ax, ay, z_m),
                    (0.18, 0.20, 0.24),
                    rot_euler=(pitch_a * sa, -pitch_a * ca, ang),
                    bevel_width=0.02,
                )

        # Corner octagonal pilaster column with base & capital
        c_ang = ang + math.pi / 8.0
        cx_p = math.cos(c_ang) * (r_core + 0.06)
        cy_p = math.sin(c_ang) * (r_core + 0.06)
        _add_polygonal_frustum(bm_pan, z_bot, z_bot + 0.22, 0.24, 0.19, segs=8, center_xy=(cx_p, cy_p))
        _add_polygonal_frustum(bm_pan, z_bot + 0.22, z_top - 0.22, 0.17, 0.16, segs=8, center_xy=(cx_p, cy_p))
        _add_polygonal_frustum(bm_pan, z_top - 0.22, z_top + 0.04, 0.18, 0.26, segs=8, center_xy=(cx_p, cy_p))

    apply_coherent_stone_weathering(bm_pan, amp=0.024, freq=1.1, seed_offset=(2.0, 3.0, 2.0))
    obj_pan = _finalize_part("Pedestal_Panels", bm_pan, col, parent, mat_ped, sharp_angle_deg=38.0)

    # 3. Pedestal_Cornices: Projecting multi-tier Gothic upper cornice & abacus table (Z = 3.28 .. 3.85m)
    bm_cor = bmesh.new()
    _add_polygonal_frustum(bm_cor, z_top, z_top + 0.20, 1.92, 2.22, segs=8, phase_rad=math.pi / 8.0)
    _add_polygonal_frustum(bm_cor, z_top + 0.20, z_top + 0.42, 2.28, 2.38, segs=16, phase_rad=math.pi / 16.0)
    _add_polygonal_frustum(bm_cor, z_top + 0.42, ped_top_z, 2.34, 2.20, segs=16, phase_rad=math.pi / 16.0)
    apply_coherent_stone_weathering(bm_cor, amp=0.026, freq=1.2, seed_offset=(4.0, 1.0, 3.6))
    obj_cor = _finalize_part("Pedestal_Cornices", bm_cor, col, parent, mat_ped, sharp_angle_deg=38.0)

    return [obj_base, obj_pan, obj_cor]


# ==============================================================================
# LAYER 3: CURVED STAIRCASE SYSTEM (SAINT_STAIRS)
# ==============================================================================

def build_curved_staircase(
    bm: bmesh.types.BMesh,
    start_radius: float,
    end_radius: float,
    start_angle_deg: float,
    end_angle_deg: float,
    z_start: float,
    total_rise: float,
    step_count: int,
    stair_width: float,
    damage_seed: str = "stairs",
    add_cheek_walls: bool = True,
) -> None:
    """Parameterized curved limestone staircase generator with individual treads, risers, and cheek walls."""
    rng = get_rng(damage_seed)
    a0 = math.radians(start_angle_deg)
    a1 = math.radians(end_angle_deg)
    da = (a1 - a0) / max(1, step_count)
    riser_h = total_rise / max(1, step_count)

    for si in range(step_count):
        t = (si + 0.5) / step_count
        ang = a0 + (si + 0.5) * da
        r_mid = start_radius + (end_radius - start_radius) * t
        z_top = z_start + (si + 1) * riser_h + rng.uniform(-0.015, 0.015)
        z_bot = max(-0.35, z_top - riser_h * 2.2)
        h_block = z_top - z_bot

        arc_tread = abs(da) * r_mid * 1.12
        w_tread = stair_width * rng.uniform(0.96, 1.03)
        px = r_mid * math.cos(ang)
        py = r_mid * math.sin(ang)

        # Occasional cracked/split two-piece step tread
        if rng.random() < 0.28:
            for half in (-0.25, 0.25):
                r_sub = r_mid + half * w_tread * 0.95
                add_box_to_bmesh(
                    bm,
                    (r_sub * math.cos(ang), r_sub * math.sin(ang), z_bot + h_block * 0.5 + rng.uniform(-0.02, 0.01)),
                    (w_tread * 0.47, arc_tread, h_block),
                    rot_euler=(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), ang),
                    bevel_width=0.03,
                )
        else:
            add_box_to_bmesh(
                bm,
                (px, py, z_bot + h_block * 0.5),
                (w_tread, arc_tread, h_block),
                rot_euler=(rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), ang),
                bevel_width=0.032,
            )

        # Inner & outer stone cheek wall / low stepped stringer curb
        if add_cheek_walls:
            for side_s, h_cheek in ((-0.52, 0.42), (0.52, 0.34)):
                if rng.random() < 0.12:
                    continue
                rc = r_mid + side_s * stair_width
                cz_top = z_top + h_cheek + rng.uniform(-0.05, 0.04)
                cz_bot = z_bot
                ch = cz_top - cz_bot
                add_box_to_bmesh(
                    bm,
                    (rc * math.cos(ang), rc * math.sin(ang), cz_bot + ch * 0.5),
                    (0.34, arc_tread * 1.05, ch),
                    rot_euler=(0.0, 0.0, ang),
                    bevel_width=0.028,
                )


def _build_saint_stairs(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mats: Dict[str, bpy.types.Material],
) -> List[bpy.types.Object]:
    """Build Stairs_Left, Stairs_Right, and Stairs_Landings matching reference composition."""
    rng = get_rng("saint_stairs_system")
    mat_stair = mats["MAT_Rootbound_StairStone"]

    # 1. Stairs_Left: Sweeping curved flight along left inner wall (214 deg -> 112 deg, Z=0.14 -> 2.32m)
    bm_left = bmesh.new()
    build_curved_staircase(
        bm_left,
        start_radius=4.95,
        end_radius=5.15,
        start_angle_deg=214.0,
        end_angle_deg=112.0,
        z_start=0.12,
        total_rise=2.20,
        step_count=14,
        stair_width=2.35,
        damage_seed="stairs_left_main",
        add_cheek_walls=True,
    )
    apply_coherent_stone_weathering(bm_left, amp=0.022, freq=1.1, seed_offset=(-5.0, 0.0, 1.0))
    obj_left = _finalize_part("Stairs_Left", bm_left, col, parent, mat_stair, sharp_angle_deg=40.0)

    # 2. Stairs_Right: Upper curved flight (-14 deg / 346 deg -> 68 deg, Z=1.08 -> 2.32m)
    #    PLUS foreground-right lower flight descending into the front-right water pool (332 deg -> 298 deg, Z=1.08 -> 0.04m)
    bm_right = bmesh.new()
    build_curved_staircase(
        bm_right,
        start_radius=5.05,
        end_radius=5.15,
        start_angle_deg=-14.0,
        end_angle_deg=68.0,
        z_start=1.08,
        total_rise=1.24,
        step_count=9,
        stair_width=2.30,
        damage_seed="stairs_right_upper",
        add_cheek_walls=True,
    )
    build_curved_staircase(
        bm_right,
        start_radius=4.85,
        end_radius=5.35,
        start_angle_deg=332.0,
        end_angle_deg=298.0,
        z_start=1.08,
        total_rise=-1.04,
        step_count=7,
        stair_width=2.15,
        damage_seed="stairs_right_lower_front",
        add_cheek_walls=True,
    )
    apply_coherent_stone_weathering(bm_right, amp=0.022, freq=1.1, seed_offset=(5.0, 0.0, 1.0))
    obj_right = _finalize_part("Stairs_Right", bm_right, col, parent, mat_stair, sharp_angle_deg=40.0)

    # 3. Stairs_Landings: Front entrance threshold, right mid-landing (332..348 deg @ Z=1.08m),
    #    and elevated rear semicircular gallery (66..114 deg @ Z=2.32m)
    bm_land = bmesh.new()
    # Elevated rear horseshoe gallery platform (56 deg .. 124 deg, r=2.35..6.55m, Z=2.32m)
    n_gal = 14
    for gi in range(n_gal):
        a0 = math.radians(56.0 + (gi / n_gal) * 68.0)
        a1 = math.radians(56.0 + ((gi + 0.94) / n_gal) * 68.0)
        am = 0.5 * (a0 + a1)
        for r_band, w_band in ((3.25, 1.75), (5.20, 2.25)):
            px = r_band * math.cos(am)
            py = r_band * math.sin(am)
            arc_l = (a1 - a0) * r_band * 1.06
            z_top = 2.32 + rng.uniform(-0.02, 0.02)
            h_l = z_top + 0.45
            add_box_to_bmesh(
                bm_land,
                (px, py, z_top - h_l * 0.5),
                (w_band, arc_l, h_l),
                rot_euler=(rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015), am),
                bevel_width=0.035,
            )

    # Right intermediate stone landing (328..350 deg, r=3.85..6.35m, Z=1.08m)
    for li in range(4):
        am = math.radians(330.0 + li * 5.5)
        r_m = 5.05
        z_top = 1.08 + rng.uniform(-0.02, 0.02)
        h_l = z_top + 0.45
        add_box_to_bmesh(
            bm_land,
            (r_m * math.cos(am), r_m * math.sin(am), z_top - h_l * 0.5),
            (2.45, 0.68, h_l),
            rot_euler=(0.0, 0.0, am),
            bevel_width=0.032,
        )

    # Left lower approach threshold (212..236 deg, r=3.9..6.2m, Z=0.14m)
    for li in range(4):
        am = math.radians(214.0 + li * 5.8)
        r_m = 4.95
        z_top = 0.14 + rng.uniform(-0.02, 0.02)
        add_box_to_bmesh(
            bm_land,
            (r_m * math.cos(am), r_m * math.sin(am), z_top - 0.35),
            (2.35, 0.65, 0.70),
            rot_euler=(0.0, 0.0, am),
            bevel_width=0.03,
        )

    apply_coherent_stone_weathering(bm_land, amp=0.020, freq=1.0, seed_offset=(0.0, 4.0, 2.3))
    obj_land = _finalize_part("Stairs_Landings", bm_land, col, parent, mat_stair, sharp_angle_deg=40.0)

    return [obj_left, obj_right, obj_land]


# ==============================================================================
# LAYER 4: CIRCULAR TERRACE AND BALUSTRADE (SAINT_TERRACE)
# ==============================================================================

def _build_saint_terrace(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mats: Dict[str, bpy.types.Material],
) -> List[bpy.types.Object]:
    """Build Terrace_Floor, Terrace_OuterWall, and Terrace_Balustrades."""
    rng = get_rng("saint_terrace")
    mat_parapet = mats["MAT_Rootbound_Parapet"]
    mat_wet = mats["MAT_Rootbound_WetStone"]

    # 1. Terrace_Floor: Outer wet stone curb ring (r=7.70..8.25m, Z=-0.35..+0.12m) leaving a shallow water channel at r=7.35..7.75m
    #    + Inner flooded basin cracked stone floor (r=2.4..6.6m, Z=-0.26..-0.08m in front pool so dark water reflects statue!)
    #    + Front causeway entrance threshold slabs (angle 262..278 deg, Z=+0.12..+0.18m)
    bm_floor = bmesh.new()
    n_curb = 52
    for ci in range(n_curb):
        ang = (ci / n_curb) * math.tau
        r_c = 7.98
        arc_l = (math.tau * r_c / n_curb) * 0.92
        z_top = rng.uniform(0.03, 0.13) if rng.random() > 0.28 else rng.uniform(-0.14, -0.02)
        add_box_to_bmesh(
            bm_floor,
            (r_c * math.cos(ang), r_c * math.sin(ang), z_top - 0.35),
            (0.56, arc_l, 0.70),
            rot_euler=(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), ang),
            bevel_width=0.028,
        )

    # Inner basin submerged/emergent cracked paving stones (leaving central front water pool open & reflective at Z=0.0)
    for ri, (r_ring, n_slabs) in enumerate(((3.35, 18), (4.85, 24), (6.05, 28))):
        for si in range(n_slabs):
            ang_deg = (si / n_slabs) * 360.0 + (ri * 7.5)
            ang = math.radians(ang_deg)
            deg_m = ang_deg % 360.0
            # Front water basin (195..342 deg) stays submerged (Z = -0.26..-0.08m) so dark water reflects statue!
            if 195.0 <= deg_m <= 342.0:
                if abs(deg_m - 270.0) < 9.0 and r_ring > 5.2:
                    # Causeway entry stepping threshold at front (-Y, 270 deg)
                    z_top = 0.12 + rng.uniform(-0.02, 0.02)
                else:
                    z_top = rng.uniform(-0.26, -0.08)
            else:
                z_top = rng.uniform(0.04, 0.15)
            arc_l = (math.tau * r_ring / n_slabs) * 0.92
            add_box_to_bmesh(
                bm_floor,
                (r_ring * math.cos(ang), r_ring * math.sin(ang), z_top - 0.30),
                (1.28, arc_l, 0.60),
                rot_euler=(rng.uniform(-0.025, 0.025), rng.uniform(-0.025, 0.025), ang),
                bevel_width=0.028,
            )

    apply_coherent_stone_weathering(bm_floor, amp=0.022, freq=0.9, seed_offset=(0.0, -2.0, 0.0))
    obj_floor = _finalize_part("Terrace_Floor", bm_floor, col, parent, mat_wet, sharp_angle_deg=40.0)

    # 2. Terrace_OuterWall: Circular Gothic retaining wall (r=6.55..7.35m, Z=-0.55..+1.82m)
    #    with 32 bays of recessed pointed Gothic blind-tracery arches, pilasters, and coping!
    bm_wall = bmesh.new()
    n_bays = 32
    r_wall = 6.95
    wall_thick = 0.78

    for bi in range(n_bays):
        ang_deg = (bi / n_bays) * 360.0
        ang = math.radians(ang_deg)
        ca, sa = math.cos(ang), math.sin(ang)
        perp_x, perp_y = -sa, ca
        bay_arc = (math.tau * r_wall / n_bays)

        # Front causeway breach: keep low carved front sill (Z <= 1.05m) on front arc (235..295 deg)
        # matching the reference's continuous front curved Gothic arcade wall, while leaving a navigable
        # low stepped entry notch right at 264..276 deg!
        if 264.0 <= ang_deg <= 276.0:
            wall_top = 0.32
        elif 218.0 <= ang_deg <= 325.0:
            wall_top = 1.26 + 0.18 * math.cos(math.radians((ang_deg - 220.0) * 1.6))
        else:
            wall_top = 1.82

        z_bot = -0.55
        h_core = wall_top - z_bot

        # Core recessed wall bay
        add_box_to_bmesh(
            bm_wall,
            (ca * r_wall, sa * r_wall, z_bot + h_core * 0.5),
            (wall_thick * 0.76, bay_arc * 0.98, h_core),
            rot_euler=(0.0, 0.0, ang),
            bevel_width=0.028,
        )

        # Lower plinth molding & upper coping cornice
        add_box_to_bmesh(
            bm_wall,
            (ca * (r_wall + 0.06), sa * (r_wall + 0.06), -0.08),
            (wall_thick * 1.02, bay_arc * 1.01, 0.36),
            rot_euler=(0.0, 0.0, ang),
            bevel_width=0.025,
        )
        if wall_top > 0.55:
            add_box_to_bmesh(
                bm_wall,
                (ca * (r_wall + 0.04), sa * (r_wall + 0.04), wall_top - 0.11),
                (wall_thick * 1.08, bay_arc * 1.02, 0.22),
                rot_euler=(0.0, 0.0, ang),
                bevel_width=0.028,
            )

            # Recessed Gothic pointed blind-arch pilaster & arch head on outer face
            pil_ang = ang - (math.pi / n_bays)
            pca, psa = math.cos(pil_ang), math.sin(pil_ang)
            r_outer_face = r_wall + wall_thick * 0.42
            add_box_to_bmesh(
                bm_wall,
                (pca * r_outer_face, psa * r_outer_face, 0.5 * (0.10 + wall_top - 0.18)),
                (0.22, 0.24, max(0.25, wall_top - 0.28)),
                rot_euler=(0.0, 0.0, pil_ang),
                bevel_width=0.02,
            )
            # Pointed blind-arch lintel ribs inside bay
            for s_side in (-1.0, 1.0):
                ax = ca * r_outer_face + perp_x * (s_side * bay_arc * 0.22)
                ay = sa * r_outer_face + perp_y * (s_side * bay_arc * 0.22)
                add_box_to_bmesh(
                    bm_wall,
                    (ax, ay, wall_top - 0.34),
                    (0.18, bay_arc * 0.44, 0.20),
                    rot_euler=(s_side * 0.28 * sa, -s_side * 0.28 * ca, ang),
                    bevel_width=0.018,
                )

    apply_coherent_stone_weathering(bm_wall, amp=0.025, freq=1.05, seed_offset=(2.0, -3.0, 0.8))
    obj_wall = _finalize_part("Terrace_OuterWall", bm_wall, col, parent, mat_parapet, sharp_angle_deg=38.0)

    # 3. Terrace_Balustrades: Carved Gothic parapet piers, balusters, and top rail along upper wall arcs
    #    (Left & Rear & Right: 334 deg -> 212 deg passing through 0/90/180 deg, with ruined breaks!)
    bm_bal = bmesh.new()
    r_bal = 6.95
    pier_Step_deg = 18.0
    # Angles from -26 deg (334 deg) counter-clockwise around back to 212 deg
    ang_cur = -26.0
    ang_end = 212.0

    while ang_cur < ang_end:
        ang_next = min(ang_end, ang_cur + pier_Step_deg)
        a0 = math.radians(ang_cur)
        a1 = math.radians(ang_next)
        am = 0.5 * (a0 + a1)
        deg_mod = ang_cur % 360.0

        # Base wall top under this balustrade bay
        z_base = 1.82 if not (218.0 <= deg_mod <= 325.0) else 1.32
        z_rail = z_base + 1.12

        # Square carved stone pier post at a0
        if not (28.0 <= deg_mod <= 44.0):  # Right-rear ruined collapse gap where roots spill!
            px = r_bal * math.cos(a0)
            py = r_bal * math.sin(a0)
            pier_h = 1.18 if rng.random() > 0.15 else rng.uniform(0.65, 0.92)
            add_box_to_bmesh(
                bm_bal,
                (px, py, z_base + pier_h * 0.5),
                (0.58, 0.58, pier_h),
                rot_euler=(0.0, 0.0, a0),
                bevel_width=0.03,
            )
            # Pier cap molding
            if pier_h > 1.0:
                add_box_to_bmesh(
                    bm_bal,
                    (px, py, z_base + pier_h + 0.06),
                    (0.68, 0.68, 0.14),
                    rot_euler=(0.0, 0.0, a0),
                    bevel_width=0.025,
                )

        # Balusters & top coping rail between a0 and a1 (skip collapsed bay at 22..42 deg & 196..212 deg)
        if not (20.0 <= deg_mod <= 42.0) and not (198.0 <= deg_mod <= 215.0):
            n_cols = 4
            for ci in range(1, n_cols + 1):
                tc = ci / (n_cols + 1)
                ac = a0 + tc * (a1 - a0)
                if rng.random() < 0.14:
                    continue  # Missing broken baluster
                bx = r_bal * math.cos(ac)
                by = r_bal * math.sin(ac)
                tilt = rng.uniform(-0.08, 0.08) if rng.random() < 0.2 else 0.0
                # Base plinth, waisted shaft, capital of baluster
                add_box_to_bmesh(bm_bal, (bx, by, z_base + 0.12), (0.28, 0.28, 0.22), rot_euler=(tilt, 0.0, ac), bevel_width=0.02)
                add_box_to_bmesh(bm_bal, (bx, by, z_base + 0.48), (0.20, 0.20, 0.54), rot_euler=(tilt, 0.0, ac), bevel_width=0.02)
                add_box_to_bmesh(bm_bal, (bx, by, z_base + 0.82), (0.28, 0.28, 0.20), rot_euler=(tilt, 0.0, ac), bevel_width=0.02)

            # Heavy molded top handrail
            arc_seg = (a1 - a0) * r_bal * 0.96
            add_box_to_bmesh(
                bm_bal,
                (r_bal * math.cos(am), r_bal * math.sin(am), z_rail - 0.10),
                (0.52, arc_seg, 0.22),
                rot_euler=(rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), am),
                bevel_width=0.028,
            )

        ang_cur = ang_next

    # Final terminal pier at 212 deg (left staircase front end)
    a_end = math.radians(212.0)
    add_box_to_bmesh(
        bm_bal,
        (r_bal * math.cos(a_end), r_bal * math.sin(a_end), 1.82 + 0.56),
        (0.62, 0.62, 1.12),
        rot_euler=(0.0, 0.0, a_end),
        bevel_width=0.03,
    )

    apply_coherent_stone_weathering(bm_bal, amp=0.022, freq=1.15, seed_offset=(-3.0, 3.0, 2.5))
    obj_bal = _finalize_part("Terrace_Balustrades", bm_bal, col, parent, mat_parapet, sharp_angle_deg=38.0)

    return [obj_floor, obj_wall, obj_bal]


# ==============================================================================
# LAYER 5: ANCIENT ROOTS, DEBRIS & COLLISION (SAINT_ROOTS, SAINT_DEBRIS, SAINT_COLLISION)
# ==============================================================================

def _add_tapered_root_tube(
    bm: bmesh.types.BMesh,
    waypoints: Sequence[Tuple[float, float, float]],
    r_start: float,
    r_end: float,
    rng,
    subdiv_per_seg: int = 5,
    ring_segs: int = 10,
    wobble_amp: float = 0.14,
) -> List[Vector]:
    """Generate a gnarled, fluted organic root tube mesh along Catmull-like interpolated waypoints."""
    pts = [Vector(p) for p in waypoints]
    if len(pts) < 2:
        return pts

    dense: List[Vector] = []
    n_seg = len(pts) - 1
    for i in range(n_seg):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(n_seg, i + 2)]
        for s in range(subdiv_per_seg):
            if i > 0 and s == 0:
                continue
            t = s / subdiv_per_seg
            t2 = t * t
            t3 = t2 * t
            # Catmull-Rom spline interpolation
            pos = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            end_atten = math.sin(((i + t) / n_seg) * math.pi)
            n_vec = noise.noise_vector(pos * 0.65 + Vector((rng.uniform(0, 5), 0, 0)))
            pos = pos + Vector((n_vec.x, n_vec.y, n_vec.z * 0.55)) * (wobble_amp * end_atten)
            dense.append(pos)
    dense.append(pts[-1])

    rings: List[List[bmesh.types.BMVert]] = []
    total_n = len(dense)
    prev_tan: Optional[Vector] = None
    prev_u: Optional[Vector] = None
    for idx, p in enumerate(dense):
        tf = idx / max(1, total_n - 1)
        rad = r_start * ((1.0 - tf) ** 0.78) + r_end * tf
        tan = dense[min(total_n - 1, idx + 1)] - dense[max(0, idx - 1)]
        if tan.length < 1e-6:
            tan = prev_tan or Vector((0.0, 0.0, 1.0))
        else:
            tan.normalize()
        if prev_u is None:
            ref = Vector((0.0, 0.0, 1.0)) if abs(tan.z) < 0.90 else Vector((1.0, 0.0, 0.0))
            u_ax = tan.cross(ref).normalized()
        else:
            # Parallel-transport frame prevents sudden twist/bow-tie pinches on near-vertical roots
            u_proj = prev_u - tan * prev_u.dot(tan)
            if u_proj.length < 1e-5:
                u_ax = (prev_tan.rotation_difference(tan) @ prev_u).normalized()
            else:
                u_ax = u_proj.normalized()
        v_ax = u_ax.cross(tan).normalized()
        prev_tan = tan
        prev_u = u_ax

        ring = []
        for si in range(ring_segs):
            ang = (si / ring_segs) * math.tau + tf * 3.5
            flute = 1.0 + 0.14 * math.sin(ang * 4.0 + tf * 6.0)
            off = (u_ax * math.cos(ang) + v_ax * math.sin(ang)) * (rad * flute)
            ring.append(bm.verts.new(p + off))
        rings.append(ring)

    for idx in range(total_n - 1):
        for si in range(ring_segs):
            sj = (si + 1) % ring_segs
            bm.faces.new([rings[idx][si], rings[idx][sj], rings[idx + 1][sj], rings[idx + 1][si]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return dense


def _build_saint_roots(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mats: Dict[str, bpy.types.Material],
    ped_top_z: float,
    fig_h: float,
) -> List[bpy.types.Object]:
    """Build Root_Primary, Root_Secondary, and Root_Tendrils (with moss cushions)."""
    rng = get_rng("saint_roots_network")
    mat_bark = mats["MAT_Rootbound_RootBark"]
    mat_moss = mats["MAT_Rootbound_Moss"]

    # 1. Root_Primary: Signature asymmetric gnarled hero root sweeping diagonally UP-RIGHT across outer robe
    #    plus heavy buttress roots spilling across the pedestal and broken stairs into the flooded basin.
    bm_pri = bmesh.new()
    primary_paths = [
        # Hero Root A: Climbs from front-left water pool -> up pedestal -> sweeps diagonally up-right across outer front robe!
        (
            [
                (-3.45, -3.35, -0.22),
                (-2.55, -2.38, -0.02),
                (-2.08, -1.82, 1.15),
                (-1.76, -1.68, 2.55),
                (-1.26, -1.60, ped_top_z + 0.08),
                (-0.68, -1.58, ped_top_z + 1.15),
                (0.16, -1.48, ped_top_z + 2.40),
                (0.80, -1.24, ped_top_z + 3.65),
                (0.98, -0.92, ped_top_z + 5.05),
                (0.88, -0.74, ped_top_z + 6.15),
            ],
            0.27,
            0.018,
        ),
        # Hero Root B: Climbs front-right pedestal base & wraps smoothly right-around lower robe (never crosses Hero Root A!)
        (
            [
                (2.48, -2.38, -0.12),
                (2.02, -1.78, 1.15),
                (1.74, -1.60, 2.55),
                (1.42, -1.48, ped_top_z + 0.08),
                (1.52, -1.10, ped_top_z + 0.55),
                (1.44, -0.68, ped_top_z + 1.25),
                (1.22, -0.38, ped_top_z + 2.05),
            ],
            0.22,
            0.016,
        ),
        # Hero Root C: Spills from left pedestal cornice across left staircase landing over outer retaining wall into left water rim
        (
            [
                (-1.48, -1.15, ped_top_z + 0.08),
                (-2.45, -1.32, 2.15),
                (-4.25, -1.95, 1.45),
                (-6.25, -2.55, 1.52),
                (-6.95, -2.85, 0.85),
                (-7.35, -3.05, -0.08),
            ],
            0.21,
            0.065,
        ),
        # Hero Root D: Massive front-right cascade over broken lower right stairs & outer wall into front-right water
        (
            [
                (1.52, -0.95, ped_top_z + 0.05),
                (2.35, -1.25, 2.10),
                (3.85, -2.65, 1.25),
                (5.45, -3.75, 1.38),
                (6.25, -4.15, 0.92),
                (6.65, -4.45, -0.10),
            ],
            0.23,
            0.070,
        ),
        # Hero Root E: Rear-right balustrade collapse root bundle
        (
            [
                (1.28, 1.15, ped_top_z + 0.12),
                (3.15, 2.45, 2.42),
                (5.25, 3.85, 2.85),
                (6.15, 4.15, 2.15),
                (6.55, 4.45, 0.15),
            ],
            0.21,
            0.065,
        ),
    ]
    for path_pts, r0, r1 in primary_paths:
        _add_tapered_root_tube(bm_pri, path_pts, r0, r1, rng, subdiv_per_seg=6, ring_segs=10, wobble_amp=0.048)

    bmesh.ops.recalc_face_normals(bm_pri, faces=bm_pri.faces[:])
    obj_pri = _finalize_part("Root_Primary", bm_pri, col, parent, mat_bark, smooth=True, sharp_angle_deg=52.0)

    # 2. Root_Secondary: Organic bifurcations hugging outer robe folds, pedestal cornice, and stairs
    bm_sec = bmesh.new()
    secondary_paths = [
        # Right hip fork upward from Hero Root A into waist & chest mantle folds
        [(0.78, -1.24, ped_top_z + 3.55), (0.98, -0.94, ped_top_z + 4.95), (0.96, -0.76, ped_top_z + 6.45), (0.82, -0.68, ped_top_z + 7.45)],
        # Left flank vine creeping up from pedestal cornice along left robe drapery
        [(-2.25, -3.05, -0.12), (-1.68, -2.08, 1.55), (-1.40, -1.50, ped_top_z + 0.25), (-1.36, -1.08, ped_top_z + 2.15), (-1.12, -0.84, ped_top_z + 4.35)],
        # Lower front pedestal weave anchored in water basin -> pedestal wall -> cornice
        [(-1.15, -2.55, -0.15), (-0.45, -2.02, 1.45), (0.35, -1.78, 2.95), (0.92, -1.52, ped_top_z + 0.12), (1.26, -1.16, ped_top_z + 1.45)],
        # Left stair tread roots
        [(-3.45, -1.25, 1.15), (-4.85, -1.85, 0.82), (-5.85, -2.95, 0.22), (-6.35, -3.65, -0.10)],
        [(-4.55, 1.85, 1.85), (-5.65, 0.55, 1.25), (-6.85, -0.65, 1.55), (-7.35, -1.10, 0.35)],
        # Right stair & front wall roots
        [(3.25, -1.95, 1.05), (4.65, -3.45, 0.52), (5.75, -4.15, 0.85), (6.35, -4.65, -0.05)],
        [(4.25, 1.25, 1.65), (5.55, -0.45, 1.18), (6.85, -1.55, 1.42), (7.25, -2.15, 0.15)],
        # Rear pedestal & gallery roots
        [(-1.35, 1.35, ped_top_z + 0.12), (-2.35, 2.85, 2.38), (-4.15, 4.55, 2.42), (-5.85, 4.95, 1.95)],
        [(0.42, 1.55, ped_top_z + 1.25), (0.85, 2.15, 2.55), (2.25, 4.25, 2.38), (4.25, 5.65, 2.45)],
    ]
    for path_pts in secondary_paths:
        _add_tapered_root_tube(bm_sec, path_pts, 0.10, 0.015, rng, subdiv_per_seg=5, ring_segs=8, wobble_amp=0.042)

    bmesh.ops.recalc_face_normals(bm_sec, faces=bm_sec.faces[:])
    obj_sec = _finalize_part("Root_Secondary", bm_sec, col, parent, mat_bark, smooth=True, sharp_angle_deg=52.0)

    # 3. Root_Tendrils: Fine creeping vines hugging diagonal root seams, pedestal & balustrades + moss cushions
    bm_ten = bmesh.new()
    tendril_paths = [
        # Hugging Hero Root A diagonal sweep closely along robe folds
        [(-0.78, -1.56, ped_top_z + 1.25), (-0.15, -1.52, ped_top_z + 2.15), (0.50, -1.36, ped_top_z + 3.25), (0.94, -1.04, ped_top_z + 4.45)],
        [(0.32, -1.42, ped_top_z + 2.65), (0.78, -1.18, ped_top_z + 4.15), (0.68, -0.96, ped_top_z + 5.55)],
        [(-1.24, -1.12, ped_top_z + 2.85), (-1.18, -0.90, ped_top_z + 4.55), (-0.94, -0.74, ped_top_z + 5.95)],
        [(2.35, -2.25, -0.10), (1.88, -1.80, 1.75), (1.58, -1.60, 3.15), (1.22, -1.42, ped_top_z + 0.55)],
        [(-6.45, -3.05, 1.35), (-6.85, -3.45, 0.65), (-7.05, -3.65, -0.05)],
        [(5.05, -4.45, 1.28), (5.45, -4.85, 0.55), (5.85, -5.15, -0.05)],
        [(2.55, -6.35, 1.25), (2.75, -6.75, 0.45), (2.95, -7.15, -0.05)],
        [(-2.35, -6.35, 1.25), (-2.55, -6.85, 0.48), (-2.75, -7.25, -0.05)],
    ]
    for path_pts in tendril_paths:
        _add_tapered_root_tube(bm_ten, path_pts, 0.038, 0.008, rng, subdiv_per_seg=4, ring_segs=6, wobble_amp=0.028)

    # Low, flattened multi-lobe organic moss cushions nestled around statue robe hem, pedestal cornice, and broken parapet
    moss_spots = [
        (0.78, -1.34, ped_top_z + 0.04, (0.48, 0.36, 0.08)),
        (-0.88, -1.32, ped_top_z + 0.04, (0.45, 0.34, 0.08)),
        (1.36, -0.58, ped_top_z + 0.04, (0.46, 0.38, 0.08)),
        (-1.34, 0.32, ped_top_z + 0.04, (0.44, 0.36, 0.08)),
        (1.52, -1.35, 2.85, (0.38, 0.32, 0.10)),
        (-1.72, -1.28, 1.45, (0.42, 0.34, 0.09)),
        (4.85, -4.55, 1.28, (0.58, 0.42, 0.10)),
        (-6.25, -2.95, 1.38, (0.52, 0.38, 0.09)),
        (5.45, 3.95, 2.38, (0.62, 0.48, 0.11)),
    ]
    for mx, my, mz, msz in moss_spots:
        add_box_to_bmesh(
            bm_ten,
            (mx, my, mz),
            msz,
            rot_euler=(rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), rng.uniform(0.0, math.tau)),
            bevel_width=0.04,
        )

    bmesh.ops.recalc_face_normals(bm_ten, faces=bm_ten.faces[:])
    apply_coherent_stone_weathering(bm_ten, amp=0.015, freq=2.0, seed_offset=(5.0, 5.0, 5.0))
    obj_ten = _finalize_part("Root_Tendrils", bm_ten, col, parent, mat_moss, smooth=True, sharp_angle_deg=50.0)

    return [obj_pri, obj_sec, obj_ten]


def _build_saint_debris(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mats: Dict[str, bpy.types.Material],
) -> List[bpy.types.Object]:
    """Build Fallen_Parapets, Broken_Stone, and Rubble matching reference's flooded basin & outer rim."""
    rng = get_rng("saint_debris_ruins")
    mat_rub = mats["MAT_Rootbound_Rubble"]
    mat_par = mats["MAT_Rootbound_Parapet"]

    # 1. Fallen_Parapets: Tilted carved rectangular Gothic relief slabs half-submerged in front water pool!
    bm_fal = bmesh.new()
    fallen_slabs = [
        # Prominent tilted carved sarcophagus/parapet slab in front-left water pool (seen in reference!)
        ((-3.45, -2.65, 0.28), (22.0, 14.0, -32.0), (1.35, 2.15, 0.38)),
        # Second tilted relief slab near front-center pedestal base
        ((0.45, -2.85, 0.14), (-16.0, 24.0, 28.0), (1.18, 1.85, 0.34)),
        # Third broken parapet section on right landing / upper stair
        ((4.45, 2.15, 2.52), (12.0, -18.0, 48.0), (0.95, 1.45, 0.36)),
        # Submerged carved fragment in front pool
        ((-1.55, -3.85, -0.02), (8.0, -12.0, 18.0), (0.92, 1.25, 0.28)),
    ]
    for (lx, ly, lz), (rx_d, ry_d, rz_d), (sx, sy, sz) in fallen_slabs:
        rot_e = (math.radians(rx_d), math.radians(ry_d), math.radians(rz_d))
        # Outer slab frame
        add_box_to_bmesh(bm_fal, (lx, ly, lz), (sx, sy, sz), rot_euler=rot_e, bevel_width=0.03)
        # Raised carved border molding on top face
        add_box_to_bmesh(bm_fal, (lx, ly, lz + 0.04), (sx * 0.78, sy * 0.82, sz * 1.12), rot_euler=rot_e, bevel_width=0.025)

    apply_coherent_stone_weathering(bm_fal, amp=0.025, freq=1.3, seed_offset=(-2.0, -3.0, 0.1))
    obj_fal = _finalize_part("Fallen_Parapets", bm_fal, col, parent, mat_par, sharp_angle_deg=38.0)

    # 2. Broken_Stone: Fractured ashlar blocks, broken column drums, and displaced stair stones
    bm_brk = bmesh.new()
    broken_spots = [
        (-2.25, -3.35, 0.06, (0.72, 0.58, 0.38)),
        (1.85, -3.15, 0.08, (0.68, 0.52, 0.34)),
        (2.75, -2.25, 0.12, (0.58, 0.48, 0.32)),
        (-4.65, -0.85, 1.28, (0.54, 0.44, 0.28)),
        (4.85, -0.95, 1.22, (0.62, 0.48, 0.32)),
        (1.25, -4.65, -0.04, (0.65, 0.55, 0.26)),
        (-0.85, -4.95, -0.03, (0.58, 0.48, 0.24)),
    ]
    for bx, by, bz, bsz in broken_spots:
        add_box_to_bmesh(
            bm_brk,
            (bx, by, bz),
            bsz,
            rot_euler=(rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), rng.uniform(0.0, math.tau)),
            bevel_width=0.03,
        )
    apply_coherent_stone_weathering(bm_brk, amp=0.030, freq=1.4, seed_offset=(3.0, -2.0, 0.0))
    obj_brk = _finalize_part("Broken_Stone", bm_brk, col, parent, mat_rub, sharp_angle_deg=38.0)

    # 3. Rubble: Wet river/limestone boulders and cobbles clustered along outer base rim & water edge
    bm_rub = bmesh.new()
    for _ in range(68):
        ang = rng.uniform(0.0, math.tau)
        # Cluster around outer curb (r=7.2..8.3m) and inner basin edges (r=2.5..4.2m)
        if rng.random() < 0.72:
            rad = rng.uniform(7.15, 8.28)
            z_r = rng.uniform(-0.08, 0.14)
        else:
            rad = rng.uniform(2.35, 4.15)
            z_r = rng.uniform(-0.06, 0.10)
        rx_s = rng.uniform(0.28, 0.72)
        ry_s = rng.uniform(0.24, 0.62)
        rz_s = rng.uniform(0.18, 0.38)
        add_box_to_bmesh(
            bm_rub,
            (rad * math.cos(ang), rad * math.sin(ang), z_r),
            (rx_s, ry_s, rz_s),
            rot_euler=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0.0, math.tau)),
            bevel_width=0.04,
        )
    apply_coherent_stone_weathering(bm_rub, amp=0.035, freq=1.6, seed_offset=(7.0, 2.0, 0.0))
    obj_rub = _finalize_part("Rubble", bm_rub, col, parent, mat_rub, sharp_angle_deg=36.0)

    return [obj_fal, obj_brk, obj_rub]


def _build_saint_collision(
    col: bpy.types.Collection,
    parent: bpy.types.Object,
    mats: Dict[str, bpy.types.Material],
) -> List[bpy.types.Object]:
    """Build explicit simplified collision proxies: Collision_Terrace, Collision_Stairs, Collision_Pedestal."""
    mat_col = mats["MAT_Rootbound_WetStone"]

    # 1. Collision_Terrace: Walkable terrace entry floor & upper rear gallery
    bm_ct = bmesh.new()
    _add_polygonal_frustum(bm_ct, -0.35, 0.14, 8.15, 8.10, segs=24)
    # Upper gallery walkable platform (rear arc 55..125 deg at Z=2.32m)
    for gi in range(8):
        am = math.radians(58.0 + gi * 9.0)
        add_box_to_bmesh(
            bm_ct,
            (4.45 * math.cos(am), 4.45 * math.sin(am), 1.16),
            (3.6, 1.1, 2.32),
            rot_euler=(0.0, 0.0, am),
            bevel_width=0.0,
        )
    obj_ct = _finalize_part("Collision_Terrace", bm_ct, col, parent, mat_col, smooth=False, sharp_angle_deg=None)
    obj_ct.hide_render = True

    # 2. Collision_Stairs: Smooth sloped walkable ramp over Left & Right staircases
    bm_cs = bmesh.new()
    # Left ramp (214 -> 112 deg, Z=0.14 -> 2.32m)
    n_ramp = 14
    for ri in range(n_ramp):
        t = (ri + 0.5) / n_ramp
        ang = math.radians(214.0 + (112.0 - 214.0) * t)
        r_m = 5.05
        z_m = 0.14 + 2.18 * t
        add_box_to_bmesh(
            bm_cs,
            (r_m * math.cos(ang), r_m * math.sin(ang), z_m * 0.5),
            (2.25, 0.78, z_m),
            rot_euler=(0.0, 0.0, ang),
            bevel_width=0.0,
        )
    # Right ramp (298 -> 68 deg, Z=0.08 -> 2.32m)
    for ri in range(n_ramp):
        t = (ri + 0.5) / n_ramp
        ang = math.radians(-62.0 + 130.0 * t)
        r_m = 5.05
        z_m = 0.08 + 2.24 * t
        add_box_to_bmesh(
            bm_cs,
            (r_m * math.cos(ang), r_m * math.sin(ang), z_m * 0.5),
            (2.25, 0.85, z_m),
            rot_euler=(0.0, 0.0, ang),
            bevel_width=0.0,
        )
    obj_cs = _finalize_part("Collision_Stairs", bm_cs, col, parent, mat_col, smooth=False, sharp_angle_deg=None)
    obj_cs.hide_render = True

    # 3. Collision_Pedestal: Solid central pedestal cylinder (r=2.38m, Z=0..4.5m)
    bm_cp = bmesh.new()
    _add_polygonal_frustum(bm_cp, -0.5, 4.5, 2.38, 2.38, segs=12)
    obj_cp = _finalize_part("Collision_Pedestal", bm_cp, col, parent, mat_col, smooth=False, sharp_angle_deg=None)
    obj_cp.hide_render = True

    return [obj_ct, obj_cs, obj_cp]


# ==============================================================================
# MASTER ASSET BUILDER
# ==============================================================================

def build_rootbound_saint(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
    subsurf_level: int = 1,
    center: Optional[Tuple[float, float, float]] = None,
    statue_rot_z_deg: Optional[float] = None,
) -> Dict[str, bpy.types.Object]:
    """Idempotently build the complete Rootbound Saint monument inside `05_ROOTBOUND_SAINT`."""
    clear_existing_rootbound_saint(include_legacy_statue=True)

    rcfg = LAYOUT["rootbound_saint"]
    root_loc = center if center is not None else tuple(rcfg["center"])
    fig_rot_z = statue_rot_z_deg if statue_rot_z_deg is not None else float(rcfg["rotation_z_deg"])
    ped_top_z = float(rcfg["pedestal_top_z"])
    fig_h = float(rcfg["statue_height"])

    col_root = cols.get("05_ROOTBOUND_SAINT") or get_or_create_collection("05_ROOTBOUND_SAINT")
    for s_sub in SAINT_SUBCOLLECTIONS:
        if s_sub not in cols:
            cols[s_sub] = get_or_create_collection(s_sub, col_root)

    root_empty = _make_group_empty("ROOTBOUND_SAINT_ROOT", None, col_root, location=root_loc)

    grp_statue = _make_group_empty(
        "SAINT_STATUE",
        root_empty,
        cols["SAINT_STATUE"],
        rotation_deg=(0.0, 0.0, fig_rot_z),
    )
    grp_pedestal = _make_group_empty("SAINT_PEDESTAL", root_empty, cols["SAINT_PEDESTAL"])
    grp_stairs = _make_group_empty("SAINT_STAIRS", root_empty, cols["SAINT_STAIRS"])
    grp_terrace = _make_group_empty("SAINT_TERRACE", root_empty, cols["SAINT_TERRACE"])
    grp_roots = _make_group_empty("SAINT_ROOTS", root_empty, cols["SAINT_ROOTS"])
    grp_debris = _make_group_empty("SAINT_DEBRIS", root_empty, cols["SAINT_DEBRIS"])
    grp_collision = _make_group_empty("SAINT_COLLISION", root_empty, cols["SAINT_COLLISION"])

    mat_statue = mats["MAT_Rootbound_StatueStone"]

    # Layer 1: Holy Woman Statue
    obj_head, obj_face = _build_saint_face_and_head(
        cols["SAINT_STATUE"], grp_statue, mat_statue, ped_top_z, fig_h, subsurf_level
    )
    obj_hood = _build_saint_hood(
        cols["SAINT_STATUE"], grp_statue, mat_statue, ped_top_z, fig_h, subsurf_level
    )
    obj_torso = _build_saint_torso_and_sleeves(
        cols["SAINT_STATUE"], grp_statue, mat_statue, ped_top_z, fig_h, subsurf_level
    )
    obj_hands = _build_saint_hands(
        cols["SAINT_STATUE"], grp_statue, mat_statue, ped_top_z, fig_h, subsurf_level
    )
    obj_robe = _build_saint_robe(
        cols["SAINT_STATUE"], grp_statue, mat_statue, ped_top_z, fig_h, subsurf_level
    )
    obj_halo = _build_saint_halo(
        cols["SAINT_STATUE"], grp_statue, mat_statue, ped_top_z, fig_h
    )

    # Layer 2: Central Gothic Pedestal
    ped_objs = _build_saint_pedestal(cols["SAINT_PEDESTAL"], grp_pedestal, mats, ped_top_z)

    # Layer 3: Curved Staircases
    stair_objs = _build_saint_stairs(cols["SAINT_STAIRS"], grp_stairs, mats)

    # Layer 4: Circular Terrace & Balustrades
    terrace_objs = _build_saint_terrace(cols["SAINT_TERRACE"], grp_terrace, mats)

    # Layer 5: Roots, Debris & Collision
    root_objs = _build_saint_roots(cols["SAINT_ROOTS"], grp_roots, mats, ped_top_z, fig_h)
    debris_objs = _build_saint_debris(cols["SAINT_DEBRIS"], grp_debris, mats)
    col_objs = _build_saint_collision(cols["SAINT_COLLISION"], grp_collision, mats)

    all_parts = [
        root_empty,
        obj_head,
        obj_face,
        obj_hood,
        obj_torso,
        obj_hands,
        obj_robe,
        obj_halo,
        *ped_objs,
        *stair_objs,
        *terrace_objs,
        *root_objs,
        *debris_objs,
        *col_objs,
    ]
    return {o.name: o for o in all_parts}


def validate_rootbound_saint() -> Dict[str, object]:
    """Validate that all required Rootbound Saint objects, materials, and bounds exist cleanly."""
    required_meshes = [
        "Saint_Head",
        "Saint_Face",
        "Saint_Hood",
        "Saint_Torso",
        "Saint_Hands",
        "Saint_Robe",
        "Saint_Halo",
        "Pedestal_Base",
        "Pedestal_Panels",
        "Pedestal_Cornices",
        "Stairs_Left",
        "Stairs_Right",
        "Stairs_Landings",
        "Terrace_Floor",
        "Terrace_OuterWall",
        "Terrace_Balustrades",
        "Root_Primary",
        "Root_Secondary",
        "Root_Tendrils",
        "Rubble",
        "Broken_Stone",
        "Fallen_Parapets",
        "Collision_Terrace",
        "Collision_Stairs",
        "Collision_Pedestal",
    ]
    missing = [n for n in required_meshes if bpy.data.objects.get(n) is None]
    unshaded = []
    total_verts = 0
    total_polys = 0
    min_z = 999.0
    max_z = -999.0
    max_r = 0.0

    root_obj = bpy.data.objects.get("ROOTBOUND_SAINT_ROOT")
    root_xy = Vector((root_obj.location.x, root_obj.location.y)) if root_obj else Vector((0.0, 2.0))

    for name in required_meshes:
        obj = bpy.data.objects.get(name)
        if not obj or obj.type != "MESH":
            continue
        total_verts += len(obj.data.vertices)
        total_polys += len(obj.data.polygons)
        if len(obj.data.materials) == 0 or obj.data.materials[0] is None:
            unshaded.append(name)
        for v in obj.data.vertices:
            w = obj.matrix_world @ v.co
            min_z = min(min_z, w.z)
            max_z = max(max_z, w.z)
            r = (Vector((w.x, w.y)) - root_xy).length
            max_r = max(max_r, r)

    legacy_present = (
        bpy.data.objects.get("Statue_Central_Figure") is not None
        or bpy.data.objects.get("Statue_Pedestal") is not None
    )

    return {
        "passed": len(missing) == 0 and len(unshaded) == 0 and not legacy_present,
        "missing_objects": missing,
        "unshaded_objects": unshaded,
        "legacy_statue_present": legacy_present,
        "total_vertices": total_verts,
        "total_polygons": total_polys,
        "bbox_min_z": round(min_z, 3),
        "bbox_max_z": round(max_z, 3),
        "max_radius_m": round(max_r, 3),
    }


def export_isolated_rootbound_glb(output_glb_path: str, bake_res: int = 1536) -> Dict[str, object]:
    """Bake PBR atlas `Sanctuary_RootboundSaint` and export `output/rootbound_saint/rootbound_saint.glb`."""
    import pbr_bake

    col_saint = bpy.data.collections.get("05_ROOTBOUND_SAINT")
    if col_saint is None:
        raise RuntimeError("05_ROOTBOUND_SAINT collection not found")

    # Hide collision proxies & non-Rootbound collections during isolated export
    visible_meshes = []
    for obj in list(bpy.data.objects):
        in_saint = any(obj.name == s.name for s in col_saint.all_objects)
        if not in_saint:
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        if obj.name.startswith("Collision_"):
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == "SUBSURF":
                    mod.levels = min(mod.levels, 1)
                    mod.render_levels = min(mod.render_levels, 1)
            visible_meshes.append(obj)

    tmp_bake_dir = os.path.join(PROJECT_ROOT, "output", "rootbound_saint", "_bake_tmp")
    pbr_bake.bake_pbr_atlas(
        atlas_name="Sanctuary_RootboundSaint",
        objects=visible_meshes,
        resolution=bake_res,
        samples_emit=1,
        samples_normal=1,
        samples_ao=6,
        ao_distance=2.0,
        island_margin=0.005,
        texture_dir=tmp_bake_dir,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_glb_path)), exist_ok=True)
    tmp_glb = os.path.abspath(output_glb_path) + ".tmp.glb"
    bpy.ops.export_scene.gltf(
        filepath=tmp_glb,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="WEBP",
        export_image_quality=86,
        export_cameras=False,
        export_lights=False,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
    )
    if os.path.exists(output_glb_path):
        os.replace(tmp_glb, output_glb_path)
    else:
        os.rename(tmp_glb, output_glb_path)

    return {"glb": output_glb_path, "bytes": os.path.getsize(output_glb_path)}


if __name__ == "__main__":
    from cameras import setup_cameras, setup_compositor_and_color_management
    from lighting import setup_lighting
    from water import build_water

    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Build, render & export isolated Rootbound Saint asset.")
    parser.add_argument("--export-glb", action="store_true", help="Also bake & export rootbound_saint.glb")
    parser.add_argument("--samples", type=int, default=48)
    args = parser.parse_args(argv)

    scene = reset_scene()
    cols = setup_collections()
    mats = create_all_materials()
    build_rootbound_saint(cols, mats, subsurf_level=2, center=(0.0, 2.0, 0.0), statue_rot_z_deg=0.0)
    build_water(cols, mats)
    setup_lighting(cols)
    cams = setup_cameras(cols, active_cam_name="CAM_ROOTBOUND_HERO")
    setup_compositor_and_color_management(scene)

    val = validate_rootbound_saint()
    print("[RootboundSaint] Validation:", json.dumps(val, indent=2))

    out_dir = os.path.join(PROJECT_ROOT, "output", "rootbound_saint")
    os.makedirs(out_dir, exist_ok=True)
    blend_out = os.path.join(out_dir, "rootbound_saint_source.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_out)
    print(f"[RootboundSaint] Saved source .blend -> {blend_out}")

    if args.export_glb:
        glb_out = os.path.join(out_dir, "rootbound_saint.glb")
        info = export_isolated_rootbound_glb(glb_out, bake_res=1536)
        print("[RootboundSaint] Exported isolated GLB:", json.dumps(info))
