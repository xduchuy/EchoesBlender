"""Anatomical underlying character body generator for THE FORGOTTEN KNIGHT.
Builds a ~1.85m (7.5-8 head) sculpted humanoid under-mesh using contoured
anatomical cross-sections matching JOINTS so armor, mail, belts, and cloth
follow realistic human proportions without cylindrical artifacts.
"""

import math
import bpy
import bmesh
from mathutils import Vector, Matrix
import config


def _sculpted_ring(center: Vector, rx: float, ry: float, segs: int,
                   pinch_back: float = 0.0, chest_bulge: float = 0.0,
                   spine_groove: float = 0.0):
    """Create an anatomically contoured cross-section ring (facing -Y forward)."""
    pts = []
    for i in range(segs):
        a = 2.0 * math.pi * i / segs
        ca = math.cos(a)
        sa = math.sin(a)
        x = ca * rx
        y = sa * ry
        # Front torso (-Y => sa < 0): pectoral / rib contour
        if sa < 0.0 and chest_bulge != 0.0:
            y -= chest_bulge * ((-sa) ** 1.4) * (1.0 - 0.35 * ca * ca)
        # Back torso (+Y => sa > 0): subtle lat taper & spinal furrow
        if sa > 0.0:
            y += pinch_back * (sa ** 1.3)
            if spine_groove > 0.0 and abs(ca) < 0.28:
                y -= spine_groove * (1.0 - (abs(ca) / 0.28))
        pts.append(center + Vector((x, y, 0.0)))
    return pts


def _build_torso_and_head(bm, radial_segs: int):
    """Loft realistic anatomical pelvis, waist, ribcage, shoulders, neck, and cranium."""
    # Slimmer internal torso/cranial proportions strictly recessed inside plate/helmet shells
    slices = [
        # (center, rx, ry, pinch_back, chest_bulge, spine_groove)
        (Vector((0.0, 0.005, 0.87)), 0.120, 0.078, 0.010, 0.000, 0.004),
        (Vector((0.0, 0.002, 0.94)), 0.132, 0.086, 0.014, 0.000, 0.006),  # Pelvis/hips
        (Vector((0.0, 0.000, 1.03)), 0.120, 0.080, 0.006, 0.004, 0.008),  # Waist narrow
        (Vector((0.0, -0.005, 1.13)), 0.130, 0.088, 0.008, 0.008, 0.010), # Lower ribs
        (Vector((0.0, -0.008, 1.25)), 0.144, 0.095, 0.010, 0.012, 0.010), # Mid ribcage
        (Vector((0.0, -0.010, 1.37)), 0.148, 0.094, 0.010, 0.012, 0.008), # Upper chest recessed inside cuirass
        (Vector((0.0, -0.008, 1.44)), 0.124, 0.080, 0.008, 0.008, 0.006), # Narrow trapezius inside pauldron/gorget
        (Vector((0.0, -0.010, 1.50)), 0.060, 0.056, 0.002, 0.002, 0.004), # Neck base
        (Vector((0.0, -0.018, 1.57)), 0.050, 0.052, 0.002, 0.000, 0.000), # Neck mid
        (Vector((0.0, -0.022, 1.63)), 0.058, 0.068, 0.000, 0.006, 0.000), # Jaw/skull base inside helmet
        (Vector((0.0, -0.025, 1.71)), 0.064, 0.078, 0.000, 0.006, 0.000), # Cranium mid
        (Vector((0.0, -0.020, 1.77)), 0.054, 0.066, 0.000, 0.004, 0.000), # Upper dome
        (Vector((0.0, -0.018, 1.80)), 0.026, 0.032, 0.000, 0.000, 0.000), # Crown inside helm liner
    ]
    rings = [
        _sculpted_ring(c, rx, ry, radial_segs, pb, cb, sg)
        for (c, rx, ry, pb, cb, sg) in slices
    ]
    config.loft_rings(bm, rings, close_cap_start=True, close_cap_end=True)


def _limb_segment(bm, points_radii, segs: int = 14):
    """Sweep contoured elliptical limb cross sections along bone polyline."""
    pts = [p for p, _, _ in points_radii]
    rings = []
    prev_n = None
    for idx, (pt, rx, ry) in enumerate(points_radii):
        if idx == 0:
            tan = (pts[1] - pts[0]).normalized()
        elif idx == len(pts) - 1:
            tan = (pts[-1] - pts[-2]).normalized()
        else:
            tan = (pts[idx + 1] - pts[idx - 1]).normalized()
        if tan.length < 1e-6:
            tan = Vector((0.0, 0.0, -1.0))

        # Keep forward axis aligned toward -Y where safe
        fwd_hint = Vector((0.0, -1.0, 0.0))
        if abs(tan.dot(fwd_hint)) > 0.92:
            fwd_hint = Vector((1.0, 0.0, 0.0))
        if prev_n is None:
            side = fwd_hint.cross(tan).normalized()
            fwd = tan.cross(side).normalized()
        else:
            side = prev_n - tan * prev_n.dot(tan)
            if side.length < 1e-5:
                side = fwd_hint.cross(tan).normalized()
            else:
                side.normalize()
            fwd = tan.cross(side).normalized()
        prev_n = side

        ring = []
        for s in range(segs):
            a = 2.0 * math.pi * s / segs
            offset = side * (math.cos(a) * rx) + fwd * (math.sin(a) * ry)
            ring.append(pt + offset)
        rings.append(ring)

    config.loft_rings(bm, rings, close_cap_start=True, close_cap_end=True)


def _build_arms(bm, segs: int):
    j = config.JOINTS
    # Right arm (-X, raised slightly & angled outward holding sword)
    sr, er, wr, hr = j["shoulder_R"], j["elbow_R"], j["wrist_R"], j["hand_R"]
    pts_r = [
        (sr + Vector((0.032, 0.0, -0.018)), 0.041, 0.042),
        (sr.lerp(er, 0.30), 0.042, 0.043),
        (sr.lerp(er, 0.72), 0.039, 0.040),
        (er, 0.034, 0.035),
        (er.lerp(wr, 0.35), 0.036, 0.035),
        (er.lerp(wr, 0.78), 0.028, 0.027),
        (wr, 0.023, 0.022),
        (hr, 0.024, 0.019),
    ]
    _limb_segment(bm, pts_r, segs=segs)

    # Left arm (+X, relaxed near hip)
    sl, el, wl, hl = j["shoulder_L"], j["elbow_L"], j["wrist_L"], j["hand_L"]
    pts_l = [
        (sl + Vector((-0.032, 0.0, -0.018)), 0.041, 0.042),
        (sl.lerp(el, 0.30), 0.042, 0.043),
        (sl.lerp(el, 0.72), 0.039, 0.040),
        (el, 0.034, 0.035),
        (el.lerp(wl, 0.35), 0.036, 0.035),
        (el.lerp(wl, 0.78), 0.028, 0.027),
        (wl, 0.023, 0.022),
        (hl, 0.024, 0.019),
    ]
    _limb_segment(bm, pts_l, segs=segs)


def _build_legs_and_feet(bm, segs: int):
    j = config.JOINTS
    for side in ("R", "L"):
        hip = j[f"hip_{side}"]
        knee = j[f"knee_{side}"]
        ankle = j[f"ankle_{side}"]
        ball = j[f"foot_ball_{side}"]
        toe = j[f"foot_toe_{side}"]

        leg_pts = [
            (hip + Vector((0.0, 0.0, 0.02)), 0.072, 0.074),
            (hip.lerp(knee, 0.25), 0.068, 0.070),
            (hip.lerp(knee, 0.65), 0.058, 0.060),
            (knee, 0.046, 0.048),
            (knee.lerp(ankle, 0.28), 0.048, 0.052),
            (knee.lerp(ankle, 0.68), 0.036, 0.038),
            (ankle, 0.032, 0.034),
            (Vector((ankle.x, ankle.y, 0.045)), 0.032, 0.038),
        ]
        _limb_segment(bm, leg_pts, segs=segs)

        heel_c = Vector((ankle.x, ankle.y + 0.028, 0.032))
        instep_c = Vector(((ankle.x + ball.x) * 0.5, (ankle.y + ball.y) * 0.5, 0.032))
        foot_pts = [
            (heel_c, 0.032, 0.024),
            (instep_c, 0.036, 0.026),
            (Vector((ball.x, ball.y, 0.024)), 0.038, 0.020),
            (Vector((toe.x, toe.y, 0.016)), 0.028, 0.012),
        ]
        _limb_segment(bm, foot_pts, segs=max(10, segs - 2))


def _build_hand_fingers(bm, side: str, segs: int = 8):
    """Add 5 articulated anatomical finger chains to the under-body mesh."""
    j = config.JOINTS
    wrist = j[f"wrist_{side}"]
    hand = j[f"hand_{side}"]
    palm_dir = (hand - wrist).normalized()
    sign = -1.0 if side == "R" else 1.0  # -X for R, +X for L

    if side == "R":
        # Right fingers curl around the vertical sword grip
        grip_c = config.SWORD_MAIN["grip_center"]
        # Fingers wrap toward +Y and +X around the leather handle
        finger_offsets = [(-0.022, 0.008), (-0.008, 0.008), (0.008, 0.008), (0.022, 0.006)]
        for f_idx, (dz, dy) in enumerate(finger_offsets):
            knuckle = hand + Vector((0.016, -0.014, dz))
            mid_j = Vector((grip_c.x - 0.020, grip_c.y - 0.020 + dy * 0.4, grip_c.z + dz))
            tip = Vector((grip_c.x + 0.016, grip_c.y - 0.004 + dy, grip_c.z + dz))
            pts = [
                (knuckle, 0.0074, 0.0074),
                (mid_j, 0.0066, 0.0066),
                (tip, 0.0054, 0.0054),
            ]
            _limb_segment(bm, pts, segs=segs)
        # Right thumb locks around front/inner side of grip
        t0 = hand + Vector((0.020, -0.018, 0.032))
        t1 = grip_c + Vector((0.018, -0.016, 0.042))
        t2 = grip_c + Vector((-0.005, -0.022, 0.036))
        _limb_segment(bm, [(t0, 0.0085, 0.0085), (t1, 0.0078, 0.0078), (t2, 0.0062, 0.0062)], segs=segs)
    else:
        # Left hand relaxed beside thigh with gentle finger curl
        for f_idx in range(4):
            off_y = -0.026 + f_idx * 0.017
            f_len = 0.072 - abs(f_idx - 1.2) * 0.010
            k = hand + Vector((0.006, off_y, -0.010))
            m = k + Vector((-0.010, off_y * 0.1, -f_len * 0.55))
            t = m + Vector((-0.022, off_y * 0.1, -f_len * 0.45))
            _limb_segment(bm, [(k, 0.0072, 0.0072), (m, 0.0064, 0.0064), (t, 0.0052, 0.0052)], segs=segs)
        # Left thumb forward
        tk = hand + Vector((0.004, -0.036, 0.010))
        tm = tk + Vector((-0.012, -0.016, -0.028))
        tt = tm + Vector((-0.014, -0.005, -0.024))
        _limb_segment(bm, [(tk, 0.0082, 0.0082), (tm, 0.0074, 0.0074), (tt, 0.0058, 0.0058)], segs=segs)


def build_character_body(detail: str = "MEDIUM") -> dict:
    """Build complete coherent articulated humanoid underbody mesh in 01_BODY."""
    ds = config.DETAIL_SETTINGS[detail]
    segs = max(12, ds["radial_segs"] - 2)
    bm = bmesh.new()

    _build_torso_and_head(bm, radial_segs=segs)
    _build_arms(bm, segs=max(10, segs - 4))
    _build_legs_and_feet(bm, segs=max(10, segs - 4))
    _build_hand_fingers(bm, "R", segs=8)
    _build_hand_fingers(bm, "L", segs=8)

    body_obj = config.finalize_bmesh(
        bm,
        name="Knight_UnderBody",
        collection_name="01_BODY",
        mat_name="MAT_Leather_Dark",
        smooth=True,
        box_uv_scale=2.0,
    )
    return {"body": body_obj}
