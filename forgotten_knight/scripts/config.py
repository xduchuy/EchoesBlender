"""Configuration, deterministic constants, anatomy coordinates, and quality presets
for THE FORGOTTEN KNIGHT reconstruction pipeline.
"""

import math
import os
import random
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler


# ---------------------------------------------------------------------------
# Project paths & deterministic seed
# ---------------------------------------------------------------------------
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
REFERENCES_DIR = os.path.join(PROJECT_DIR, "references")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
RENDERS_DIR = os.path.join(PROJECT_DIR, "renders")
TEXTURES_DIR = os.path.join(OUTPUT_DIR, "textures")

REFERENCE_IMAGE_PATH = os.path.join(REFERENCES_DIR, "forgotten_knight.png")
BLEND_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "forgotten_knight.blend")
GLB_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "forgotten_knight.glb")

SEED = 42


def seeded_rng(offset: int = 0) -> random.Random:
    """Return a deterministic Random instance keyed off global SEED."""
    return random.Random(SEED + offset)


# ---------------------------------------------------------------------------
# Collections (Section 24 exact naming)
# ---------------------------------------------------------------------------
COLLECTIONS = [
    "00_REFERENCE",
    "01_BODY",
    "02_ARMATURE",
    "03_HELMET",
    "04_HOOD",
    "05_TORSO_ARMOR",
    "06_ARM_ARMOR",
    "07_HANDS",
    "08_CHAINMAIL",
    "09_TUNIC",
    "10_CAPE",
    "11_LEG_ARMOR",
    "12_BELTS",
    "13_WEAPONS",
    "14_LANTERN",
    "15_PEDESTAL",
    "16_LIGHTING",
    "17_CAMERAS",
    "18_PRESENTATION",
]


# ---------------------------------------------------------------------------
# Material library (Section 15 exact naming)
# ---------------------------------------------------------------------------
MATERIAL_NAMES = [
    "MAT_Steel_Worn",
    "MAT_Steel_Oxidized",
    "MAT_Steel_Dark",
    "MAT_Chainmail",
    "MAT_Leather_Dark",
    "MAT_Leather_Brown",
    "MAT_Fabric_ForestGreen",
    "MAT_Fabric_Cape",
    "MAT_Fabric_Tabard",
    "MAT_Brass_Aged",
    "MAT_Rust",
    "MAT_Stone_Weathered",
    "MAT_Moss",
    "MAT_Dirt",
]


# ---------------------------------------------------------------------------
# Quality & detail presets (Sections 23 & 29)
# ---------------------------------------------------------------------------
QUALITY_PRESETS = {
    "preview": {
        "sheet_width": 960,
        "sheet_height": 540,
        "view_width": 480,
        "view_height": 540,
        "detail_width": 640,
        "detail_height": 640,
        "samples": 48,
        "use_denoising": True,
        "default_detail": "MEDIUM",
    },
    "review": {
        "sheet_width": 1920,
        "sheet_height": 1080,
        "view_width": 960,
        "view_height": 1080,
        "detail_width": 960,
        "detail_height": 960,
        "samples": 128,
        "use_denoising": True,
        "default_detail": "MEDIUM",
    },
    "final": {
        "sheet_width": 2560,
        "sheet_height": 1440,
        "view_width": 1280,
        "view_height": 1440,
        "detail_width": 1200,
        "detail_height": 1200,
        "samples": 256,
        "use_denoising": True,
        "default_detail": "HIGH",
    },
}

DETAIL_SETTINGS = {
    "LOW": {
        "subdiv": 1,
        "radial_segs": 14,
        "cloth_subdiv": 1,
        "chainmail_rings_per_zone": 140,
        "pedestal_segs": 48,
        "root_count": 10,
    },
    "MEDIUM": {
        "subdiv": 2,
        "radial_segs": 20,
        "cloth_subdiv": 2,
        "chainmail_rings_per_zone": 320,
        "pedestal_segs": 72,
        "root_count": 18,
    },
    "HIGH": {
        "subdiv": 2,
        "radial_segs": 26,
        "cloth_subdiv": 3,
        "chainmail_rings_per_zone": 540,
        "pedestal_segs": 96,
        "root_count": 26,
    },
}


# ---------------------------------------------------------------------------
# Anatomical measurements & reference pose coordinates (meters, Z-up, -Y fwd)
# Right side = -X (viewer left in front view), Left side = +X (viewer right)
# ---------------------------------------------------------------------------
CHARACTER_HEIGHT = 1.855

JOINTS = {
    "root": Vector((0.0, 0.0, 0.0)),
    "pelvis": Vector((0.0, 0.00, 0.96)),
    "spine_low": Vector((0.0, 0.00, 1.09)),
    "spine_mid": Vector((0.0, -0.01, 1.24)),
    "chest": Vector((0.0, -0.01, 1.38)),
    "neck_base": Vector((0.0, -0.01, 1.49)),
    "neck_top": Vector((0.0, -0.02, 1.57)),
    "head_pivot": Vector((0.0, -0.025, 1.62)),
    "head_top": Vector((0.0, -0.035, 1.845)),

    # Clavicles & Shoulders
    "clavicle_R": Vector((-0.07, -0.01, 1.43)),
    "shoulder_R": Vector((-0.240, 0.005, 1.435)),
    "elbow_R": Vector((-0.375, 0.015, 1.155)),
    "wrist_R": Vector((-0.465, -0.115, 0.925)),
    "hand_R": Vector((-0.478, -0.145, 0.880)),

    "clavicle_L": Vector((0.07, -0.01, 1.43)),
    "shoulder_L": Vector((0.242, -0.010, 1.442)),
    "elbow_L": Vector((0.288, 0.055, 1.145)),
    "wrist_L": Vector((0.278, -0.068, 0.865)),
    "hand_L": Vector((0.274, -0.095, 0.800)),

    # Legs & Feet (standing flat on pedestal Z=0.0)
    "hip_R": Vector((-0.118, 0.005, 0.935)),
    "knee_R": Vector((-0.188, -0.018, 0.505)),
    "ankle_R": Vector((-0.225, 0.025, 0.095)),
    "foot_ball_R": Vector((-0.242, -0.085, 0.024)),
    "foot_toe_R": Vector((-0.252, -0.155, 0.014)),

    "hip_L": Vector((0.118, -0.010, 0.935)),
    "knee_L": Vector((0.160, -0.072, 0.512)),
    "ankle_L": Vector((0.172, -0.075, 0.095)),
    "foot_ball_L": Vector((0.184, -0.195, 0.024)),
    "foot_toe_L": Vector((0.192, -0.265, 0.014)),
}

# Sword coordinates matched to Right Hand & reference slope
SWORD_MAIN = {
    "grip_center": Vector((-0.476, -0.142, 0.892)),
    "pommel_pos": Vector((-0.505, -0.145, 1.158)),
    "guard_pos": Vector((-0.466, -0.140, 0.818)),
    "tip_pos": Vector((-0.340, -0.132, 0.004)),
}

# Diagonal back-mounted scabbard & sheathed sword (draped OVER the cape)
SWORD_BACK = {
    "pommel_pos": Vector((-0.300, 0.237, 1.665)),
    "guard_pos": Vector((-0.205, 0.244, 1.385)),
    "scabbard_top": Vector((-0.195, 0.244, 1.355)),
    "scabbard_tip": Vector((0.405, 0.212, 0.440)),
}

# Lantern hanging straight beneath Left hand/hip (clearly left/front of scabbard tip in front view)
LANTERN_ANCHOR = Vector((0.268, -0.055, 0.725))

# Pedestal geometry dimensions (matched proportionally to 1.85m knight silhouette)
PEDESTAL = {
    "top_z": 0.000,
    "rim_z": 0.032,
    "radius_top": 0.80,
    "radius_rim_outer": 0.88,
    "radius_base": 0.96,
    "height": 0.44,
}


# ---------------------------------------------------------------------------
# Scene & Mesh helpers
# ---------------------------------------------------------------------------
def ensure_directories():
    """Ensure all required output and render directories exist."""
    for d in (REFERENCES_DIR, OUTPUT_DIR, RENDERS_DIR, TEXTURES_DIR):
        os.makedirs(d, exist_ok=True)


def clear_scene():
    """Reset the Blender scene cleanly for deterministic builds."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def setup_collections():
    """Create all Section 24 project collections and return lookup dict."""
    scene = bpy.context.scene
    root_col = scene.collection
    cols = {}
    for name in COLLECTIONS:
        if name in bpy.data.collections:
            col = bpy.data.collections[name]
        else:
            col = bpy.data.collections.new(name)
            root_col.children.link(col)
        cols[name] = col
    return cols


def link_object(obj, collection_name: str):
    """Link object exclusively into the named collection."""
    col = bpy.data.collections.get(collection_name)
    if col is None:
        col = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(col)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def set_smooth_shading(obj):
    """Apply smooth shading compatible with Blender 4.x and 5.x."""
    if obj.type != "MESH" or not obj.data:
        return
    mesh = obj.data
    for poly in mesh.polygons:
        poly.use_smooth = True


def add_weighted_normal(obj):
    """Add a Weighted Normal modifier when appropriate in Blender 5.x."""
    if obj.type != "MESH":
        return
    mod = obj.modifiers.new(name="WeightedNormal", type="WEIGHTED_NORMAL")
    mod.keep_sharp = True
    return mod


def add_subsurf(obj, levels: int = 1, render_levels: int | None = None):
    """Attach a Subdivision Surface modifier."""
    if obj.type != "MESH" or levels <= 0:
        return None
    mod = obj.modifiers.new(name="Subsurf", type="SUBSURF")
    mod.levels = levels
    mod.render_levels = render_levels if render_levels is not None else levels
    return mod


def add_solidify(obj, thickness: float = 0.004, offset: float = 0.0):
    """Give cloth or plate armor real physical shell thickness."""
    if obj.type != "MESH":
        return None
    mod = obj.modifiers.new(name="Solidify", type="SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_rim = True
    return mod


def assign_material(obj, mat_name: str):
    """Assign a named material from bpy.data.materials to obj."""
    if obj.type != "MESH":
        return
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        return
    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat


def apply_all_modifiers(obj):
    """Evaluate and apply modifiers cleanly in object mode without ops dependency if possible."""
    if obj.type != "MESH" or len(obj.modifiers) == 0:
        return
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(eval_obj)
    old_mesh = obj.data
    old_mats = list(old_mesh.materials)
    obj.modifiers.clear()
    obj.data = new_mesh
    new_mesh.name = old_mesh.name
    for m in old_mats:
        if m and m.name not in new_mesh.materials:
            new_mesh.materials.append(m)
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)


def generate_box_uvs(bm, scale: float = 2.0):
    """Create deterministic triplanar/box UV coordinates directly on a BMesh."""
    uv_layer = bm.loops.layers.uv.verify()
    for face in bm.faces:
        n = face.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in face.loops:
            co = loop.vert.co * scale
            if az >= ax and az >= ay:
                loop[uv_layer].uv = (co.x + 0.5, co.y + 0.5)
            elif ax >= ay and ax >= az:
                loop[uv_layer].uv = (co.y + 0.5, co.z)
            else:
                loop[uv_layer].uv = (co.x + 0.5, co.z)


def finalize_bmesh(bm, name: str, collection_name: str, mat_name: str | None = None,
                   smooth: bool = True, box_uv_scale: float = 1.6) -> bpy.types.Object:
    """Update normals, generate box UVs if missing, build Mesh object and link it."""
    bm.normal_update()
    if len(bm.loops.layers.uv) == 0:
        generate_box_uvs(bm, scale=box_uv_scale)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    link_object(obj, collection_name)
    if smooth:
        set_smooth_shading(obj)
    if mat_name:
        assign_material(obj, mat_name)
    return obj


def loft_rings(bm, rings, close_cap_start: bool = False, close_cap_end: bool = False):
    """Loft a sequence of equal-length Vector rings into quad faces inside BMesh."""
    vert_rings = []
    for ring in rings:
        v_ring = [bm.verts.new(Vector(p)) for p in ring]
        vert_rings.append(v_ring)
    n_rings = len(vert_rings)
    if n_rings < 2:
        return vert_rings
    n_pts = len(vert_rings[0])
    for r in range(n_rings - 1):
        r0 = vert_rings[r]
        r1 = vert_rings[r + 1]
        for i in range(n_pts):
            i_next = (i + 1) % n_pts
            try:
                bm.faces.new((r0[i], r0[i_next], r1[i_next], r1[i]))
            except ValueError:
                pass
    if close_cap_start and n_pts >= 3:
        try:
            bm.faces.new(list(reversed(vert_rings[0])))
        except ValueError:
            pass
    if close_cap_end and n_pts >= 3:
        try:
            bm.faces.new(vert_rings[-1])
        except ValueError:
            pass
    return vert_rings


def tube_along_points(bm, points, radii, radial_segs: int = 12,
                      cap_start: bool = True, cap_end: bool = True,
                      elliptical: tuple[float, float] = (1.0, 1.0)):
    """Sweep a smooth circular/elliptical tube along a 3D polyline inside BMesh."""
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return []
    rings = []
    prev_normal = None
    for idx, pt in enumerate(pts):
        if idx == 0:
            tangent = (pts[1] - pts[0]).normalized()
        elif idx == len(pts) - 1:
            tangent = (pts[-1] - pts[-2]).normalized()
        else:
            tangent = (pts[idx + 1] - pts[idx - 1]).normalized()
        if tangent.length < 1e-6:
            tangent = Vector((0.0, 0.0, 1.0))

        if prev_normal is None:
            ref = Vector((0.0, 1.0, 0.0)) if abs(tangent.y) < 0.9 else Vector((1.0, 0.0, 0.0))
            binorm = tangent.cross(ref).normalized()
            norm = binorm.cross(tangent).normalized()
        else:
            # Parallel transport to minimize twist
            norm = prev_normal - tangent * prev_normal.dot(tangent)
            if norm.length < 1e-5:
                ref = Vector((0.0, 1.0, 0.0)) if abs(tangent.y) < 0.9 else Vector((1.0, 0.0, 0.0))
                norm = tangent.cross(ref).normalized()
            else:
                norm.normalize()
            binorm = tangent.cross(norm).normalized()
        prev_normal = norm

        rad = radii[idx] if isinstance(radii, (list, tuple)) else radii
        ring = []
        for s in range(radial_segs):
            ang = 2.0 * math.pi * s / radial_segs
            offset = (norm * math.cos(ang) * elliptical[0] + binorm * math.sin(ang) * elliptical[1]) * rad
            ring.append(pt + offset)
        rings.append(ring)

    return loft_rings(bm, rings, close_cap_start=cap_start, close_cap_end=cap_end)


def create_curved_plate_patch(name: str, collection_name: str, center_pts, widths,
                              arc_angles, radial_steps: int = 10, thickness: float = 0.005,
                              mat_name: str = "MAT_Steel_Worn",
                              flare_ends: float = 0.0, crease_center: float = 0.0,
                              subdiv: int = 1):
    """Build a curved parametric armor plate with real shell thickness and soft bevel."""
    bm = bmesh.new()
    n_u = len(center_pts)
    grid = []
    for iu in range(n_u):
        p = Vector(center_pts[iu])
        w = widths[iu]
        ang_span = arc_angles[iu] if isinstance(arc_angles, (list, tuple)) else arc_angles
        row = []
        for iv in range(radial_steps):
            t = iv / max(1, radial_steps - 1) - 0.5  # -0.5 .. +0.5
            ang = t * ang_span
            # Local curved surface wrapping around -Y forward direction
            rad_x = math.sin(ang) * w
            rad_y = (1.0 - math.cos(ang)) * w * 0.72
            ridge = crease_center * max(0.0, 1.0 - abs(t) * 4.5)
            flare = flare_ends * (1.0 if iu in (0, n_u - 1) else 0.0)
            v = bm.verts.new(Vector((p.x + rad_x, p.y + rad_y - ridge - flare * 0.5, p.z + flare)))
            row.append(v)
        grid.append(row)

    for iu in range(n_u - 1):
        for iv in range(radial_steps - 1):
            bm.faces.new((
                grid[iu][iv],
                grid[iu][iv + 1],
                grid[iu + 1][iv + 1],
                grid[iu + 1][iv],
            ))

    obj = finalize_bmesh(bm, name, collection_name, mat_name=mat_name, smooth=True)
    if thickness > 0.0:
        add_solidify(obj, thickness=thickness, offset=0.0)
    if subdiv > 0:
        add_subsurf(obj, levels=subdiv)
    return obj


def add_rivet_strip(name: str, collection_name: str, points, radius: float = 0.0045,
                    mat_name: str = "MAT_Brass_Aged", segments: int = 8):
    """Build a single lightweight object containing instanced dome rivets along seam points."""
    bm = bmesh.new()
    for pt_info in points:
        if len(pt_info) == 2:
            pt, normal = pt_info
        else:
            pt, normal = pt_info, Vector((0.0, -1.0, 0.0))
        pt = Vector(pt)
        n = Vector(normal).normalized()
        rot = Vector((0.0, 0.0, 1.0)).rotation_difference(n).to_matrix().to_4x4()
        mat = Matrix.Translation(pt) @ rot
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius)
        for v in res["verts"]:
            if v.co.z < -radius * 0.25:
                v.co.z = -radius * 0.25
            v.co.z *= 0.65
            v.co = mat @ v.co
    obj = finalize_bmesh(bm, name, collection_name, mat_name=mat_name, smooth=True)
    return obj
