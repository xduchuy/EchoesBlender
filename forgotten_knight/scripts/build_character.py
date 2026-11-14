"""Main orchestrator & CLI entrypoint for THE FORGOTTEN KNIGHT reconstruction pipeline.
Usage:
  blender -b --python scripts/build_character.py -- --quality preview
  blender -b --python scripts/build_character.py -- --quality review
  blender -b --python scripts/build_character.py -- --quality final
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

# Ensure sibling modules & root scripts (`pbr_bake`) import cleanly via `blender -b --python`
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(os.path.dirname(_THIS_DIR))
_ROOT_SCRIPTS = os.path.join(_ROOT_DIR, "scripts")
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
if _ROOT_SCRIPTS not in sys.path:
    sys.path.append(_ROOT_SCRIPTS)

import bpy
from mathutils import Vector

import config
import pbr_bake
import materials
import character_body
import helmet_generator
import armor_generator
import chainmail_generator
import cloth_generator
import equipment_generator
import sword_generator
import lantern_generator
import pedestal
import rigging
import lighting
import cameras
import render


def _parse_cli_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Build & render THE FORGOTTEN KNIGHT in Blender")
    parser.add_argument("--quality", choices=["preview", "review", "final"], default="preview",
                        help="Render quality preset")
    parser.add_argument("--detail", choices=["LOW", "MEDIUM", "HIGH"], default=None,
                        help="Geometry subdivision/chainmail density override")
    parser.add_argument("--view", choices=["front", "back", "sheet", "all"], default="all",
                        help="Which views to render")
    parser.add_argument("--samples", type=int, default=None, help="Explicit Cycles sample override")
    parser.add_argument("--closeups", action="store_true", help="Also render upper front/rear closeups")
    parser.add_argument("--skip-render", action="store_true", help="Build .blend and .glb without rendering")
    parser.add_argument("--skip-glb", action="store_true", help="Skip .glb export")
    parser.add_argument("--output-blend", default=os.path.join(config.OUTPUT_DIR, "forgotten_knight_v2.blend"),
                        help="Output .blend path (defaults to V2 path, preserving baseline)")
    parser.add_argument("--output-glb", default=os.path.join(config.OUTPUT_DIR, "forgotten_knight_v2.glb"),
                        help="Output .glb path (also copied to public/models/forgotten_knight.glb when --sync-web is set)")
    parser.add_argument("--render-dir", default=os.path.join(config.RENDERS_DIR, "v2"),
                        help="Output directory for character sheet & closeup renders")
    parser.add_argument("--max-subdiv", type=int, default=1, help="Clamp subdiv before baking GLB")
    parser.add_argument("--bake-scale", type=float, default=1.0, help="Atlas resolution scale (1.0 = 1K/512px)")
    parser.add_argument("--webp-quality", type=int, default=86, help="WebP quality (0..100)")
    parser.add_argument("--sync-web", action="store_true",
                        help="Also copy exported GLB to public/models/forgotten_knight.glb")
    return parser.parse_args(argv)


def _world_bbox(obj):
    """Return min/max Vector in world coordinates."""
    deps = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(deps)
    pts = [eo.matrix_world @ Vector(c) for c in eo.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def validate_character(rig_info: dict) -> dict:
    """Automated geometry, grounding, material, rig, and hierarchy validation (Section 27)."""
    checks = {}
    warnings = []

    # 1. Total character height & proportions
    helm = bpy.data.objects.get("Helm_Skull")
    boot_l = bpy.data.objects.get("Armor_Boot_L")
    boot_r = bpy.data.objects.get("Armor_Boot_R")
    ped = bpy.data.objects.get("Pedestal_Stone_Base")
    sword_blade = bpy.data.objects.get("Weapon_Longsword_Blade")
    scab_back = bpy.data.objects.get("Weapon_Back_Scabbard")
    lantern = bpy.data.objects.get("Lantern_Frame_Housing")
    cape = bpy.data.objects.get("Cape_Back_Cloak")

    if helm and boot_l and boot_r:
        _, hmax = _world_bbox(helm)
        bl_min, _ = _world_bbox(boot_l)
        br_min, _ = _world_bbox(boot_r)
        min_foot_z = min(bl_min.z, br_min.z)
        height = hmax.z - min_foot_z
        checks["height_m"] = round(height, 4)
        checks["boot_l_min_z"] = round(bl_min.z, 4)
        checks["boot_r_min_z"] = round(br_min.z, 4)
        if not (1.75 <= height <= 1.98):
            warnings.append(f"Character height {height:.3f}m outside [1.75, 1.98]m")
        if abs(bl_min.z) > 0.025 or abs(br_min.z) > 0.025:
            warnings.append(f"Boot ground contact offset L={bl_min.z:.4f}, R={br_min.z:.4f}")
    else:
        warnings.append("Missing core helmet or boot meshes")

    if ped:
        _, pmax = _world_bbox(ped)
        checks["pedestal_top_z"] = round(pmax.z, 4)

    if sword_blade:
        smin, _ = _world_bbox(sword_blade)
        checks["sword_tip_z"] = round(smin.z, 4)
        if smin.z < -0.015 or smin.z > 0.04:
            warnings.append(f"Longsword tip Z={smin.z:.4f} deviates from pedestal top")

    # 2. Check all required materials & collections exist and meshes have materials assigned
    missing_mats = [m for m in config.MATERIAL_NAMES if bpy.data.materials.get(m) is None]
    missing_cols = [c for c in config.COLLECTIONS if bpy.data.collections.get(c) is None]
    checks["missing_materials"] = missing_mats
    checks["missing_collections"] = missing_cols

    unshaded_meshes = [
        o.name for o in bpy.data.objects
        if o.type == "MESH" and not o.hide_render and len(o.data.materials) == 0
    ]
    checks["unshaded_meshes"] = unshaded_meshes
    if missing_mats:
        warnings.append(f"Missing materials: {missing_mats}")
    if unshaded_meshes:
        warnings.append(f"Meshes without material: {unshaded_meshes}")

    # 3. Poly & bone counts (excluding hidden reference plane)
    total_verts = 0
    total_polys = 0
    deps = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.hide_render:
            me = o.evaluated_get(deps).data
            total_verts += len(me.vertices)
            total_polys += len(me.polygons)

    checks["total_vertices"] = total_verts
    checks["total_polygons"] = total_polys
    checks["rig_bones"] = rig_info.get("bone_count", 0)
    checks["rigid_bound_meshes"] = rig_info.get("rigid_bound", 0)
    checks["deform_bound_meshes"] = rig_info.get("deform_bound", 0)
    checks["has_cape_folds"] = cape is not None and len(cape.data.polygons) > 100
    checks["has_back_scabbard"] = scab_back is not None
    checks["has_lantern"] = lantern is not None
    checks["warnings"] = warnings
    checks["passed"] = len(warnings) == 0
    return checks


def _simplify_unbaked_utility_mats() -> None:
    """Keep inner helm void dark matte and lantern ember/glass crisp for glTF."""
    void_mat = bpy.data.materials.get("MAT_Helm_Void")
    if void_mat and void_mat.use_nodes:
        bsdf = pbr_bake.find_node_by_bl_idname(void_mat.node_tree, "ShaderNodeBsdfPrincipled")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.004, 0.004, 0.005, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.98
    glass_mat = bpy.data.materials.get("MAT_Glass_Lantern")
    if glass_mat and glass_mat.use_nodes:
        bsdf = pbr_bake.find_node_by_bl_idname(glass_mat.node_tree, "ShaderNodeBsdfPrincipled")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.88, 0.72, 0.42, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.28
            if "Alpha" in bsdf.inputs:
                bsdf.inputs["Alpha"].default_value = 0.48
        glass_mat.blend_method = "BLEND" if hasattr(glass_mat, "blend_method") else "BLEND"


def export_glb(glb_path: str, max_subdiv: int = 1, bake_scale: float = 1.0, webp_quality: int = 86):
    """Bake 4 PBR atlases (preserving Armature + animations) and export glTF 2.0 binary (.glb)."""
    export_cols = [
        "01_BODY", "02_ARMATURE", "03_HELMET", "04_HOOD", "05_TORSO_ARMOR",
        "06_ARM_ARMOR", "07_HANDS", "08_CHAINMAIL", "09_TUNIC", "10_CAPE",
        "11_LEG_ARMOR", "12_BELTS", "13_WEAPONS", "14_LANTERN", "15_PEDESTAL",
    ]
    # Remove studio lighting/backdrop/cameras from in-memory export copy
    for col_name in ("00_REFERENCE", "16_LIGHTING", "17_CAMERAS"):
        col = bpy.data.collections.get(col_name)
        if col:
            for obj in list(col.all_objects):
                bpy.data.objects.remove(obj, do_unlink=True)

    # Clamp Subsurf levels on export copy before modifier apply & Cycles bake
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == "SUBSURF":
                    mod.levels = min(mod.levels, max_subdiv)
                    mod.render_levels = min(mod.render_levels, max_subdiv)

    all_objs = {o.name: o for o in bpy.data.objects}
    skip_bake = {"Helm_InnerShadow", "Lantern_Glass_Chamber", "Lantern_Inner_Chamber"}
    assigned = set(skip_bake)

    def _collect(col_names):
        res = []
        for cn in col_names:
            c = bpy.data.collections.get(cn)
            if c:
                for o in c.all_objects:
                    if o.type == "MESH" and not o.hide_render and o.name not in assigned:
                        res.append(o)
                        assigned.add(o.name)
        return res

    # Group logically into 4 compact PBR atlases
    armor_steel_objs = _collect(["03_HELMET", "05_TORSO_ARMOR", "06_ARM_ARMOR", "07_HANDS", "14_LANTERN"])
    leather_objs = []
    for cn in ("11_LEG_ARMOR", "13_WEAPONS", "12_BELTS"):
        col = bpy.data.collections.get(cn)
        if not col:
            continue
        for o in col.all_objects:
            if o.type != "MESH" or o.hide_render or o.name in assigned:
                continue
            assigned.add(o.name)
            is_leather = (
                cn == "12_BELTS"
                or "Leather" in o.name
                or "Straps" in o.name
                or "Grip" in o.name
                or o.name == "Weapon_Back_Scabbard"
                or o.name.startswith("Armor_Boot_")
            )
            if is_leather:
                leather_objs.append(o)
            else:
                armor_steel_objs.append(o)
    cloth_objs = _collect(["01_BODY", "04_HOOD", "08_CHAINMAIL", "09_TUNIC", "10_CAPE"])
    pedestal_objs = _collect(["15_PEDESTAL"])

    tmp_tex_dir = os.path.join(config.OUTPUT_DIR, "_bake_tmp")
    os.makedirs(tmp_tex_dir, exist_ok=True)
    groups = [
        ("Knight_Armor_Steel", 1024, armor_steel_objs, 0.45, 6),
        ("Knight_Cloth_Garments", 1024, cloth_objs, 0.55, 6),
        ("Knight_Leather_Gear", 512, leather_objs, 0.35, 4),
        ("Knight_Pedestal", 512, pedestal_objs, 0.65, 4),
    ]
    for atlas_name, base_res, objs, ao_dist, ao_s in groups:
        if not objs:
            continue
        res = max(256, int(round((base_res * bake_scale) / 64.0)) * 64)
        print(f"[ExportKnight] Baking atlas {atlas_name}: {len(objs)} objs @ {res}x{res}...", flush=True)
        pbr_bake.bake_pbr_atlas(
            atlas_name=atlas_name,
            objects=objs,
            resolution=res,
            samples_emit=1,
            samples_normal=1,
            samples_ao=ao_s,
            ao_distance=ao_dist,
            island_margin=0.005,
            texture_dir=os.path.join(tmp_tex_dir, atlas_name),
        )

    for sname in skip_bake:
        sobj = all_objs.get(sname)
        if sobj and sobj.type == "MESH":
            pbr_bake.apply_non_armature_modifiers([sobj])

    _simplify_unbaked_utility_mats()
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    bpy.ops.object.select_all(action="DESELECT")
    for col_name in export_cols:
        col = bpy.data.collections.get(col_name)
        if col:
            for obj in col.all_objects:
                if obj.type in ("MESH", "ARMATURE") and not obj.hide_render:
                    obj.select_set(True)

    try:
        os.makedirs(os.path.dirname(os.path.abspath(glb_path)), exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=glb_path,
            export_format="GLB",
            use_selection=True,
            export_apply=False,
            export_yup=True,
            export_materials="EXPORT",
            export_image_format="WEBP",
            export_image_quality=webp_quality,
            export_texcoords=True,
            export_normals=True,
            export_skins=True,
            export_animations=True,
            export_nla_strips=True,
            export_draco_mesh_compression_enable=True,
        )
    finally:
        shutil.rmtree(tmp_tex_dir, ignore_errors=True)


def main():
    t0 = time.time()
    args = _parse_cli_args()
    preset = config.QUALITY_PRESETS[args.quality]
    detail = args.detail or preset["default_detail"]

    config.ensure_directories()
    scene = config.clear_scene()
    config.setup_collections()

    print(f"[ForgottenKnight] Building quality={args.quality} detail={detail}")
    materials.create_all_materials()
    character_body.build_character_body(detail=detail)
    helmet_generator.build_helmet(detail=detail)
    armor_generator.build_armor(detail=detail)
    chainmail_generator.build_chainmail(detail=detail)
    cloth_generator.build_cloth(detail=detail)
    equipment_generator.build_equipment(detail=detail)
    sword_generator.build_weapons(detail=detail)
    lantern_generator.build_lantern(detail=detail)
    pedestal.build_pedestal(detail=detail)

    rig_info = rigging.build_rigging()
    lighting.setup_studio_lighting(scene)
    cameras.setup_cameras()

    # Validate constructed scene
    val = validate_character(rig_info)
    print("[Validation]", json.dumps(val, indent=2))

    # Save procedural V2 .blend BEFORE destructive glTF baking
    try:
        bpy.ops.file.pack_all()
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(args.output_blend)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.output_blend)
    print(f"[Saved BLEND] {args.output_blend}")

    # Render requested views from full-resolution procedural scene BEFORE baking export copy
    rendered = {}
    if not args.skip_render:
        rendered = render.run_renders(
            scene,
            preset_name=args.quality,
            view=args.view,
            samples_override=args.samples,
            include_closeups=args.closeups,
            output_dir=args.render_dir,
        )
        for k, p in rendered.items():
            print(f"[Rendered {k}] {p}")

    # Bake PBR atlases (keeping Armature + NLA animations intact) & export compressed WebP GLB
    exported_glb_path = None
    if not args.skip_glb:
        export_glb(
            args.output_glb,
            max_subdiv=args.max_subdiv,
            bake_scale=args.bake_scale,
            webp_quality=args.webp_quality,
        )
        exported_glb_path = args.output_glb
        glb_mb = os.path.getsize(args.output_glb) / (1024 * 1024)
        print(f"[Exported GLB] {args.output_glb} ({glb_mb:.2f} MB)")
        if args.sync_web:
            web_glb = os.path.join(_ROOT_DIR, "public", "models", "forgotten_knight.glb")
            os.makedirs(os.path.dirname(web_glb), exist_ok=True)
            shutil.copy2(args.output_glb, web_glb)
            print(f"[Synced Web GLB] {web_glb}")

    summary = {
        "quality": args.quality,
        "detail": detail,
        "elapsed_sec": round(time.time() - t0, 2),
        "validation": val,
        "blend": args.output_blend,
        "glb": exported_glb_path if (exported_glb_path and os.path.exists(exported_glb_path)) else None,
        "renders": rendered,
    }
    stats_path = os.path.join(config.OUTPUT_DIR, "build_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[Done in {summary['elapsed_sec']}s]")


if __name__ == "__main__":
    main()
