"""Cameras, Blender 5.3 compositor post-processing, and optional camera push animation."""

import math
from typing import Dict, List, Optional

import bpy
from mathutils import Vector

from config import LAYOUT


def _create_tracked_camera(
    name: str,
    cfg: dict,
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Create a camera with a dedicated target empty and TRACK_TO constraint."""
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = cfg["lens"]
    cam_data.sensor_width = cfg["sensor_width"]
    cam_data.clip_start = 0.2
    cam_data.clip_end = 1000.0
    cam_data.dof.use_dof = bool(cfg.get("dof_enable", False))

    cam_obj = bpy.data.objects.new(name, cam_data)
    cam_obj.location = cfg["location"]
    col.objects.link(cam_obj)

    tgt = bpy.data.objects.new(f"{name}_Target", None)
    tgt.empty_display_type = "SPHERE"
    tgt.empty_display_size = 1.2
    tgt.location = cfg["target"]
    col.objects.link(tgt)

    trk = cam_obj.constraints.new("TRACK_TO")
    trk.target = tgt
    trk.track_axis = "TRACK_NEGATIVE_Z"
    trk.up_axis = "UP_Y"

    return cam_obj


def setup_cameras(
    cols: Dict[str, bpy.types.Collection],
    active_cam_name: str = "CAM_HERO_REFERENCE",
) -> Dict[str, bpy.types.Object]:
    """Create hero and secondary inspection cameras and assign the active scene camera."""
    col = cols["12_CAMERAS"]
    cams: Dict[str, bpy.types.Object] = {}
    for cname, ccfg in LAYOUT["cameras"].items():
        cams[cname] = _create_tracked_camera(cname, ccfg, col)

    hero = cams.get(active_cam_name) or cams["CAM_HERO_REFERENCE"]
    bpy.context.scene.camera = hero
    return cams


def setup_compositor_and_color_management(scene: bpy.types.Scene) -> None:
    """Configure AgX color management and restrained Blender 5.3 compositor post-processing."""
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -0.38
    scene.view_settings.gamma = 1.0

    # Blender 5.3 uses compositing_node_group with NodeGroupOutput
    ng = bpy.data.node_groups.get("Sanctuary_Compositor") or bpy.data.node_groups.new(
        "Sanctuary_Compositor", "CompositorNodeTree"
    )
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")

    rl = ng.nodes.new("CompositorNodeRLayers")
    rl.location = (-500, 0)

    # Restrained atmospheric fog glow on sunlit mist & sky highlights
    glare = ng.nodes.new("CompositorNodeGlare")
    glare.location = (-200, 0)
    glare.inputs["Type"].default_value = "Fog Glow"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = 1.25
    glare.inputs["Strength"].default_value = 0.14
    glare.inputs["Size"].default_value = 0.65

    # Very subtle tonal polish (cool shadow lift, gentle highlight contrast)
    cb = ng.nodes.new("CompositorNodeColorBalance")
    cb.location = (80, 0)
    cb.inputs[2].default_value = "Lift/Gamma/Gain"
    cb.inputs[4].default_value = (0.99, 0.998, 1.01, 1.0)
    cb.inputs[6].default_value = (1.0, 1.0, 0.995, 1.0)
    cb.inputs[8].default_value = (1.02, 1.01, 0.985, 1.0)

    out = ng.nodes.new("NodeGroupOutput")
    out.location = (380, 0)

    ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
    ng.links.new(glare.outputs["Image"], cb.inputs["Image"])
    ng.links.new(cb.outputs["Image"], out.inputs["Image"])

    scene.compositing_node_group = ng


def setup_cinematic_animation(
    scene: bpy.types.Scene,
    cam_obj: bpy.types.Object,
    duration_sec: float = 8.0,
    fps: int = 24,
) -> None:
    """Create a restrained, smooth 8-10s aerial push-in animation on CAM_HERO_REFERENCE."""
    scene.render.fps = fps
    scene.frame_start = 1
    end_frame = int(round(duration_sec * fps))
    scene.frame_end = end_frame

    base_loc = Vector(LAYOUT["cameras"]["CAM_HERO_REFERENCE"]["location"])
    start_loc = base_loc + Vector((4.5, -9.0, 2.2))
    end_loc = base_loc + Vector((-2.5, 4.5, -1.2))

    cam_obj.location = start_loc
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_obj.location = end_loc
    cam_obj.keyframe_insert(data_path="location", frame=end_frame)

    if cam_obj.animation_data and cam_obj.animation_data.action:
        act = cam_obj.animation_data.action
        fcurves = getattr(act, "fcurves", None)
        if fcurves is None and hasattr(act, "layers"):
            fcurves = []
            for lyr in act.layers:
                for strip in getattr(lyr, "strips", []):
                    for bag in getattr(strip, "channelbags", []):
                        fcurves.extend(bag.fcurves)
        if fcurves:
            for fcurve in fcurves:
                for kp in fcurve.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.handle_left_type = "AUTO_CLAMPED"
                    kp.handle_right_type = "AUTO_CLAMPED"
