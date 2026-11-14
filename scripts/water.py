"""Calm dark flooded basin water surface."""

import math
from typing import Dict, List

import bpy
import bmesh
from mathutils import Vector, noise

from config import LAYOUT
from geometry_utils import create_mesh_object


def build_water(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
) -> List[bpy.types.Object]:
    """Create the flooded basin water surface extending out to the distant horizon."""
    col = cols["06_WATER"]
    water_z = LAYOUT["water_level"]

    bm = bmesh.new()
    # High-detail inner basin (-105..+105 X, -115..+75 Y)
    nx, ny = 64, 64
    x0, x1 = -105.0, 105.0
    y0, y1 = -115.0, 75.0
    grid = []
    for iy in range(ny + 1):
        y = y0 + (y1 - y0) * (iy / ny)
        row = []
        for ix in range(nx + 1):
            x = x0 + (x1 - x0) * (ix / nx)
            # Very gentle calm undulation (only ~2cm)
            z = water_z + noise.noise(Vector((x * 0.08, y * 0.08, 0.0))) * 0.022
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)

    for iy in range(ny):
        for ix in range(nx):
            bm.faces.new([grid[iy][ix], grid[iy][ix + 1], grid[iy + 1][ix + 1], grid[iy + 1][ix]])

    # Distant calm sea/lake skirt extending from inner basin out to horizon (Y=+420, X=±400)
    outer_verts = [
        bm.verts.new((-420.0, -220.0, water_z)),
        bm.verts.new((420.0, -220.0, water_z)),
        bm.verts.new((420.0, 420.0, water_z)),
        bm.verts.new((-420.0, 420.0, water_z)),
    ]
    # Connect outer corners to inner perimeter corners cleanly without overlapping inner mesh
    in_bl = grid[0][0]
    in_br = grid[0][nx]
    in_tr = grid[ny][nx]
    in_tl = grid[ny][0]
    bm.faces.new([outer_verts[0], outer_verts[1], in_br, in_bl])
    bm.faces.new([outer_verts[1], outer_verts[2], in_tr, in_br])
    bm.faces.new([outer_verts[2], outer_verts[3], in_tl, in_tr])
    bm.faces.new([outer_verts[3], outer_verts[0], in_bl, in_tl])

    # Fill perimeter strips along inner boundary edges so skirt joins seamlessly
    for ix in range(nx):
        bm.faces.new([in_bl, in_br, grid[0][ix + 1], grid[0][ix]]) if False else None
    # Note: the 4 quads above use corner verts only; refine by linking to edge verts if needed,
    # or simply make outer horizon sheet 1cm lower (-0.015) around inner region!
    # Actually let's use clean rim strips so there's zero self-overlap:
    # Remove those 4 corner-shortcut faces and stitch properly along edges:
    for f in list(bm.faces):
        if any(v in outer_verts for v in f.verts):
            bm.faces.remove(f)

    # Bottom strip (iy = 0)
    for ix in range(nx):
        t0, t1 = ix / nx, (ix + 1) / nx
        ox0 = -420.0 + 840.0 * t0
        ox1 = -420.0 + 840.0 * t1
        v_o0 = bm.verts.new((ox0, -220.0, water_z))
        v_o1 = bm.verts.new((ox1, -220.0, water_z))
        bm.faces.new([v_o0, v_o1, grid[0][ix + 1], grid[0][ix]])
    # Top/horizon strip (iy = ny)
    for ix in range(nx):
        t0, t1 = ix / nx, (ix + 1) / nx
        ox0 = -420.0 + 840.0 * t0
        ox1 = -420.0 + 840.0 * t1
        v_o0 = bm.verts.new((ox0, 420.0, water_z))
        v_o1 = bm.verts.new((ox1, 420.0, water_z))
        bm.faces.new([grid[ny][ix], grid[ny][ix + 1], v_o1, v_o0])
    # Left strip (ix = 0)
    for iy in range(ny):
        t0, t1 = iy / ny, (iy + 1) / ny
        oy0 = -220.0 + 640.0 * t0
        oy1 = -220.0 + 640.0 * t1
        v_o0 = bm.verts.new((-420.0, oy0, water_z))
        v_o1 = bm.verts.new((-420.0, oy1, water_z))
        bm.faces.new([v_o0, grid[iy][0], grid[iy + 1][0], v_o1])
    # Right strip (ix = nx)
    for iy in range(ny):
        t0, t1 = iy / ny, (iy + 1) / ny
        oy0 = -220.0 + 640.0 * t0
        oy1 = -220.0 + 640.0 * t1
        v_o0 = bm.verts.new((420.0, oy0, water_z))
        v_o1 = bm.verts.new((420.0, oy1, water_z))
        bm.faces.new([grid[iy][nx], v_o0, v_o1, grid[iy + 1][nx]])

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    water_obj = create_mesh_object(
        "Water_Flooded_Basin",
        bm,
        col,
        mat=mats["MAT_Water_Dark"],
        smooth=True,
    )
    return [water_obj]
