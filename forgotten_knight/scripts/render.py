"""Cycles render pipeline & seamless 16:9 side-by-side character sheet compositor
for THE FORGOTTEN KNIGHT (Section 20 & 23).
Renders CAM_FRONT_3Q -> renders/front_view.png, CAM_REAR_3Q -> renders/back_view.png,
combines them cleanly into renders/character_sheet.png (Left=Front, Right=Rear),
and optionally produces preview.png and closeup shots.
"""

import os
import bpy
import numpy as np
import config


def configure_render_engine(scene, preset_name: str, samples_override: int | None = None):
    """Configure Blender Cycles, OpenImageDenoise, and AgX color management."""
    preset = config.QUALITY_PRESETS[preset_name]
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples_override if samples_override is not None else preset["samples"]
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.025 if preset_name == "preview" else 0.015
    scene.cycles.use_denoising = preset["use_denoising"]
    if hasattr(scene.cycles, "denoiser"):
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 4
    scene.cycles.sample_clamp_indirect = 4.0

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"

    # AgX look with subtle cinematic dark-fantasy contrast
    vt = scene.view_settings
    for name in ("AgX", "Filmic", "Standard"):
        try:
            vt.view_transform = name
            break
        except Exception:
            pass
    for look_name in ("AgX - Medium High Contrast", "AgX - Medium Contrast", "Medium Contrast", "None"):
        try:
            vt.look = look_name
            break
        except Exception:
            pass
    vt.exposure = -0.10


def _render_camera_to(scene, cam_name: str, out_path: str, width: int, height: int):
    """Set active camera & resolution cleanly and render single frame."""
    cam = bpy.data.objects.get(cam_name)
    if cam is None:
        raise RuntimeError(f"Missing camera: {cam_name}")
    scene.camera = cam
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    return out_path


def _stitch_side_by_side(left_path: str, right_path: str, out_path: str,
                         width: int, height: int):
    """Combine front_view.png (Left) and back_view.png (Right) into a seamless
    16:9 character sheet with subtle studio center gradient feathering."""
    img_l = bpy.data.images.load(left_path)
    img_r = bpy.data.images.load(right_path)

    lw, lh = img_l.size
    rw, rh = img_r.size
    arr_l = np.array(img_l.pixels[:], dtype=np.float32).reshape((lh, lw, 4))
    arr_r = np.array(img_r.pixels[:], dtype=np.float32).reshape((rh, rw, 4))

    bpy.data.images.remove(img_l)
    bpy.data.images.remove(img_r)

    half_w = width // 2
    if lw != half_w or lh != height or rw != half_w or rh != height:
        # Clean nearest/linear slice fallback if custom size differs
        arr_l = arr_l[:height, :half_w, :]
        arr_r = arr_r[:height, :half_w, :]

    canvas = np.zeros((height, width, 4), dtype=np.float32)
    canvas[:, :half_w, :] = arr_l
    canvas[:, half_w:, :] = arr_r

    # Subtle 24-pixel horizontal mist blend along center join so background merges seamlessly
    feather = min(24, half_w // 6)
    if feather > 1:
        mid_strip_l = arr_l[:, half_w - feather:, :]
        mid_strip_r = arr_r[:, :feather, :]
        avg_edge = 0.5 * (mid_strip_l[:, ::-1, :] + mid_strip_r)
        # Keep foreground untouched if needed — center seam sits in empty studio mist
        for dx in range(feather):
            alpha = dx / (feather - 1)
            canvas[:, half_w - feather + dx, :] = (
                (1.0 - 0.5 * alpha) * arr_l[:, half_w - feather + dx, :]
                + (0.5 * alpha) * arr_r[:, dx, :]
            )
            canvas[:, half_w + dx, :] = (
                (0.5 * (1.0 - alpha)) * arr_l[:, half_w - 1 - dx, :]
                + (0.5 + 0.5 * alpha) * arr_r[:, dx, :]
            )

    out_name = os.path.basename(out_path)
    old = bpy.data.images.get(out_name)
    if old:
        bpy.data.images.remove(old)
    out_img = bpy.data.images.new(out_name, width=width, height=height, alpha=True)
    out_img.pixels.foreach_set(canvas.ravel())
    out_img.filepath_raw = out_path
    out_img.file_format = "PNG"
    out_img.save()
    bpy.data.images.remove(out_img)


def run_renders(scene, preset_name: str = "preview", view: str = "all",
                samples_override: int | None = None, include_closeups: bool = False,
                output_dir: str | None = None) -> dict:
    """Execute requested camera renders and assemble character_sheet.png."""
    preset = config.QUALITY_PRESETS[preset_name]
    configure_render_engine(scene, preset_name, samples_override=samples_override)

    vw, vh = preset["view_width"], preset["view_height"]
    sw, sh = preset["sheet_width"], preset["sheet_height"]

    rdir = output_dir or config.RENDERS_DIR
    os.makedirs(rdir, exist_ok=True)
    front_path = os.path.join(rdir, "front_view.png")
    back_path = os.path.join(rdir, "back_view.png")
    sheet_path = os.path.join(rdir, "character_sheet.png")
    preview_path = os.path.join(rdir, "preview.png")

    rendered = {}

    if view in ("front", "all", "sheet"):
        _render_camera_to(scene, "CAM_FRONT_3Q", front_path, vw, vh)
        rendered["front_view"] = front_path

    if view in ("back", "all", "sheet"):
        _render_camera_to(scene, "CAM_REAR_3Q", back_path, vw, vh)
        rendered["back_view"] = back_path

    if view in ("all", "sheet") and os.path.exists(front_path) and os.path.exists(back_path):
        _stitch_side_by_side(front_path, back_path, sheet_path, sw, sh)
        rendered["character_sheet"] = sheet_path

        # Also keep renders/preview.png populated cleanly from preview/sheet pass
        if preset_name == "preview" or not os.path.exists(preview_path):
            _stitch_side_by_side(front_path, back_path, preview_path, sw, sh)
            rendered["preview"] = preview_path

    if include_closeups:
        dw, dh = preset["detail_width"], preset["detail_height"]
        helm_path = os.path.join(rdir, "helmet_closeup.png")
        back_det_path = os.path.join(rdir, "equipment_closeup.png")
        _render_camera_to(scene, "CAM_FRONT_DETAIL", helm_path, dw, dh)
        _render_camera_to(scene, "CAM_BACK_DETAIL", back_det_path, dw, dh)
        rendered["helmet_closeup"] = helm_path
        rendered["equipment_closeup"] = back_det_path

    return rendered
