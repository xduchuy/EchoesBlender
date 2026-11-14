"""Realistic chainmail generator for THE FORGOTTEN KNIGHT (Section 07 & 29).
Combines textured metallic mail under-layers with lightweight staggered 4-in-1
3D chainmail ring geometry in all high-visibility openings: upper arms, elbows,
neck collar, waist/thigh hauberk V-skirt, and rear hip gaps in 08_CHAINMAIL.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix
import config


def _create_single_ring_verts(bm, center: Vector, normal: Vector,
                              major_r: float = 0.0068, minor_r: float = 0.0016,
                              maj_segs: int = 8, min_segs: int = 4):
    """Add a low-poly beveled torus mail ring inside a single shared BMesh."""
    n = normal.normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(n.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    u = n.cross(ref).normalized()
    v = n.cross(u).normalized()

    rings = []
    for i in range(maj_segs):
        theta = 2.0 * math.pi * i / maj_segs
        rad_dir = u * math.cos(theta) + v * math.sin(theta)
        ring_center = center + rad_dir * major_r
        r_verts = []
        for j in range(min_segs):
            phi = 2.0 * math.pi * j / min_segs
            pt = ring_center + rad_dir * (math.cos(phi) * minor_r) + n * (math.sin(phi) * minor_r)
            r_verts.append(bm.verts.new(pt))
        rings.append(r_verts)

    for i in range(maj_segs):
        inext = (i + 1) % maj_segs
        for j in range(min_segs):
            jnext = (j + 1) % min_segs
            bm.faces.new((rings[i][j], rings[inext][j], rings[inext][jnext], rings[i][jnext]))


def _populate_ring_grid(bm, sampler_fn, rows: int, cols: int, ring_r: float = 0.0068):
    """Populate a parametric surface function (u in 0..1, v in 0..1) with staggered 4-in-1 rings."""
    rng = config.seeded_rng(701)
    for ir in range(rows):
        u = ir / max(1, rows - 1)
        row_shift = 0.5 / max(1, cols) if (ir % 2 == 1) else 0.0
        for ic in range(cols):
            v = (ic / max(1, cols - 1)) + row_shift
            if v > 1.0:
                v -= 1.0
            pos, normal = sampler_fn(u, v)
            tilt = (1 if ir % 2 == 0 else -1) * 0.35 + (rng.random() - 0.5) * 0.14
            tang = Vector((-normal.y, normal.x, 0.0))
            if tang.length < 1e-4:
                tang = Vector((1.0, 0.0, 0.0))
            tang.normalize()
            tilted_n = (normal + Vector((0.0, 0.0, tilt)) + tang * 0.12).normalized()
            _create_single_ring_verts(bm, pos, tilted_n, major_r=ring_r, minor_r=ring_r * 0.25)


def _build_arm_chainmail_sleeves(detail: str) -> list:
    """Exposed chainmail along upper arms, underarms, and elbow bends."""
    objs = []
    j = config.JOINTS
    rows_arm = {"LOW": 10, "MEDIUM": 16, "HIGH": 22}[detail]
    cols_arm = {"LOW": 10, "MEDIUM": 15, "HIGH": 20}[detail]

    for side in ("R", "L"):
        sh = j[f"shoulder_{side}"]
        el = j[f"elbow_{side}"]
        wr = j[f"wrist_{side}"]
        in_x = -0.035 if side == "L" else 0.035

        # Base dark mail sleeve backing mesh extending cleanly into shoulder socket so underbody never shows
        bm_base = bmesh.new()
        pts_back = [
            (sh + Vector((in_x, 0.0, 0.008)), 0.060),
            (sh.lerp(el, 0.10), 0.062),
            (sh.lerp(el, 0.55), 0.056),
            (el, 0.050),
            (el.lerp(wr, 0.28), 0.047),
        ]
        config.tube_along_points(bm_base, [p for p, _ in pts_back], [r for _, r in pts_back], radial_segs=14)
        base_obj = config.finalize_bmesh(bm_base, f"Chainmail_SleeveBase_{side}", "08_CHAINMAIL", mat_name="MAT_Chainmail", smooth=True)
        objs.append(base_obj)

        # Real 3D staggered chainmail rings covering upper bicep through elbow crook
        bm_rings = bmesh.new()
        def _sample_arm(u, v, p_start=sh.lerp(el, 0.08), p_end=el.lerp(wr, 0.18)):
            c = p_start.lerp(p_end, u)
            rad = 0.061 - u * 0.012
            dir_v = (p_end - p_start).normalized()
            ref = Vector((0.0, -1.0, 0.0))
            ax = ref.cross(dir_v).normalized()
            ay = dir_v.cross(ax).normalized()
            ang = v * math.pi * 2.0
            n = (ax * math.cos(ang) + ay * math.sin(ang)).normalized()
            return c + n * rad, n

        _populate_ring_grid(bm_rings, _sample_arm, rows=rows_arm, cols=cols_arm, ring_r=0.0066)
        rings_obj = config.finalize_bmesh(bm_rings, f"Chainmail_Rings_Arm_{side}", "08_CHAINMAIL", mat_name="MAT_Chainmail", smooth=True)
        objs.append(rings_obj)

    return objs


def _build_hauberk_skirt(detail: str) -> list:
    """Build waist-to-upper-thigh chainmail hauberk skirt prominently visible in front tabard V-gap
    and rear hip openings."""
    objs = []
    # Base flared skirt backing cylinder (Z=0.96 -> 0.54)
    bm_base = bmesh.new()
    slices = [
        (0.97, 0.165, 0.118),
        (0.84, 0.184, 0.132),
        (0.70, 0.202, 0.145),
        (0.56, 0.214, 0.155),
    ]
    rings_b = []
    for z, rx, ry in slices:
        rings_b.append([Vector((math.cos(2 * math.pi * i / 18) * rx, math.sin(2 * math.pi * i / 18) * ry - 0.008, z)) for i in range(18)])
    config.loft_rings(bm_base, rings_b, close_cap_start=False, close_cap_end=False)
    objs.append(config.finalize_bmesh(bm_base, "Chainmail_SkirtBase", "08_CHAINMAIL", mat_name="MAT_Chainmail", smooth=True))

    # Real 3D rings in front central V-gap (between tabard panels) & rear lower peep window
    rows_s = {"LOW": 10, "MEDIUM": 16, "HIGH": 22}[detail]
    cols_s = {"LOW": 14, "MEDIUM": 22, "HIGH": 30}[detail]

    bm_rings = bmesh.new()
    def _sample_skirt_front(u, v):
        z = 0.94 - u * 0.36  # 0.94 down to 0.58
        rx = 0.172 + u * 0.045
        ry = 0.125 + u * 0.032
        # Span around front center (-pi/2 +/- 0.85 rad) AND rear center (+pi/2 +/- 0.70 rad)
        if v < 0.55:
            tv = v / 0.55 * 2.0 - 1.0
            ang = -math.pi * 0.5 + tv * 0.82
        else:
            tv = (v - 0.55) / 0.45 * 2.0 - 1.0
            ang = math.pi * 0.5 + tv * 0.68
        n = Vector((math.cos(ang), math.sin(ang), -0.10)).normalized()
        pt = Vector((math.cos(ang) * rx, math.sin(ang) * ry - 0.008, z))
        return pt, n

    _populate_ring_grid(bm_rings, _sample_skirt_front, rows=rows_s, cols=cols_s, ring_r=0.0074)
    objs.append(config.finalize_bmesh(bm_rings, "Chainmail_Rings_Hauberk", "08_CHAINMAIL", mat_name="MAT_Chainmail", smooth=True))

    # Neck gorget mail edge peeking just between helmet chin and green scarf
    bm_neck = bmesh.new()
    def _sample_neck(u, v):
        z = 1.50 + u * 0.08
        ang = v * math.pi * 2.0
        rx, ry = 0.072, 0.078
        pt = Vector((math.cos(ang) * rx, math.sin(ang) * ry - 0.020, z))
        n = Vector((math.cos(ang), math.sin(ang), 0.0)).normalized()
        return pt, n
    _populate_ring_grid(bm_neck, _sample_neck, rows=4 if detail == "LOW" else 6, cols=16 if detail == "LOW" else 22, ring_r=0.0062)
    objs.append(config.finalize_bmesh(bm_neck, "Chainmail_Rings_Neck", "08_CHAINMAIL", mat_name="MAT_Chainmail", smooth=True))

    return objs


def build_chainmail(detail: str = "MEDIUM") -> dict:
    """Create all chainmail mesh layers and instanced 3D ring strips in 08_CHAINMAIL."""
    arms = _build_arm_chainmail_sleeves(detail)
    skirt = _build_hauberk_skirt(detail)
    return {"arms": arms, "skirt": skirt}
