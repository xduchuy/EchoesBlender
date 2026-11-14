"""Volumetric mist and distant atmospheric perspective volumes."""

from typing import Dict, List, Tuple

import bpy
import bmesh
from mathutils import Matrix

from config import LAYOUT
from geometry_utils import create_mesh_object
from materials import build_volume_mist_material


def _create_volume_box(
    name: str,
    center: Tuple[float, float, float],
    size: Tuple[float, float, float],
    col: bpy.types.Collection,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    """Create a wireframe-displayed volumetric domain box."""
    bm = bmesh.new()
    bmesh.ops.create_cube(
        bm,
        size=1.0,
        matrix=Matrix.Diagonal((size[0], size[1], size[2], 1.0)),
    )
    obj = create_mesh_object(name, bm, col, mat=mat, location=center, smooth=False)
    obj.display_type = "WIRE"
    # Prevent large fog domains from darkening direct infinite Sun rays before reaching the towers
    obj.visible_shadow = False
    return obj


def build_atmosphere(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
) -> List[bpy.types.Object]:
    """Create multi-layer volumetric mist over water channels, courtyard, and distant horizon."""
    col = cols["10_ATMOSPHERE"]
    acfg = LAYOUT["atmosphere"]
    objs: List[bpy.types.Object] = []

    # 1. Right channel low drifting mist (prominent bright mist pocket behind/right of Right Front tower)
    mist_right_mat = build_volume_mist_material(
        "MAT_Fog_RightChannel",
        base_density=acfg["mist_density"] * 1.45,
        color=(0.86, 0.88, 0.85, 1.0),
        noise_scale=0.048,
        anisotropy=0.58,
    )
    objs.append(
        _create_volume_box(
            "Atmosphere_Mist_RightChannel",
            center=(38.0, -18.0, 4.5),
            size=(58.0, 105.0, 11.0),
            col=col,
            mat=mist_right_mat,
        )
    )

    # 2. Central courtyard & statue base low water mist
    mist_court_mat = build_volume_mist_material(
        "MAT_Fog_Courtyard",
        base_density=acfg["courtyard_haze_density"] * 1.35,
        color=(0.82, 0.85, 0.84, 1.0),
        noise_scale=0.065,
        anisotropy=0.52,
    )
    objs.append(
        _create_volume_box(
            "Atmosphere_Mist_Courtyard",
            center=(0.0, 0.0, 2.2),
            size=(46.0, 56.0, 5.5),
            col=col,
            mat=mist_court_mat,
        )
    )

    # 3. Left rear channel mist (between Left Bastion and Left Midground Crags)
    objs.append(
        _create_volume_box(
            "Atmosphere_Mist_LeftChannel",
            center=(-46.0, 14.0, 3.2),
            size=(52.0, 72.0, 8.5),
            col=col,
            mat=mats["MAT_Fog_Volume"],
        )
    )

    # 4. Far-field aerial perspective haze fading distant mountains & right spire
    haze_dist_mat = build_volume_mist_material(
        "MAT_Fog_DistantHaze",
        base_density=acfg["distant_haze_density"],
        color=(0.86, 0.87, 0.82, 1.0),
        anisotropy=0.58,
        is_uniform=True,
    )
    objs.append(
        _create_volume_box(
            "Atmosphere_Haze_Distant",
            center=(0.0, 165.0, 38.0),
            size=(540.0, 265.0, 95.0),
            col=col,
            mat=haze_dist_mat,
        )
    )

    return objs
