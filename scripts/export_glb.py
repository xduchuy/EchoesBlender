"""Optimize and export `drowned_sanctuary_v2.blend` to a baked PBR Web-ready `.glb`.

Usage:
    blender -b output/drowned_sanctuary_v2.blend --python scripts/export_glb.py -- \
        --output public/models/drowned_sanctuary.glb --max-subdiv 1
"""

import argparse
import json
import os
import struct
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import bpy

SCRIPTS_DIR = str(Path(__file__).resolve().parent)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import pbr_bake  # noqa: E402


EXCLUDED_COLLECTIONS = {"00_REFERENCE", "10_ATMOSPHERE", "11_LIGHTING", "12_CAMERAS"}


def _parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Bake PBR atlases & export Sanctuary GLB.")
    parser.add_argument(
        "--blend",
        default=None,
        help="Optional .blend file to open before exporting.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(PROJECT_ROOT, "public", "models", "drowned_sanctuary.glb"),
        help="Destination .glb path.",
    )
    parser.add_argument(
        "--max-subdiv",
        type=int,
        default=1,
        help="Clamp subdivision levels for WebGL performance before baking.",
    )
    parser.add_argument(
        "--bake-scale",
        type=float,
        default=1.0,
        help="Resolution multiplier for baked atlases (1.0 = 2K hero / 1K secondary).",
    )
    parser.add_argument(
        "--webp-quality",
        type=int,
        default=84,
        help="Embedded WebP image quality for glTF textures (0..100).",
    )
    parser.add_argument(
        "--no-draco",
        action="store_true",
        help="Disable Draco mesh compression.",
    )
    return parser.parse_args(argv)


def _delete_excluded_collections() -> None:
    """Remove scene helper/camera/fog objects cleanly from the in-memory export copy."""
    to_remove = set()
    for cname in EXCLUDED_COLLECTIONS:
        col = bpy.data.collections.get(cname)
        if col:
            for obj in col.all_objects:
                to_remove.add(obj)

    for obj in list(to_remove):
        bpy.data.objects.remove(obj, do_unlink=True)

    for cname in EXCLUDED_COLLECTIONS:
        col = bpy.data.collections.get(cname)
        if col:
            bpy.data.collections.remove(col)


def _clamp_subdivs(max_subdiv: int) -> None:
    """Cap active Subsurf modifiers before destructive modifier apply & baking."""
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for mod in obj.modifiers:
            if mod.type == "SUBSURF":
                mod.levels = min(mod.levels, max_subdiv)
                mod.render_levels = min(mod.render_levels, max_subdiv)


def _simplify_water_for_gltf() -> None:
    """Ensure Water_Flooded_Basin keeps a clean Principled BSDF without Cycles Volume nodes."""
    water_obj = bpy.data.objects.get("Water_Flooded_Basin")
    if water_obj is None or water_obj.type != "MESH":
        return
    if water_obj.data and not water_obj.data.uv_layers:
        water_obj.data.uv_layers.new(name="UVMap")
    mat = bpy.data.materials.get("MAT_Water_Dark")
    if mat is None:
        return
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.015, 0.025, 0.022, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.09
    bsdf.inputs["Metallic"].default_value = 0.05
    bsdf.inputs["IOR"].default_value = 1.333
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def _simplify_silhouette_for_gltf() -> None:
    """Ensure Causeway_Scale_Figure keeps an ultra-light fallback material."""
    fig = bpy.data.objects.get("Causeway_Scale_Figure")
    if fig is None or fig.type != "MESH":
        return
    mat = bpy.data.materials.get("MAT_Dark_Silhouette")
    if mat and mat.use_nodes:
        nt = mat.node_tree
        bsdf = pbr_bake.find_node_by_bl_idname(nt, "ShaderNodeBsdfPrincipled")
        out = pbr_bake.find_node_by_bl_idname(nt, "ShaderNodeOutputMaterial")
        if bsdf and out:
            for inp_name in ("Base Color", "Roughness", "Normal"):
                inp = bsdf.inputs.get(inp_name)
                if inp and inp.is_linked:
                    for lk in list(inp.links):
                        nt.links.remove(lk)
            bsdf.inputs["Base Color"].default_value = (0.02, 0.022, 0.025, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.85


def _collect_atlas_groups() -> List[tuple[str, int, List[bpy.types.Object], float]]:
    """Group Sanctuary objects into 5 tightly packed PBR atlases without merging meshes."""
    all_objs = {o.name: o for o in bpy.data.objects}
    assigned = {"Water_Flooded_Basin", "Causeway_Scale_Figure"}

    def _pick(names: Sequence[str]) -> List[bpy.types.Object]:
        out = []
        for n in names:
            o = all_objs.get(n)
            if o is not None and o.name not in assigned and o.type in ("MESH", "CURVE"):
                out.append(o)
                assigned.add(o.name)
        return out

    def _pick_collection(cname: str, exclude_names: set[str] | None = None) -> List[bpy.types.Object]:
        col = bpy.data.collections.get(cname)
        if not col:
            return []
        ex = exclude_names or set()
        out = []
        for o in col.all_objects:
            if o.name in assigned or o.name in ex or o.type not in ("MESH", "CURVE"):
                continue
            out.append(o)
            assigned.add(o.name)
        return out

    # 1. Hero Architecture (towers, main apse arcade) -> 2048px
    hero_arch = _pick([
        "Tower_LeftFront_Main",
        "Tower_LeftBastion",
        "Tower_RightFront_Complex",
        "Arcade_Rear_Apse",
        "Tower_LeftRear_Belfry",
        "Tower_RightRear_Belfry",
    ])

    # 2. Central Monumental Statue + Pedestal -> 1024px
    statue_objs = _pick_collection("05_STATUE")

    # 3. Foreground & Midground Stratified Cliffs -> 1024px (separated from Terrain_Seabed for crisp detail)
    cliff_objs = _pick_collection("02_CLIFFS")

    # 4. Roots, Courtyard Plaza, Causeway Bridge & Flooded Rubble -> 1024px
    roots_rubble = (
        _pick_collection("07_ROOTS")
        + _pick_collection("04_COURTYARD")
        + _pick_collection("08_RUBBLE")
    )

    # 5. Secondary Architecture, Terrain Seabed, Distant Mountains & Reeds -> 1024px
    secondary = (
        _pick(["Walls_Connecting_Ruins", "Tower_Distant_MistRuin"])
        + _pick_collection("01_TERRAIN")
        + _pick_collection("09_VEGETATION")
        + _pick_collection("03_ARCHITECTURE")
    )

    return [
        ("Sanctuary_HeroArch", 2048, hero_arch, 2.8),
        ("Sanctuary_Statue", 1024, statue_objs, 1.8),
        ("Sanctuary_Cliffs", 1024, cliff_objs, 3.2),
        ("Sanctuary_RootsRubble", 1024, roots_rubble, 1.6),
        ("Sanctuary_SecondaryTrim", 1024, secondary, 2.6),
    ]


def _inspect_glb(glb_path: str) -> Dict[str, object]:
    """Read GLB binary header + JSON chunk to verify textures, primitives, and byte size."""
    raw = Path(glb_path).read_bytes()
    jlen = struct.unpack("<I", raw[12:16])[0]
    g = json.loads(raw[20 : 20 + jlen].decode("utf-8"))
    mats = g.get("materials", [])
    imgs = g.get("images", [])
    meshes = g.get("meshes", [])
    prim_count = sum(len(m.get("primitives", [])) for m in meshes)
    return {
        "bytes": len(raw),
        "materials": len(mats),
        "images": len(imgs),
        "image_mimes": sorted({i.get("mimeType", "?") for i in imgs}),
        "meshes": len(meshes),
        "primitives": prim_count,
        "draco_used": any(
            "KHR_draco_mesh_compression" in p.get("extensions", {})
            for m in meshes
            for p in m.get("primitives", [])
        ),
    }


def prepare_and_export(
    output_path: str,
    max_subdiv: int,
    use_draco: bool,
    bake_scale: float = 1.0,
    webp_quality: int = 84,
) -> int:
    """Bake procedural materials into packed PBR atlases and export compressed GLB."""
    t0 = time.perf_counter()
    _delete_excluded_collections()
    _clamp_subdivs(max_subdiv)

    water_obj = bpy.data.objects.get("Water_Flooded_Basin")
    ao_hide = [water_obj] if water_obj else []

    tmp_tex_dir = os.path.join(tempfile.gettempdir(), "echoes_sanctuary_bake")
    groups = _collect_atlas_groups()

    for atlas_name, base_res, objs, ao_dist in groups:
        if not objs:
            continue
        res = max(256, int(round((base_res * bake_scale) / 64.0)) * 64)
        ao_samples = 6 if atlas_name in ("Sanctuary_HeroArch", "Sanctuary_Statue") else 4
        print(f"[ExportSanctuary] Baking atlas {atlas_name}: {len(objs)} objs @ {res}x{res}...", flush=True)
        pbr_bake.bake_pbr_atlas(
            atlas_name=atlas_name,
            objects=objs,
            resolution=res,
            samples_emit=1,
            samples_normal=1,
            samples_ao=ao_samples,
            ao_distance=ao_dist,
            island_margin=0.006,
            texture_dir=os.path.join(tmp_tex_dir, atlas_name),
            ao_occluders_hide=ao_hide,
        )

    _simplify_water_for_gltf()
    _simplify_silhouette_for_gltf()

    # Purge unused procedural shaders/temp meshes so only baked atlases + water export.
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    output_abs = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_abs), exist_ok=True)
    tmp_glb = output_abs + ".tmp.glb"

    export_kwargs = dict(
        filepath=tmp_glb,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
        export_image_format="WEBP",
        export_image_quality=webp_quality,
        export_extras=False,
        export_cameras=False,
        export_lights=False,
    )
    if use_draco:
        export_kwargs.update(
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
            export_draco_position_quantization=14,
            export_draco_normal_quantization=10,
            export_draco_texcoord_quantization=12,
        )

    bpy.ops.export_scene.gltf(**export_kwargs)
    if os.path.exists(output_abs):
        os.replace(tmp_glb, output_abs)
    else:
        os.rename(tmp_glb, output_abs)

    stats = _inspect_glb(output_abs)
    dt = time.perf_counter() - t0
    print(f"[ExportSanctuary] Exported in {dt:.1f}s -> {output_abs}")
    print(f"[ExportSanctuary] GLB stats: {json.dumps(stats)}")
    return 0


def main() -> int:
    args = _parse_args()
    if args.blend:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.blend))
    return prepare_and_export(
        output_path=args.output,
        max_subdiv=args.max_subdiv,
        use_draco=not args.no_draco,
        bake_scale=args.bake_scale,
        webp_quality=args.webp_quality,
    )


if __name__ == "__main__":
    raise SystemExit(main())
