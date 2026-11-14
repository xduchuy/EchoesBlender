"""Geometry helpers, collection hierarchy, and deterministic RNG utilities."""

import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector, noise

from config import LAYOUT, SEED


def get_rng(salt: str = "") -> random.Random:
    """Return a deterministic Random instance seeded from global SEED and salt."""
    h = 0
    for ch in salt:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return random.Random(SEED ^ h)


def reset_scene() -> bpy.types.Scene:
    """Clear all objects, meshes, materials, and orphaned data blocks cleanly."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def get_or_create_collection(
    name: str, parent: Optional[bpy.types.Collection] = None
) -> bpy.types.Collection:
    """Retrieve or create a collection and link it under parent or scene root."""
    if name in bpy.data.collections:
        col = bpy.data.collections[name]
    else:
        col = bpy.data.collections.new(name)
        target = parent if parent is not None else bpy.context.scene.collection
        target.children.link(col)
    return col


def setup_collections() -> Dict[str, bpy.types.Collection]:
    """Create the complete organized collection hierarchy for The Drowned Sanctuary."""
    cols: Dict[str, bpy.types.Collection] = {}
    top_names = [
        "00_REFERENCE",
        "01_TERRAIN",
        "02_CLIFFS",
        "03_ARCHITECTURE",
        "04_COURTYARD",
        "05_STATUE",
        "06_WATER",
        "07_ROOTS",
        "08_RUBBLE",
        "09_VEGETATION",
        "10_ATMOSPHERE",
        "11_LIGHTING",
        "12_CAMERAS",
    ]
    for name in top_names:
        cols[name] = get_or_create_collection(name)

    arch_parent = cols["03_ARCHITECTURE"]
    arch_subs = [
        "ARCH_LeftFront",
        "ARCH_LeftRear",
        "ARCH_RightRear",
        "ARCH_RightFront",
        "ARCH_RearArcade",
        "ARCH_ConnectingWalls",
    ]
    for sub in arch_subs:
        cols[sub] = get_or_create_collection(sub, arch_parent)

    return cols


def create_control_empty(cols: Dict[str, bpy.types.Collection]) -> bpy.types.Object:
    """Create an Empty with custom properties exposing key editable scene parameters."""
    ctrl = bpy.data.objects.new("Sanctuary_Control", None)
    ctrl.empty_display_type = "PLAIN_AXES"
    ctrl.empty_display_size = 3.0
    ctrl.location = (0.0, 0.0, 0.0)
    cols["00_REFERENCE"].objects.link(ctrl)

    ctrl["water_level"] = float(LAYOUT["water_level"])
    ctrl["sun_elevation_deg"] = float(LAYOUT["lighting"]["sun_elevation_deg"])
    ctrl["sun_azimuth_deg"] = float(LAYOUT["lighting"]["sun_azimuth_deg"])
    ctrl["sun_energy"] = float(LAYOUT["lighting"]["sun_energy"])
    ctrl["mist_density"] = float(LAYOUT["atmosphere"]["mist_density"])
    ctrl["courtyard_haze_density"] = float(LAYOUT["atmosphere"]["courtyard_haze_density"])
    ctrl["distant_haze_density"] = float(LAYOUT["atmosphere"]["distant_haze_density"])
    ctrl["seed"] = int(SEED)
    return ctrl


def link_object_to_collection(
    obj: bpy.types.Object, col: bpy.types.Collection
) -> bpy.types.Object:
    """Ensure object is linked exclusively to the specified collection."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def assign_material(
    obj: bpy.types.Object, mat: Optional[bpy.types.Material]
) -> None:
    """Assign material to slot 0 of mesh/curve object."""
    if mat is None or not hasattr(obj.data, "materials"):
        return
    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat


def apply_sharp_edge_shading(
    bm: bmesh.types.BMesh, sharp_angle_deg: float = 44.0
) -> None:
    """Smooth gentle surfaces while marking sharp dihedral creases for crisp rock/stone edges."""
    thresh = math.radians(sharp_angle_deg)
    bm.normal_update()
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) <= thresh
        else:
            e.smooth = False


def create_mesh_object(
    name: str,
    bm: bmesh.types.BMesh,
    col: bpy.types.Collection,
    mat: Optional[bpy.types.Material] = None,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    smooth: bool = False,
    sharp_angle_deg: Optional[float] = None,
) -> bpy.types.Object:
    """Convert a BMesh into a Blender Object with clean normals and link it."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if sharp_angle_deg is not None:
        apply_sharp_edge_shading(bm, sharp_angle_deg=sharp_angle_deg)
    elif smooth:
        for f in bm.faces:
            f.smooth = True

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    col.objects.link(obj)
    if mat is not None:
        assign_material(obj, mat)
    return obj


def instance_mesh_object(
    name: str,
    mesh_data: bpy.types.Mesh,
    col: bpy.types.Collection,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    mat: Optional[bpy.types.Material] = None,
) -> bpy.types.Object:
    """Create a linked mesh instance sharing geometry data."""
    obj = bpy.data.objects.new(name, mesh_data)
    obj.location = location
    obj.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    obj.scale = scale
    col.objects.link(obj)
    if mat is not None:
        assign_material(obj, mat)
    return obj


def gothic_arch_points(
    half_span: float,
    spring_z: float,
    apex_z: float,
    segments_per_side: int = 10,
) -> List[Tuple[float, float]]:
    """
    Compute 2D profile points (x, z) from (-half_span, spring_z) up to (0, apex_z)
    and down to (+half_span, spring_z) using a true two-centered pointed Gothic arc.
    """
    if half_span <= 0.001:
        return [(0.0, spring_z)]
    rise = max(0.05, apex_z - spring_z)
    # Circle through (-half_span, spring_z) and (0, apex_z) with center at (xc, spring_z), xc >= 0:
    # (xc + half_span)^2 = xc^2 + rise^2  =>  2*xc*half_span + half_span^2 = rise^2
    # Wait: for pointed arch, center for left arc is at (+xc, spring_z) so radius R = xc + half_span
    # Distance to apex (0, apex_z): xc^2 + rise^2 = (xc + half_span)^2 => xc = (rise^2 - half_span^2) / (2 * half_span)
    # If rise < half_span (drop arch), fall back cleanly to smooth pointed ellipse-like interpolation.
    pts: List[Tuple[float, float]] = []
    if rise >= half_span * 1.02:
        xc = (rise * rise - half_span * half_span) / (2.0 * half_span)
        radius = xc + half_span
        theta_end = math.atan2(rise, xc)  # angle from left-pointing horizontal up toward apex
        # Left arc: center at (+xc, spring_z), angle goes from pi down to pi - theta_end
        for i in range(segments_per_side + 1):
            t = i / segments_per_side
            ang = math.pi - t * theta_end
            x = xc + radius * math.cos(ang)
            z = spring_z + radius * math.sin(ang)
            pts.append((x, z))
        # Right arc: center at (-xc, spring_z), angle goes from theta_end down to 0
        for i in range(1, segments_per_side + 1):
            t = i / segments_per_side
            ang = (1.0 - t) * theta_end
            x = -xc + radius * math.cos(ang)
            z = spring_z + radius * math.sin(ang)
            pts.append((x, z))
    else:
        # Low pointed arch
        for i in range(segments_per_side + 1):
            t = i / segments_per_side
            ang = (math.pi * 0.5) * (1.0 - t)
            x = -half_span * math.sin(ang)
            z = spring_z + rise * (math.cos(ang) ** 0.85)
            pts.append((x, z))
        for i in range(1, segments_per_side + 1):
            t = i / segments_per_side
            ang = (math.pi * 0.5) * t
            x = half_span * math.sin(ang)
            z = spring_z + rise * (math.cos(ang) ** 0.85)
            pts.append((x, z))
    return pts


def add_box_to_bmesh(
    bm: bmesh.types.BMesh,
    center: Tuple[float, float, float],
    size: Tuple[float, float, float],
    rot_euler: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    bevel_width: float = 0.0,
    noise_amp: float = 0.0,
    noise_scale: float = 0.5,
    rng: Optional[random.Random] = None,
) -> List[bmesh.types.BMVert]:
    """Append a box (optionally beveled and stone-weathered) into an existing BMesh."""
    sx, sy, sz = size
    mat_scale = Matrix.Diagonal((sx, sy, sz, 1.0))
    mat_rot = Euler(rot_euler, "XYZ").to_matrix().to_4x4()
    mat_loc = Matrix.Translation(center)
    xf = mat_loc @ mat_rot @ mat_scale

    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=xf)
    verts = ret["verts"]

    if bevel_width > 0.001:
        edges = list({e for v in verts for e in v.link_edges})
        bev_ret = bmesh.ops.bevel(
            bm,
            geom=edges,
            offset=bevel_width,
            segments=1,
            profile=0.5,
            affect="EDGES",
            clamp_overlap=True,
        )
        bev_verts = [v for v in bev_ret.get("verts", []) if v.is_valid]
        if bev_verts:
            verts = bev_verts

    if noise_amp > 0.0001:
        seed_offset = Vector((0.0, 0.0, 0.0))
        if rng is not None:
            seed_offset = Vector(
                (rng.uniform(-50, 50), rng.uniform(-50, 50), rng.uniform(-50, 50))
            )
        for v in verts:
            if v.is_valid:
                p = v.co * noise_scale + seed_offset
                v.co += noise.noise_vector(p) * noise_amp

    return [v for v in verts if v.is_valid]


def apply_coherent_stone_weathering(
    bm: bmesh.types.BMesh,
    amp: float = 0.05,
    freq: float = 0.35,
    seed_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    z_erosion_boost: float = 0.0,
) -> None:
    """Displace vertices gently using multi-octave 3D noise for weathered stone silhouettes."""
    off = Vector(seed_offset)
    for v in bm.verts:
        p = v.co * freq + off
        n1 = noise.noise_vector(p)
        n2 = noise.noise_vector(p * 2.7 + Vector((11.3, -7.1, 4.9))) * 0.35
        scale = amp
        if z_erosion_boost > 0.0 and v.co.z > 0.0:
            scale += z_erosion_boost * min(1.0, v.co.z / 30.0)
        v.co += (n1 + n2) * scale


def subdivide_mesh_edges_for_detail(
    bm: bmesh.types.BMesh, cuts: int = 1, max_edge_len: float = 1.6
) -> None:
    """Subdivide long edges before displacement so masonry surfaces deform cleanly."""
    if cuts <= 0:
        return
    long_edges = [e for e in bm.edges if e.calc_length() > max_edge_len]
    if long_edges:
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=cuts, use_grid_fill=True)
