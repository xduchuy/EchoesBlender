"""Ancient recursive gnarled tree root systems invading the sanctuary masonry."""

import math
import random
from typing import Dict, List, Sequence, Tuple

import bpy
from mathutils import Vector, noise

from geometry_utils import assign_material, get_rng


def _subdivide_and_distort_path(
    waypoints: Sequence[Tuple[float, float, float]],
    steps_per_seg: int,
    wobble_amp: float,
    wobble_freq: float,
    rng: random.Random,
) -> List[Vector]:
    """Interpolate Catmull-Rom-like smooth spline through waypoints and add organic 3D noise."""
    pts = [Vector(p) for p in waypoints]
    if len(pts) < 2:
        return pts

    seed_off = Vector((rng.uniform(-40, 40), rng.uniform(-40, 40), rng.uniform(-40, 40)))
    out: List[Vector] = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(n - 1, i + 2)]
        for s in range(steps_per_seg):
            t = s / steps_per_seg
            t2 = t * t
            t3 = t2 * t
            # Catmull-Rom interpolation
            pos = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            # Zero wobble right at pinned start/end points? Keep slight organic drift everywhere
            nv = noise.noise_vector(pos * wobble_freq + seed_off)
            # Taper wobble slightly near endpoints
            pos += nv * wobble_amp
            out.append(pos)
    out.append(pts[-1].copy())
    return out


def _add_spline_to_curve(
    curve_data: bpy.types.Curve,
    points: List[Vector],
    r_start: float,
    r_end: float,
    rng: random.Random,
    knottiness: float = 0.22,
) -> None:
    """Append a tapered NURBS/Poly spline with bumpy radius variation to a Curve data-block."""
    if len(points) < 2:
        return
    spline = curve_data.splines.new("NURBS")
    spline.points.add(len(points) - 1)
    n = len(points)
    phase = rng.uniform(0.0, 6.28)
    for i, p in enumerate(points):
        t = i / max(1, n - 1)
        # Taper smoothly + organic knots/bulges
        base_r = r_start * ((1.0 - t) ** 0.75) + r_end * (t ** 0.75)
        knot = 1.0 + knottiness * math.sin(t * 14.0 + phase) * (1.0 - 0.5 * t)
        r = max(0.025, base_r * knot)
        sp = spline.points[i]
        sp.co = (p.x, p.y, p.z, 1.0)
        sp.radius = r
    spline.use_endpoint_u = True
    spline.order_u = min(4, len(points))


def _create_root_bundle(
    name: str,
    waypoints: Sequence[Tuple[float, float, float]],
    r_start: float,
    r_end: float,
    col: bpy.types.Collection,
    mat: bpy.types.Material,
    rng: random.Random,
    bevel_res: int = 3,
    n_twins: int = 2,
    n_branches: int = 6,
    n_tendrils: int = 5,
    wobble_amp: float = 0.55,
) -> bpy.types.Object:
    """Build a complete twisted root trunk bundle with recursive secondary branches and hanging tendrils."""
    curve_data = bpy.data.curves.new(name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 6
    curve_data.bevel_depth = 1.0
    curve_data.bevel_resolution = bevel_res
    curve_data.use_fill_caps = True

    # Main primary trunk + intertwined companion strands
    main_pts = _subdivide_and_distort_path(waypoints, steps_per_seg=4, wobble_amp=wobble_amp, wobble_freq=0.22, rng=rng)
    _add_spline_to_curve(curve_data, main_pts, r_start, r_end, rng, knottiness=0.25)

    for tw in range(n_twins):
        twin_pts: List[Vector] = []
        ang0 = tw * math.pi + rng.uniform(0.0, 1.5)
        for i, mp in enumerate(main_pts):
            t = i / max(1, len(main_pts) - 1)
            twist_ang = ang0 + t * 9.5
            off_r = (r_start * (1.0 - t) + r_end * t) * 0.72
            offset = Vector((math.cos(twist_ang) * off_r, math.sin(twist_ang) * off_r, math.sin(twist_ang * 0.7) * off_r * 0.5))
            twin_pts.append(mp + offset)
        _add_spline_to_curve(curve_data, twin_pts, r_start * 0.52, r_end * 0.6, rng, knottiness=0.28)

    # Recursive secondary & tertiary branches splitting off the main trunk
    for bi in range(n_branches):
        t_idx = int(rng.uniform(0.18, 0.85) * (len(main_pts) - 1))
        origin = main_pts[t_idx]
        t_frac = t_idx / max(1, len(main_pts) - 1)
        br_r0 = (r_start * (1.0 - t_frac) + r_end * t_frac) * rng.uniform(0.40, 0.65)

        # Tangent direction + outward/downward splay
        tangent = (main_pts[min(len(main_pts) - 1, t_idx + 1)] - main_pts[max(0, t_idx - 1)]).normalized()
        splay = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-0.8, 0.15))).normalized()
        dir_vec = (tangent * 0.65 + splay * 0.75).normalized()
        br_len = rng.uniform(4.5, 11.0)
        mid = origin + dir_vec * (br_len * 0.48) + Vector((rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), -0.8))
        tip = origin + dir_vec * br_len + Vector((rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5), -2.4))
        # Clamp tip so roots plunge into water (-0.8m) rather than dangling absurdly deep
        if tip.z < -0.9:
            tip.z = rng.uniform(-0.8, -0.2)

        br_pts = _subdivide_and_distort_path([tuple(origin), tuple(mid), tuple(tip)], steps_per_seg=4, wobble_amp=0.45, wobble_freq=0.35, rng=rng)
        _add_spline_to_curve(curve_data, br_pts, br_r0, 0.04, rng, knottiness=0.2)

        # Tertiary sub-twig off secondary branch
        if len(br_pts) >= 5 and rng.random() < 0.75:
            sub_orig = br_pts[len(br_pts) // 2]
            sub_tip = sub_orig + Vector((rng.uniform(-2.2, 2.2), rng.uniform(-2.2, 2.2), rng.uniform(-3.5, -0.8)))
            sub_pts = _subdivide_and_distort_path([tuple(sub_orig), tuple(sub_tip)], steps_per_seg=3, wobble_amp=0.25, wobble_freq=0.5, rng=rng)
            _add_spline_to_curve(curve_data, sub_pts, br_r0 * 0.55, 0.025, rng)

    # Hanging fine root tendrils draping inside arches & down masonry walls
    for ti in range(n_tendrils):
        t_idx = int(rng.uniform(0.15, 0.78) * (len(main_pts) - 1))
        orig = main_pts[t_idx]
        drop_h = rng.uniform(3.5, 9.5)
        mid = orig + Vector((rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), -drop_h * 0.5))
        tip = orig + Vector((rng.uniform(-1.1, 1.1), rng.uniform(-1.1, 1.1), -drop_h))
        if tip.z < -0.6:
            tip.z = rng.uniform(-0.6, 0.5)
        tend_pts = _subdivide_and_distort_path([tuple(orig), tuple(mid), tuple(tip)], steps_per_seg=3, wobble_amp=0.22, wobble_freq=0.6, rng=rng)
        _add_spline_to_curve(curve_data, tend_pts, rng.uniform(0.09, 0.16), 0.02, rng)

    obj = bpy.data.objects.new(name, curve_data)
    col.objects.link(obj)
    assign_material(obj, mat)
    return obj


def build_all_roots(
    cols: Dict[str, bpy.types.Collection],
    mats: Dict[str, bpy.types.Material],
    bevel_res: int = 3,
) -> List[bpy.types.Object]:
    """Build all hero ancient root systems wrapping the sanctuary towers and arcade."""
    rng = get_rng("ancient_roots")
    col = cols["07_ROOTS"]
    mat = mats["MAT_Bark_Ancient"]
    objs: List[bpy.types.Object] = []

    # 1. Left Front Tower: gnarled root bundle cascading down front-right corner & across open arch
    objs.append(
        _create_root_bundle(
            "Roots_LeftFront_Main",
            waypoints=[
                (-17.8, -1.5, 25.5),
                (-16.0, -4.5, 19.0),
                (-15.5, -6.2, 12.5),
                (-16.2, -7.0, 5.5),
                (-17.0, -7.8, -0.7),
            ],
            r_start=0.88,
            r_end=0.16,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=2,
            n_branches=8,
            n_tendrils=7,
        )
    )
    # Branch draping over the Left Courtyard Flying Arch
    objs.append(
        _create_root_bundle(
            "Roots_LeftFront_ArchDrape",
            waypoints=[
                (-16.5, -1.0, 21.0),
                (-13.5, 0.6, 17.5),
                (-10.2, 1.2, 14.0),
                (-9.5, 0.5, 8.0),
                (-9.8, -0.5, 1.0),
            ],
            r_start=0.55,
            r_end=0.10,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=1,
            n_branches=6,
            n_tendrils=8,
        )
    )

    # 2. Left Rear / Arcade Shoulder Roots: crawling across upper left arcade wall
    objs.append(
        _create_root_bundle(
            "Roots_LeftArcade_Shoulder",
            waypoints=[
                (-15.5, 18.5, 25.5),
                (-14.0, 15.0, 20.5),
                (-11.2, 17.2, 17.5),
                (-7.5, 21.0, 15.0),
                (-6.2, 19.5, 8.5),
                (-6.5, 18.0, 0.2),
            ],
            r_start=0.70,
            r_end=0.12,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=2,
            n_branches=7,
            n_tendrils=7,
        )
    )

    # 3. Right Rear / Arcade Shoulder Roots
    objs.append(
        _create_root_bundle(
            "Roots_RightArcade_Shoulder",
            waypoints=[
                (13.0, 19.5, 24.5),
                (11.2, 17.0, 19.5),
                (9.8, 18.0, 14.0),
                (11.0, 15.0, 7.5),
                (11.8, 12.5, -0.5),
            ],
            r_start=0.62,
            r_end=0.11,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=1,
            n_branches=5,
            n_tendrils=5,
        )
    )

    # 4. Right Front Tower Massive Root Cascade (draping over shadowed courtyard wall & stair!)
    objs.append(
        _create_root_bundle(
            "Roots_RightFront_MainCascade",
            waypoints=[
                (22.2, -7.5, 25.0),
                (20.0, -10.0, 19.0),
                (18.5, -12.8, 12.8),
                (17.2, -14.8, 6.2),
                (15.2, -14.2, 1.5),
                (13.5, -13.5, -0.8),
            ],
            r_start=0.98,
            r_end=0.18,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=2,
            n_branches=9,
            n_tendrils=8,
            wobble_amp=0.68,
        )
    )
    objs.append(
        _create_root_bundle(
            "Roots_RightFront_LowerBranch",
            waypoints=[
                (19.8, -14.8, 16.5),
                (18.6, -19.0, 11.2),
                (18.8, -22.2, 5.4),
                (19.2, -23.8, -0.8),
            ],
            r_start=0.58,
            r_end=0.12,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=1,
            n_branches=6,
            n_tendrils=5,
        )
    )

    return objs
