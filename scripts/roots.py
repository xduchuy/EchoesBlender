"""Ancient recursive gnarled tree root systems invading the sanctuary masonry."""

import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

import bpy
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree

from geometry_utils import assign_material, get_rng


def _build_arch_bvh_trees() -> List[Tuple[bpy.types.Object, BVHTree]]:
    """Collect world-space BVHTrees of major stone architecture/cliffs for root surface clinging."""
    trees: List[Tuple[bpy.types.Object, BVHTree]] = []
    deps = bpy.context.evaluated_depsgraph_get()
    for col_name in ("03_ARCHITECTURE", "02_CLIFFS"):
        col = bpy.data.collections.get(col_name)
        if not col:
            continue
        objs = list(col.all_objects)
        for obj in objs:
            if obj.type != "MESH" or obj.data is None or len(obj.data.polygons) == 0:
                continue
            eval_obj = obj.evaluated_get(deps)
            mesh = eval_obj.to_mesh()
            mesh.transform(obj.matrix_world)
            # Build BVHTree directly from transformed polygons/verts
            verts = [v.co.copy() for v in mesh.vertices]
            polys = [list(p.vertices) for p in mesh.polygons]
            eval_obj.to_mesh_clear()
            if verts and polys:
                trees.append((obj, BVHTree.FromPolygons(verts, polys)))
    return trees


def _snap_point_near_stone(
    pt: Vector,
    radius: float,
    bvh_trees: Sequence[Tuple[bpy.types.Object, BVHTree]],
    max_snap_dist: float = 1.65,
) -> Vector:
    """Pull a root point toward nearby stone masonry surface without collapsing bridging spans."""
    if not bvh_trees:
        return pt
    best_loc = None
    best_norm = None
    best_d = max_snap_dist
    for _, tree in bvh_trees:
        loc, norm, _, dist = tree.find_nearest(pt, best_d)
        if loc is not None and dist < best_d:
            best_d = dist
            best_loc = loc
            best_norm = norm
    if best_loc is None:
        return pt
    # Hug surface at 55% of local root radius outside stone face (slightly embedded for grounded look)
    offset_dir = best_norm.normalized() if best_norm and best_norm.length > 1e-4 else Vector((0, 0, 1))
    target = best_loc + offset_dir * (radius * 0.55)
    blend = max(0.0, min(1.0, 1.0 - (best_d / max_snap_dist) ** 1.3))
    return pt.lerp(target, blend * 0.85)


def _subdivide_and_distort_path(
    waypoints: Sequence[Tuple[float, float, float]],
    steps_per_seg: int,
    wobble_amp: float,
    wobble_freq: float,
    rng: random.Random,
    pin_endpoints: bool = True,
) -> List[Vector]:
    """Interpolate Catmull-Rom spline through waypoints with endpoint-tapered organic drift."""
    pts = [Vector(p) for p in waypoints]
    if len(pts) < 2:
        return pts

    seed_off = Vector((rng.uniform(-40, 40), rng.uniform(-40, 40), rng.uniform(-40, 40)))
    out: List[Vector] = []
    n = len(pts)
    total_steps = (n - 1) * steps_per_seg
    step_idx = 0
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(n - 1, i + 2)]
        for s in range(steps_per_seg):
            t = s / steps_per_seg
            t2 = t * t
            t3 = t2 * t
            pos = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
            )
            t_global = step_idx / max(1, total_steps)
            env = (math.sin(math.pi * t_global) ** 0.65) if pin_endpoints else 1.0
            nv = noise.noise_vector(pos * wobble_freq + seed_off)
            pos += nv * (wobble_amp * env)
            out.append(pos)
            step_idx += 1
    out.append(pts[-1].copy())
    return out


def _add_spline_to_curve(
    curve_data: bpy.types.Curve,
    points: List[Vector],
    r_start: float,
    r_end: float,
    rng: random.Random,
    knottiness: float = 0.20,
) -> None:
    """Append an organically tapered NURBS spline with buttress root flare and bark flutes."""
    if len(points) < 2:
        return
    spline = curve_data.splines.new("NURBS")
    spline.points.add(len(points) - 1)
    n = len(points)
    phase = rng.uniform(0.0, 6.28)
    for i, p in enumerate(points):
        t = i / max(1, n - 1)
        flare = 1.0 + 0.16 * math.exp(-t * 7.5)
        base_r = (r_start * ((1.0 - t) ** 1.15) + r_end * (t ** 1.15)) * flare
        knot = 1.0 + knottiness * math.sin(t * 14.0 + phase) * (1.0 - 0.5 * t)
        r = max(0.022, base_r * knot)
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
    wobble_amp: float = 0.45,
    bvh_trees: Sequence[Tuple[bpy.types.Object, BVHTree]] = (),
) -> bpy.types.Object:
    """Build a twisted root bundle that hugs masonry surfaces with secondary branches & tendrils."""
    curve_data = bpy.data.curves.new(name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 6
    curve_data.bevel_depth = 1.0
    curve_data.bevel_resolution = bevel_res
    curve_data.use_fill_caps = True

    # Main primary trunk snapped organically to masonry + intertwined companion strands
    raw_pts = _subdivide_and_distort_path(
        waypoints, steps_per_seg=4, wobble_amp=wobble_amp, wobble_freq=0.22, rng=rng, pin_endpoints=True
    )
    main_pts = [
        _snap_point_near_stone(
            p,
            r_start * (1.0 - (idx / max(1, len(raw_pts) - 1))) + r_end * (idx / max(1, len(raw_pts) - 1)),
            bvh_trees,
            max_snap_dist=1.75,
        )
        for idx, p in enumerate(raw_pts)
    ]
    _add_spline_to_curve(curve_data, main_pts, r_start, r_end, rng, knottiness=0.22)

    for tw in range(n_twins):
        twin_pts: List[Vector] = []
        ang0 = tw * math.pi + rng.uniform(0.0, 1.5)
        for i, mp in enumerate(main_pts):
            t = i / max(1, len(main_pts) - 1)
            twist_ang = ang0 + t * 9.5
            off_r = (r_start * (1.0 - t) + r_end * t) * 0.68
            offset = Vector((math.cos(twist_ang) * off_r, math.sin(twist_ang) * off_r, math.sin(twist_ang * 0.7) * off_r * 0.45))
            twin_pts.append(_snap_point_near_stone(mp + offset, off_r * 0.6, bvh_trees, max_snap_dist=1.1))
        _add_spline_to_curve(curve_data, twin_pts, r_start * 0.50, r_end * 0.58, rng, knottiness=0.24)

    # Recursive secondary & curved tertiary branches splitting off the main trunk
    for bi in range(n_branches):
        t_idx = int(rng.uniform(0.18, 0.85) * (len(main_pts) - 1))
        origin = main_pts[t_idx]
        t_frac = t_idx / max(1, len(main_pts) - 1)
        br_r0 = (r_start * (1.0 - t_frac) + r_end * t_frac) * rng.uniform(0.38, 0.62)

        tangent = (main_pts[min(len(main_pts) - 1, t_idx + 1)] - main_pts[max(0, t_idx - 1)]).normalized()
        splay = Vector((rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-0.85, 0.12))).normalized()
        dir_vec = (tangent * 0.62 + splay * 0.78).normalized()
        br_len = rng.uniform(4.2, 10.2)
        mid = origin + dir_vec * (br_len * 0.48) + Vector((rng.uniform(-1.1, 1.1), rng.uniform(-1.1, 1.1), -0.9))
        tip = origin + dir_vec * br_len + Vector((rng.uniform(-1.4, 1.4), rng.uniform(-1.4, 1.4), -2.5))
        if tip.z < -0.9:
            tip.z = rng.uniform(-0.8, -0.2)
        mid = _snap_point_near_stone(mid, br_r0 * 0.5, bvh_trees, max_snap_dist=1.4)

        br_pts = _subdivide_and_distort_path([tuple(origin), tuple(mid), tuple(tip)], steps_per_seg=4, wobble_amp=0.38, wobble_freq=0.36, rng=rng, pin_endpoints=False)
        _add_spline_to_curve(curve_data, br_pts, br_r0, 0.035, rng, knottiness=0.18)

        # Curved multi-segment tertiary sub-twig off secondary branch (no stiff 2-point sticks!)
        if len(br_pts) >= 5 and rng.random() < 0.78:
            sub_orig = br_pts[len(br_pts) // 2]
            sub_mid = sub_orig + Vector((rng.uniform(-1.1, 1.1), rng.uniform(-1.1, 1.1), rng.uniform(-1.6, -0.3)))
            sub_tip = sub_mid + Vector((rng.uniform(-1.4, 1.4), rng.uniform(-1.4, 1.4), rng.uniform(-2.0, -0.6)))
            if sub_tip.z < -0.7:
                sub_tip.z = rng.uniform(-0.7, 0.0)
            sub_pts = _subdivide_and_distort_path([tuple(sub_orig), tuple(sub_mid), tuple(sub_tip)], steps_per_seg=3, wobble_amp=0.22, wobble_freq=0.55, rng=rng, pin_endpoints=False)
            _add_spline_to_curve(curve_data, sub_pts, br_r0 * 0.50, 0.022, rng, knottiness=0.16)

    # Hanging fine root tendrils draping inside arches & down masonry walls
    for ti in range(n_tendrils):
        t_idx = int(rng.uniform(0.15, 0.78) * (len(main_pts) - 1))
        orig = main_pts[t_idx]
        drop_h = rng.uniform(3.5, 9.2)
        mid = orig + Vector((rng.uniform(-0.75, 0.75), rng.uniform(-0.75, 0.75), -drop_h * 0.52))
        tip = orig + Vector((rng.uniform(-0.95, 0.95), rng.uniform(-0.95, 0.95), -drop_h))
        if tip.z < -0.6:
            tip.z = rng.uniform(-0.6, 0.5)
        tend_pts = _subdivide_and_distort_path([tuple(orig), tuple(mid), tuple(tip)], steps_per_seg=3, wobble_amp=0.20, wobble_freq=0.62, rng=rng, pin_endpoints=False)
        _add_spline_to_curve(curve_data, tend_pts, rng.uniform(0.08, 0.14), 0.018, rng, knottiness=0.14)

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
    bvh_trees = _build_arch_bvh_trees()
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
            r_start=0.78,
            r_end=0.14,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=3,
            n_branches=9,
            n_tendrils=8,
            bvh_trees=bvh_trees,
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
            r_start=0.50,
            r_end=0.10,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=2,
            n_branches=7,
            n_tendrils=9,
            bvh_trees=bvh_trees,
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
            r_start=0.46,
            r_end=0.08,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=3,
            n_branches=8,
            n_tendrils=8,
            bvh_trees=bvh_trees,
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
            r_start=0.42,
            r_end=0.08,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=2,
            n_branches=6,
            n_tendrils=6,
            bvh_trees=bvh_trees,
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
            r_start=0.84,
            r_end=0.16,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=3,
            n_branches=10,
            n_tendrils=9,
            wobble_amp=0.52,
            bvh_trees=bvh_trees,
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
            r_start=0.52,
            r_end=0.11,
            col=col,
            mat=mat,
            rng=rng,
            bevel_res=bevel_res,
            n_twins=2,
            n_branches=7,
            n_tendrils=6,
            bvh_trees=bvh_trees,
        )
    )

    return objs
