"""Master scene generator and CLI runner for The Drowned Sanctuary."""

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

# Ensure scripts/ directory is importable regardless of current working directory
SCRIPTS_DIR = str(Path(__file__).resolve().parent)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import bpy

from atmosphere import build_atmosphere
from cameras import (
    setup_cameras,
    setup_cinematic_animation,
    setup_compositor_and_color_management,
)
from config import GEOMETRY_OVERRIDES, LAYOUT, QUALITY_PRESETS
from geometry_utils import create_control_empty, reset_scene, setup_collections
from gothic_architecture import build_all_architecture
from lighting import setup_lighting
from materials import create_all_materials
from rootbound_saint import build_rootbound_saint, validate_rootbound_saint
from roots import build_all_roots
from statue import build_central_statue
from terrain import (
    build_courtyard_and_causeway,
    build_flooded_rubble_and_reeds,
    build_terrain_and_cliffs,
)
from water import build_water


def _parse_args() -> argparse.Namespace:
    """Parse arguments passed after `--` to Blender."""
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Build and render The Drowned Sanctuary in Blender.")
    parser.add_argument(
        "--quality",
        choices=["preview", "review", "final"],
        default="preview",
        help="Render and build quality preset.",
    )
    parser.add_argument(
        "--preset",
        choices=["fast", "balanced", "high"],
        default=None,
        help="Optional geometry detail preset override.",
    )
    parser.add_argument(
        "--camera",
        default="CAM_HERO_REFERENCE",
        help="Active camera name to render.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=None,
        help="Optional Cycles sample count override.",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Build and save the .blend file without rendering.",
    )
    parser.add_argument(
        "--animate",
        action="store_true",
        help="Add 8-second smooth camera push animation and render animation frames.",
    )
    parser.add_argument(
        "--output-blend",
        default=os.path.join(PROJECT_ROOT, "output", "drowned_sanctuary.blend"),
        help="Destination .blend path.",
    )
    parser.add_argument(
        "--output-render",
        default=None,
        help="Destination PNG render path.",
    )
    return parser.parse_args(argv)


def _configure_cycles_device(scene: bpy.types.Scene) -> str:
    """Attempt GPU rendering if available in Cycles, otherwise fall back cleanly to CPU."""
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons.get("cycles")
    if prefs is None:
        scene.cycles.device = "CPU"
        return "CPU (cycles addon prefs unavailable)"

    cprefs = prefs.preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            cprefs.compute_device_type = backend
            cprefs.refresh_devices()
            gpu_devices = [d for d in cprefs.devices if d.type != "CPU"]
            if gpu_devices:
                for d in cprefs.devices:
                    d.use = (d.type != "CPU")
                scene.cycles.device = "GPU"
                return f"GPU ({backend}: {gpu_devices[0].name})"
        except Exception:
            continue

    cprefs.compute_device_type = "NONE"
    cprefs.refresh_devices()
    for d in cprefs.devices:
        d.use = (d.type == "CPU")
    scene.cycles.device = "CPU"
    cpu_name = cprefs.devices[0].name if cprefs.devices else "CPU"
    return f"CPU ({cpu_name})"


def _configure_render_settings(scene: bpy.types.Scene, qcfg: dict, samples_override: int | None) -> str:
    """Apply Cycles quality, denoising, sampling, and volume settings."""
    device_label = _configure_cycles_device(scene)

    scene.render.resolution_x = qcfg["res_x"]
    scene.render.resolution_y = qcfg["res_y"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"

    cyc = scene.cycles
    cyc.samples = samples_override if samples_override is not None else qcfg["samples"]
    cyc.use_adaptive_sampling = True
    cyc.adaptive_threshold = qcfg["adaptive_threshold"]

    cyc.use_denoising = bool(qcfg["use_denoising"])
    if hasattr(cyc, "denoiser"):
        cyc.denoiser = "OPENIMAGEDENOISE"
    if hasattr(cyc, "denoising_input_passes"):
        cyc.denoising_input_passes = "RGB_ALBEDO_NORMAL"

    cyc.max_bounces = qcfg["max_bounces"]
    cyc.diffuse_bounces = qcfg["diffuse_bounces"]
    cyc.glossy_bounces = qcfg["glossy_bounces"]
    cyc.transmission_bounces = qcfg["transmission_bounces"]
    cyc.volume_bounces = qcfg["volume_bounces"]
    cyc.transparent_max_bounces = 8

    cyc.volume_step_rate = qcfg["volume_step_rate"]
    cyc.volume_max_steps = qcfg["volume_max_steps"]
    cyc.sample_clamp_direct = 10.0
    cyc.sample_clamp_indirect = 4.0

    return device_label


def build_and_render() -> int:
    """Execute complete scene build, save .blend, and render output image."""
    args = _parse_args()
    qcfg = dict(QUALITY_PRESETS[args.quality])
    geom_preset = args.preset if args.preset else qcfg["geometry_preset"]
    if args.preset:
        qcfg.update(GEOMETRY_OVERRIDES[args.preset])

    blend_path = os.path.abspath(args.output_blend)
    render_path = os.path.abspath(
        args.output_render
        if args.output_render
        else os.path.join(PROJECT_ROOT, "renders", qcfg["output_filename"])
    )
    os.makedirs(os.path.dirname(blend_path), exist_ok=True)
    os.makedirs(os.path.dirname(render_path), exist_ok=True)

    t0 = time.perf_counter()
    print(f"[DrownedSanctuary] Building scene (quality={args.quality}, geom={geom_preset})...")

    scene = reset_scene()
    cols = setup_collections()
    create_control_empty(cols)

    print("[DrownedSanctuary] 1/9 Creating procedural PBR materials...")
    mats = create_all_materials()

    print("[DrownedSanctuary] 2/9 Building terrain & stratified cliffs...")
    build_terrain_and_cliffs(
        cols,
        mats,
        terrain_subdiv=qcfg["terrain_subdiv"],
        cliff_subdiv=qcfg["cliff_subdiv"],
    )

    print("[DrownedSanctuary] 3/9 Building Gothic sanctuary architecture...")
    build_all_architecture(cols, mats, preset=geom_preset)

    monument_mode = LAYOUT.get("monument_mode", "ROOTBOUND_SAINT")
    if monument_mode == "ROOTBOUND_SAINT":
        print("[DrownedSanctuary] 4/9 Building The Rootbound Saint monument...")
        build_rootbound_saint(cols, mats, subsurf_level=qcfg["subsurf_level"])
        val_saint = validate_rootbound_saint()
        print(f"[DrownedSanctuary] Rootbound Saint validation: {val_saint}")
        if not val_saint.get("passed"):
            raise RuntimeError(f"Rootbound Saint validation failed: {val_saint}")
    else:
        print("[DrownedSanctuary] 4/9 Sculpting central legacy monumental statue...")
        build_central_statue(cols, mats, subsurf_level=qcfg["subsurf_level"])

    print("[DrownedSanctuary] 5/9 Building flooded courtyard & diagonal causeway...")
    build_courtyard_and_causeway(cols, mats)

    print("[DrownedSanctuary] 6/9 Generating ancient recursive root systems...")
    build_all_roots(cols, mats, bevel_res=qcfg["root_bevel_res"])

    print("[DrownedSanctuary] 7/9 Scattering flooded ruins & reeds...")
    build_flooded_rubble_and_reeds(cols, mats, rubble_scale=qcfg["rubble_scale"])

    print("[DrownedSanctuary] 8/9 Building water, lighting, atmosphere & cameras...")
    build_water(cols, mats)
    setup_lighting(cols)
    build_atmosphere(cols, mats)
    cams = setup_cameras(cols, active_cam_name=args.camera)
    setup_compositor_and_color_management(scene)

    if args.animate:
        setup_cinematic_animation(scene, cams["CAM_HERO_REFERENCE"], duration_sec=8.0, fps=24)

    device_label = _configure_render_settings(scene, qcfg, args.samples)
    scene.render.filepath = render_path

    # Save editable .blend project before rendering so work is never lost
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    t_build = time.perf_counter() - t0
    print(f"[DrownedSanctuary] Saved .blend to {blend_path} ({t_build:.1f}s)")
    print(
        f"[DrownedSanctuary] Render config: {qcfg['res_x']}x{qcfg['res_y']}, "
        f"samples={scene.cycles.samples}, device={device_label}, camera={scene.camera.name}"
    )

    if args.skip_render:
        print("[DrownedSanctuary] Skipping render as requested (--skip-render).")
        return 0

    t_ren0 = time.perf_counter()
    if args.animate:
        anim_dir = os.path.join(PROJECT_ROOT, "renders", "animation")
        os.makedirs(anim_dir, exist_ok=True)
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.filepath = os.path.join(anim_dir, "drowned_sanctuary_flythrough.mp4")
        bpy.ops.render.render(animation=True)
        target_check = scene.render.filepath
    else:
        bpy.ops.render.render(write_still=True)
        target_check = render_path

    t_ren = time.perf_counter() - t_ren0
    if not os.path.exists(target_check) or os.path.getsize(target_check) == 0:
        print(f"[DrownedSanctuary] ERROR: Expected output missing or empty: {target_check}", file=sys.stderr)
        return 2

    print(f"[DrownedSanctuary] Render complete in {t_ren:.1f}s -> {target_check}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(build_and_render())
    except Exception as exc:
        print(f"[DrownedSanctuary] FATAL ERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
