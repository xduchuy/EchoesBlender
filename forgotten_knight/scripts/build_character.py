"""Main orchestrator & CLI entrypoint for THE FORGOTTEN KNIGHT reconstruction pipeline.
Usage:
  blender -b --python scripts/build_character.py -- --quality preview
  blender -b --python scripts/build_character.py -- --quality review
  blender -b --python scripts/build_character.py -- --quality final
"""

import argparse
import json
import os
import sys
import time

# Ensure sibling modules import cleanly when invoked via `blender -b --python`
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import bpy
from mathutils import Vector

import config
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


def export_glb(glb_path: str):
    """Export rigged character + pedestal meshes cleanly as glTF 2.0 binary (.glb)."""
    bpy.ops.object.select_all(action="DESELECT")
    export_cols = [
        "01_BODY", "02_ARMATURE", "03_HELMET", "04_HOOD", "05_TORSO_ARMOR",
        "06_ARM_ARMOR", "07_HANDS", "08_CHAINMAIL", "09_TUNIC", "10_CAPE",
        "11_LEG_ARMOR", "12_BELTS", "13_WEAPONS", "14_LANTERN", "15_PEDESTAL",
    ]
    for col_name in export_cols:
        col = bpy.data.collections.get(col_name)
        if col:
            for obj in col.objects:
                if obj.type in ("MESH", "ARMATURE") and not obj.hide_render:
                    obj.select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_draco_mesh_compression_enable=True,
    )


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

    # Save primary editable .blend file (pack external crest texture so scene is self-contained!)
    try:
        bpy.ops.file.pack_all()
    except Exception:
        pass
    bpy.ops.wm.save_as_mainfile(filepath=config.BLEND_OUTPUT_PATH)
    print(f"[Saved BLEND] {config.BLEND_OUTPUT_PATH}")

    # Export optional GLB
    if not args.skip_glb:
        try:
            export_glb(config.GLB_OUTPUT_PATH)
            glb_mb = os.path.getsize(config.GLB_OUTPUT_PATH) / (1024 * 1024)
            print(f"[Exported GLB] {config.GLB_OUTPUT_PATH} ({glb_mb:.2f} MB)")
        except Exception as exc:
            print(f"[GLB Export Warning] {exc}")

    # Render requested views
    rendered = {}
    if not args.skip_render:
        rendered = render.run_renders(
            scene,
            preset_name=args.quality,
            view=args.view,
            samples_override=args.samples,
            include_closeups=args.closeups,
        )
        for k, p in rendered.items():
            print(f"[Rendered {k}] {p}")

    summary = {
        "quality": args.quality,
        "detail": detail,
        "elapsed_sec": round(time.time() - t0, 2),
        "validation": val,
        "blend": config.BLEND_OUTPUT_PATH,
        "glb": config.GLB_OUTPUT_PATH if os.path.exists(config.GLB_OUTPUT_PATH) else None,
        "renders": rendered,
    }
    stats_path = os.path.join(config.OUTPUT_DIR, "build_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[Done in {summary['elapsed_sec']}s]")


if __name__ == "__main__":
    main()
