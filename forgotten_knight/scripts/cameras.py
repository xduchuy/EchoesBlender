"""Camera rig and viewport reference plane generator for THE FORGOTTEN KNIGHT (Section 21).
Creates CAM_FRONT_3Q, CAM_REAR_3Q, CAM_FRONT_DETAIL, and CAM_BACK_DETAIL in 17_CAMERAS
pointing to the single shared knight + pedestal asset with consistent vertical framing
and telephoto compression (75-80mm).
"""

import math
import os
import bpy
import bmesh
from mathutils import Vector
import config


def _create_target_empty(name: str, loc: tuple, col_name: str = "17_CAMERAS"):
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.15
    empty.location = Vector(loc)
    config.link_object(empty, col_name)
    return empty


def _create_camera(name: str, location: tuple, target_obj,
                   lens: float = 75.0, dof_fstop: float = 4.5,
                   focus_target=None) -> bpy.types.Object:
    """Create a perspective telephoto camera tracked neatly to target_obj."""
    cdata = bpy.data.cameras.new(name=name)
    cdata.type = "PERSP"
    cdata.lens = lens
    cdata.sensor_fit = "VERTICAL"
    cdata.sensor_height = 24.0
    cdata.clip_start = 0.05
    cdata.clip_end = 100.0

    # Gentle studio DOF keeps character razor-sharp while blurring distant silhouettes
    cdata.dof.use_dof = True
    cdata.dof.focus_object = focus_target if focus_target is not None else target_obj
    cdata.dof.aperture_fstop = dof_fstop

    cobj = bpy.data.objects.new(name=name, object_data=cdata)
    cobj.location = Vector(location)
    config.link_object(cobj, "17_CAMERAS")

    track = cobj.constraints.new(type="TRACK_TO")
    track.target = target_obj
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    return cobj


def _build_reference_plane():
    """Place reference image plane inside hidden-by-default 00_REFERENCE collection for viewport checks."""
    if not os.path.exists(config.REFERENCE_IMAGE_PATH):
        return None
    img = bpy.data.images.load(config.REFERENCE_IMAGE_PATH, check_existing=True)
    bm = bmesh.new()
    # 16:9 board positioned neatly off-stage to the far side for optional viewport reference
    w, h = 3.20, 1.79
    cx, cy, cz = -4.0, 2.5, 0.90
    v0 = bm.verts.new(Vector((cx - w * 0.5, cy, cz - h * 0.5)))
    v1 = bm.verts.new(Vector((cx + w * 0.5, cy, cz - h * 0.5)))
    v2 = bm.verts.new(Vector((cx + w * 0.5, cy, cz + h * 0.5)))
    v3 = bm.verts.new(Vector((cx - w * 0.5, cy, cz + h * 0.5)))
    face = bm.faces.new((v0, v1, v2, v3))
    uv = bm.loops.layers.uv.verify()
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for loop, uv_co in zip(face.loops, uvs):
        loop[uv].uv = uv_co

    ref_obj = config.finalize_bmesh(bm, "Reference_Sheet_Board", "00_REFERENCE", smooth=False)
    mat = bpy.data.materials.new("MAT_Reference_Preview")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emi = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], emi.inputs["Color"])
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    ref_obj.data.materials.append(mat)
    # Hide from render outputs so it never intrudes on studio renders
    ref_obj.hide_render = True
    ref_obj.hide_viewport = True
    return ref_obj


def setup_cameras() -> dict:
    """Create Section 21 camera rig targeting the shared character center."""
    target_full = _create_target_empty("CamTarget_FullBody", (0.0, 0.0, 0.85))
    target_upper = _create_target_empty("CamTarget_UpperDetail", (0.0, 0.0, 1.36))
    focus_body = _create_target_empty("CamFocus_Knight", (0.0, -0.05, 1.05))

    # Front 3/4 view (~17 deg right of front -Y, slightly elevated looking over wet pedestal)
    az_f = math.radians(17.5)
    dist_full = 7.55
    cam_front = _create_camera(
        "CAM_FRONT_3Q",
        location=(dist_full * math.sin(az_f), -dist_full * math.cos(az_f), 1.38),
        target_obj=target_full,
        lens=75.0,
        dof_fstop=2.2,
        focus_target=focus_body,
    )

    # Rear 3/4 view (~24 deg left of rear +Y so left brass pauldron + back scabbard + held hilt all read!)
    az_r = math.radians(24.0)
    cam_rear = _create_camera(
        "CAM_REAR_3Q",
        location=(dist_full * math.sin(az_r), dist_full * math.cos(az_r), 1.40),
        target_obj=target_full,
        lens=75.0,
        dof_fstop=2.2,
        focus_target=focus_body,
    )

    # Upper close-up cameras (80mm portrait compression)
    dist_det = 3.15
    cam_front_det = _create_camera(
        "CAM_FRONT_DETAIL",
        location=(dist_det * math.sin(az_f), -dist_det * math.cos(az_f), 1.50),
        target_obj=target_upper,
        lens=80.0,
        dof_fstop=5.6,
        focus_target=target_upper,
    )
    cam_back_det = _create_camera(
        "CAM_BACK_DETAIL",
        location=(dist_det * math.sin(az_r), dist_det * math.cos(az_r), 1.52),
        target_obj=target_upper,
        lens=80.0,
        dof_fstop=5.6,
        focus_target=target_upper,
    )

    ref_board = _build_reference_plane()
    bpy.context.scene.camera = cam_front
    return {
        "CAM_FRONT_3Q": cam_front,
        "CAM_REAR_3Q": cam_rear,
        "CAM_FRONT_DETAIL": cam_front_det,
        "CAM_BACK_DETAIL": cam_back_det,
        "ref_board": ref_board,
    }
