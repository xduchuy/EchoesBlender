"""Export The Drowned Sanctuary Blender scene to an optimized web-ready .glb (glTF 2.0 + Draco).

Usage:
    blender -b output/drowned_sanctuary.blend --python scripts/export_glb.py
    blender -b output/drowned_sanctuary.blend --python scripts/export_glb.py -- --output public/models/drowned_sanctuary.glb --max-subdiv 1
"""

import argparse
import math
import os
import sys
import time
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).resolve().parent)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import bpy
from mathutils import Vector, noise

from config import COLORS


EXCLUDED_COLLECTIONS = {"00_REFERENCE", "10_ATMOSPHERE", "11_LIGHTING", "12_CAMERAS"}


def _parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Export Drowned Sanctuary scene to web-optimized GLB.")
    parser.add_argument(
        "--output",
        default=os.path.join(PROJECT_ROOT, "public", "models", "drowned_sanctuary.glb"),
        help="Output .glb path.",
    )
    parser.add_argument(
        "--max-subdiv",
        type=int,
        default=1,
        help="Cap Subdivision Surface render levels for web triangle budget.",
    )
    parser.add_argument(
        "--no-draco",
        action="store_true",
        help="Disable Draco mesh compression.",
    )
    return parser.parse_args(argv)


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _mix_rgb(c1, c2, t: float):
    t = _clamp01(t)
    inv = 1.0 - t
    return (
        c1[0] * inv + c2[0] * t,
        c1[1] * inv + c2[1] * t,
        c1[2] * inv + c2[2] * t,
    )


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = _clamp01((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def _sample_vertex_color(mat_name: str, wp: Vector, wn: Vector):
    """Compute procedural PBR-matched linear vertex color matching Blender shader palette."""
    n_macro = 0.5 + 0.5 * noise.noise(wp * 0.14)
    n_med = 0.5 + 0.5 * noise.noise(wp * 0.85)
    n_strata = 0.5 + 0.5 * noise.noise(Vector((wp.x * 0.09, wp.y * 0.09, wp.z * 1.15)))
    n_patch = 0.5 + 0.5 * noise.noise(wp * 0.12 + Vector((11.3, -7.1, 3.7)))

    if mat_name in ("MAT_Rock_Cliff", "MAT_Rock_Dark"):
        if mat_name == "MAT_Rock_Dark":
            base = _mix_rgb((0.025, 0.030, 0.029), (0.075, 0.080, 0.070), n_strata)
        else:
            t = _smoothstep(0.25, 0.82, n_strata)
            mid = _mix_rgb((0.048, 0.049, 0.041), (0.130, 0.123, 0.102), _clamp01(t * 1.4))
            base = _mix_rgb(mid, (0.220, 0.204, 0.162), _smoothstep(0.45, 0.92, t))
            # Bedding plane striations
            strata_band = 0.5 + 0.5 * math.sin(wp.z * 2.2 + n_macro * 4.2)
            base = _mix_rgb(base, (base[0] * 0.68, base[1] * 0.68, base[2] * 0.66), 0.35 * (1.0 - strata_band))

        base = _mix_rgb(base, (base[0] * 0.72, base[1] * 0.73, base[2] * 0.70), 0.35 * (1.0 - n_med))
        # Upward grass / olive turf on cliff ledges
        up = _smoothstep(0.50, 0.76, wn.z)
        patch = _smoothstep(0.32, 0.62, n_patch)
        z_ok = _smoothstep(2.4, 5.2, wp.z)
        base = _mix_rgb(base, COLORS["grass_muted"][:3], up * patch * z_ok * 0.92)
        # Wet shoreline rock
        wet = 1.0 - _smoothstep(-0.3, 2.0, wp.z)
        base = _mix_rgb(base, (0.022, 0.026, 0.023), wet * 0.85)
        return (*base, 1.0)

    if mat_name.startswith("MAT_Limestone") or mat_name == "MAT_Statue_Weathered":
        if mat_name == "MAT_Limestone_Light":
            ca, cb = COLORS["limestone_sunlit"][:3], (0.31, 0.28, 0.21)
            moss_amt, wet_h = 0.18, 2.2
        elif mat_name == "MAT_Limestone_Wet":
            ca, cb = (0.14, 0.145, 0.12), COLORS["limestone_shadow"][:3]
            moss_amt, wet_h = 0.38, 3.6
        elif mat_name == "MAT_Limestone_Eroded":
            ca, cb = COLORS["limestone_eroded"][:3], COLORS["limestone_shadow"][:3]
            moss_amt, wet_h = 0.30, 2.6
        elif mat_name == "MAT_Limestone_Moss":
            ca, cb = COLORS["limestone_mid"][:3], COLORS["limestone_shadow"][:3]
            moss_amt, wet_h = 0.62, 2.8
        elif mat_name == "MAT_Statue_Weathered":
            ca, cb = COLORS["statue_stone"][:3], (0.24, 0.23, 0.19)
            moss_amt, wet_h = 0.34, 2.4
        else:
            ca, cb = COLORS["limestone_sunlit"][:3], COLORS["limestone_mid"][:3]
            moss_amt, wet_h = 0.25, 2.4

        # Subtle course banding
        course = 0.5 + 0.5 * math.sin(wp.z * 3.8 + n_med * 0.6)
        base = _mix_rgb(ca, cb, _clamp01(n_med * 0.65 + (1.0 - course) * 0.25))
        base = _mix_rgb(base, COLORS["limestone_shadow"][:3], _clamp01(n_macro * 0.55))

        # Upward moss on ledges & crowns
        up = _smoothstep(0.38, 0.85, wn.z)
        base = _mix_rgb(base, COLORS["moss_olive"][:3], _clamp01(up * n_macro * moss_amt * 1.5))

        # Waterline dampness
        wet = 1.0 - _smoothstep(-0.2, wet_h, wp.z)
        base = _mix_rgb(base, (0.042, 0.048, 0.040), wet * (0.65 + 0.35 * n_med))
        return (*base, 1.0)

    if mat_name == "MAT_Bark_Ancient":
        grain = 0.5 + 0.5 * noise.noise(Vector((wp.x * 2.2, wp.y * 2.2, wp.z * 0.5)))
        base = _mix_rgb((0.032, 0.025, 0.019), (0.088, 0.072, 0.052), grain)
        up = _smoothstep(0.42, 0.86, wn.z)
        base = _mix_rgb(base, COLORS["moss_dark"][:3], up * n_patch * 0.72)
        wet = 1.0 - _smoothstep(-0.2, 1.8, wp.z)
        return (*_mix_rgb(base, (0.018, 0.020, 0.017), wet * 0.75), 1.0)

    if mat_name == "MAT_Submerged_Stone":
        base = _mix_rgb((0.028, 0.036, 0.032), (0.075, 0.082, 0.068), n_med)
        return (*base, 1.0)

    if mat_name == "MAT_Ground_Grass":
        base = _mix_rgb(COLORS["moss_dark"][:3], COLORS["grass_muted"][:3], n_med)
        return (*base, 1.0)

    if mat_name == "MAT_Ground_Mud":
        return (*COLORS["mud_dark"][:3], 1.0)

    if mat_name == "MAT_Water_Dark":
        return (*COLORS["water_deep"][:3], 1.0)

    if mat_name == "MAT_Dark_Silhouette":
        return (0.02, 0.024, 0.024, 1.0)

    return (*COLORS["limestone_mid"][:3], 1.0)


def _bake_vertex_colors(obj: bpy.types.Object, baked_meshes: set) -> None:
    """Create deterministic linear vertex colors ('Col') on mesh vertices for WebGL PBR."""
    mesh = obj.data
    if not mesh or len(mesh.vertices) == 0 or mesh in baked_meshes:
        return
    baked_meshes.add(mesh)

    mat_names = [m.name if m else "" for m in mesh.materials]
    default_mat = mat_names[0] if mat_names else ""

    # Determine dominant material per vertex from polygon slots
    vert_mat = [default_mat] * len(mesh.vertices)
    for poly in mesh.polygons:
        mname = mat_names[poly.material_index] if poly.material_index < len(mat_names) else default_mat
        for vid in poly.vertices:
            vert_mat[vid] = mname

    attr = mesh.color_attributes.get("Col")
    if attr and (attr.domain != "POINT" or attr.data_type != "FLOAT_COLOR"):
        mesh.color_attributes.remove(attr)
        attr = None
    if attr is None:
        attr = mesh.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
    mesh.color_attributes.active_color = attr

    mw = obj.matrix_world
    rot = mw.to_3x3()
    flat_colors = []
    extend = flat_colors.extend
    for i, v in enumerate(mesh.vertices):
        wp = mw @ v.co
        wn = (rot @ v.normal).normalized()
        extend(_sample_vertex_color(vert_mat[i], wp, wn))
    attr.data.foreach_set("color", flat_colors)


def _is_excluded(obj: bpy.types.Object) -> bool:
    for col in obj.users_collection:
        if col.name in EXCLUDED_COLLECTIONS:
            return True
    return obj.type not in {"MESH", "CURVE"}


def prepare_and_export(output_path: str, max_subdiv: int, use_draco: bool) -> int:
    t0 = time.perf_counter()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    print(f"[ExportGLB] Starting export -> {output_path}", flush=True)

    # Deselect everything
    bpy.ops.object.select_all(action="DESELECT")

    # Convert curves to meshes so root networks export cleanly with modifiers applied and vertex colors
    curve_objs = [o for o in list(bpy.data.objects) if o.type == "CURVE" and not _is_excluded(o)]
    for obj in curve_objs:
        obj.hide_viewport = False
        obj.hide_set(False)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.convert(target="MESH")
        obj.select_set(False)
    print(f"[ExportGLB] Converted {len(curve_objs)} curves in {time.perf_counter() - t0:.1f}s", flush=True)

    # Apply modifiers cleanly & bake vertex colors on every exported mesh
    export_objs = [o for o in list(bpy.data.objects) if o.type == "MESH" and not _is_excluded(o)]
    total_verts = 0
    total_polys = 0
    baked_meshes = set()

    for obj in export_objs:
        obj.hide_viewport = False
        obj.hide_set(False)

        # Cap Subdivision modifiers for optimal web polycount
        for mod in obj.modifiers:
            if mod.type == "SUBSURF":
                mod.levels = min(mod.levels, max_subdiv)
                mod.render_levels = min(mod.render_levels, max_subdiv)

        if obj.modifiers and obj.data.users == 1:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            for mod in list(obj.modifiers):
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except Exception:
                    pass
            obj.select_set(False)

        # Bake vertex colors directly into mesh points
        _bake_vertex_colors(obj, baked_meshes)
        total_verts += len(obj.data.vertices)
        total_polys += len(obj.data.polygons)

    print(
        f"[ExportGLB] Baked vertex colors on {len(baked_meshes)} unique meshes "
        f"({total_verts} total verts, {total_polys} total polys) in {time.perf_counter() - t0:.1f}s",
        flush=True,
    )

    # Simplify material node trees to clean Principled BSDF with Vertex Color linked for glTF fidelity
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue
        if mat.name.startswith("MAT_Fog"):
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        out = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"), None)
        if not bsdf or not out:
            continue

        # Replace complex procedural Base Color link with Color Attribute 'Col' for glTF
        for link in list(bsdf.inputs["Base Color"].links):
            nt.links.remove(link)
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])

        # Clear unexportable procedural roughness/normal links and assign balanced scalar PBR defaults
        for sock_name in ("Roughness", "Normal", "Specular IOR Level"):
            if sock_name in bsdf.inputs:
                for link in list(bsdf.inputs[sock_name].links):
                    nt.links.remove(link)

        if mat.name == "MAT_Water_Dark":
            bsdf.inputs["Roughness"].default_value = 0.08
            if "Specular IOR Level" in bsdf.inputs:
                bsdf.inputs["Specular IOR Level"].default_value = 0.55
        elif "Wet" in mat.name or "Submerged" in mat.name:
            bsdf.inputs["Roughness"].default_value = 0.36
        elif "Bark" in mat.name:
            bsdf.inputs["Roughness"].default_value = 0.90
        elif "Rock" in mat.name:
            bsdf.inputs["Roughness"].default_value = 0.88
        else:
            bsdf.inputs["Roughness"].default_value = 0.84

    # Select all exportable objects
    bpy.ops.object.select_all(action="DESELECT")
    for obj in export_objs:
        obj.select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(output_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_normals=True,
        export_materials="EXPORT",
        export_vertex_color="NAME",
        export_vertex_color_name="Col",
        export_animations=False,
        export_draco_mesh_compression_enable=use_draco,
        export_draco_mesh_compression_level=6,
    )

    elapsed = time.perf_counter() - t0
    size_mb = os.path.getsize(output_path) / (1024.0 * 1024.0)
    print(
        f"[ExportGLB] Exported {len(export_objs)} meshes "
        f"({total_verts} verts, {total_polys} polys) -> {output_path} "
        f"({size_mb:.2f} MB) in {elapsed:.1f}s [draco={use_draco}]"
    )
    return 0


def main() -> int:
    args = _parse_args()
    return prepare_and_export(
        output_path=args.output,
        max_subdiv=args.max_subdiv,
        use_draco=not args.no_draco,
    )


if __name__ == "__main__":
    sys.exit(main())
