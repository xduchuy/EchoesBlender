"""Functional humanoid + secondary equipment armature & non-destructive skinning
for THE FORGOTTEN KNIGHT in collection 02_ARMATURE (Section 18).
Preserves the exact static reference pose while supporting future posing/animation
and clean GLB export:
- Rigid steel plates, gauntlets, helmet, weapons, belts -> 1.0 rigid bone weight
- Soft cloth garments, chainmail sleeves/skirt, underbody -> smooth inverse-distance weights
"""

import math
import bpy
from mathutils import Vector, Matrix, Quaternion
import config


# Parent map & exact bone chains (head_key_or_vec, tail_key_or_vec, parent_name)
def _build_bone_specs():
    j = config.JOINTS
    sb = config.SWORD_BACK
    la = config.LANTERN_ANCHOR

    return [
        ("Root", Vector((0.0, 0.0, 0.0)), Vector((0.0, -0.15, 0.0)), None),
        ("Pelvis", j["pelvis"] - Vector((0, 0, 0.04)), j["spine_low"], "Root"),
        ("Spine", j["spine_low"], j["spine_mid"], "Pelvis"),
        ("Chest", j["spine_mid"], j["neck_base"], "Spine"),
        ("Neck", j["neck_base"], j["head_pivot"], "Chest"),
        ("Head", j["head_pivot"], j["head_top"], "Neck"),

        # Left Arm
        ("Clavicle_L", j["clavicle_L"], j["shoulder_L"], "Chest"),
        ("UpperArm_L", j["shoulder_L"], j["elbow_L"], "Clavicle_L"),
        ("Forearm_L", j["elbow_L"], j["wrist_L"], "UpperArm_L"),
        ("Hand_L", j["wrist_L"], j["hand_L"], "Forearm_L"),
        ("Fingers_L", j["hand_L"], j["hand_L"] + Vector((-0.02, -0.01, -0.08)), "Hand_L"),

        # Right Arm
        ("Clavicle_R", j["clavicle_R"], j["shoulder_R"], "Chest"),
        ("UpperArm_R", j["shoulder_R"], j["elbow_R"], "Clavicle_R"),
        ("Forearm_R", j["elbow_R"], j["wrist_R"], "UpperArm_R"),
        ("Hand_R", j["wrist_R"], j["hand_R"], "Forearm_R"),
        ("Fingers_R", j["hand_R"], config.SWORD_MAIN["grip_center"] + Vector((0.02, -0.02, -0.02)), "Hand_R"),

        # Left Leg
        ("Thigh_L", j["hip_L"], j["knee_L"], "Pelvis"),
        ("Shin_L", j["knee_L"], j["ankle_L"], "Thigh_L"),
        ("Foot_L", j["ankle_L"], j["foot_ball_L"], "Shin_L"),
        ("Toe_L", j["foot_ball_L"], j["foot_toe_L"], "Foot_L"),

        # Right Leg
        ("Thigh_R", j["hip_R"], j["knee_R"], "Pelvis"),
        ("Shin_R", j["knee_R"], j["ankle_R"], "Thigh_R"),
        ("Foot_R", j["ankle_R"], j["foot_ball_R"], "Shin_R"),
        ("Toe_R", j["foot_ball_R"], j["foot_toe_R"], "Foot_R"),

        # Secondary dynamic rig bones (future animation support per Section 18)
        ("Cape_Upper", Vector((0.0, 0.14, 1.44)), Vector((0.0, 0.18, 1.05)), "Chest"),
        ("Cape_Mid", Vector((0.0, 0.18, 1.05)), Vector((0.0, 0.21, 0.65)), "Cape_Upper"),
        ("Cape_Lower", Vector((0.0, 0.21, 0.65)), Vector((0.0, 0.23, 0.24)), "Cape_Mid"),
        ("Weapon_Back_Bone", sb["scabbard_top"], sb["scabbard_tip"], "Chest"),
        ("Weapon_Main_Bone", config.SWORD_MAIN["guard_pos"], config.SWORD_MAIN["tip_pos"], "Hand_R"),
        ("Lantern_Swing", la + Vector((-0.02, 0.0, 0.04)), la + Vector((0.0, 0.0, -0.15)), "Pelvis"),
    ]


# Strict single-bone rigid bindings (zero distortion on plate steel/metal/weapons)
RIGID_OBJECT_BONE_MAP = {
    "Helm_Skull": "Head",
    "Helm_Crest": "Head",
    "Helm_Brow_Brim": "Head",
    "Helm_Faceguard": "Head",
    "Helm_InnerShadow": "Head",
    "Helm_Rivets": "Head",

    "Armor_Cuirass": "Chest",
    "Armor_Chest_Heraldry": "Chest",
    "Armor_Fauld_1": "Spine",
    "Armor_Fauld_2": "Pelvis",
    "Armor_Tasset_L": "Thigh_L",
    "Armor_Tasset_Trim_L": "Thigh_L",
    "Armor_Tasset_R": "Thigh_R",
    "Armor_Tasset_Trim_R": "Thigh_R",

    "Armor_Pauldron_L": "UpperArm_L",
    "Armor_Pauldron_Rim_L": "UpperArm_L",
    "Armor_ShoulderLames_L": "UpperArm_L",
    "Armor_Rivets_Arm_L": "UpperArm_L",
    "Armor_Couter_L": "Forearm_L",
    "Armor_Vambrace_L": "Forearm_L",
    "Armor_Cuff_Brass_L": "Forearm_L",
    "Armor_Gauntlet_L": "Hand_L",

    "Armor_Pauldron_R": "UpperArm_R",
    "Armor_ShoulderLames_R": "UpperArm_R",
    "Armor_Couter_R": "Forearm_R",
    "Armor_Vambrace_R": "Forearm_R",
    "Armor_Cuff_Brass_R": "Forearm_R",
    "Armor_Gauntlet_R": "Hand_R",

    "Armor_Cuisse_L": "Thigh_L",
    "Armor_Poleyn_L": "Shin_L",
    "Armor_Greave_Front_L": "Shin_L",
    "Armor_Greave_Trim_L": "Shin_L",
    "Armor_Greave_Leather_L": "Shin_L",
    "Armor_Calf_Straps_L": "Shin_L",
    "Armor_Boot_L": "Foot_L",
    "Armor_Sabaton_Plates_L": "Foot_L",

    "Armor_Cuisse_R": "Thigh_R",
    "Armor_Poleyn_R": "Shin_R",
    "Armor_Greave_Front_R": "Shin_R",
    "Armor_Greave_Trim_R": "Shin_R",
    "Armor_Greave_Leather_R": "Shin_R",
    "Armor_Calf_Straps_R": "Shin_R",
    "Armor_Boot_R": "Foot_R",
    "Armor_Sabaton_Plates_R": "Foot_R",

    "Belts_Waist_Assembly": "Pelvis",
    "Belts_Buckles_Hardware": "Pelvis",
    "Belts_Leather_Pouches": "Pelvis",
    "Belts_Chest_Baldric": "Chest",

    "Weapon_Longsword_Blade": "Weapon_Main_Bone",
    "Weapon_Longsword_Guard": "Weapon_Main_Bone",
    "Weapon_Longsword_Grip": "Weapon_Main_Bone",
    "Weapon_Longsword_Pommel": "Weapon_Main_Bone",

    "Weapon_Back_Scabbard": "Weapon_Back_Bone",
    "Weapon_Back_Scabbard_Fittings": "Weapon_Back_Bone",
    "Weapon_Back_Guard": "Weapon_Back_Bone",
    "Weapon_Back_Grip": "Weapon_Back_Bone",
    "Weapon_Back_Pommel": "Weapon_Back_Bone",

    "Lantern_Chain_Hook": "Pelvis",
    "Lantern_Frame_Housing": "Lantern_Swing",
    "Lantern_Glass_Chamber": "Lantern_Swing",
    "Lantern_Inner_Chamber": "Lantern_Swing",
}


# Smooth organic multi-bone bindings for cloth, mail, and underbody
DEFORM_GROUPS_MAP = {
    "Knight_UnderBody": [
        "Pelvis", "Spine", "Chest", "Neck", "Head",
        "UpperArm_L", "Forearm_L", "Hand_L", "Fingers_L",
        "UpperArm_R", "Forearm_R", "Hand_R", "Fingers_R",
        "Thigh_L", "Shin_L", "Foot_L", "Toe_L",
        "Thigh_R", "Shin_R", "Foot_R", "Toe_R",
    ],
    "Hood_Scarf_Wrap_1": ["Neck", "Chest", "Head"],
    "Hood_Scarf_Wrap_2": ["Neck", "Chest", "UpperArm_R"],
    "Hood_Scarf_Drape": ["Chest", "Neck", "UpperArm_R"],
    "Hood_Rear_Cowl": ["Head", "Neck", "Chest"],
    "Tunic_Upper_Surcoat": ["Pelvis", "Spine", "Chest"],
    "Tabard_Front_L": ["Pelvis", "Thigh_L", "Shin_L"],
    "Tabard_Front_R": ["Pelvis", "Thigh_R", "Shin_R"],
    "Cape_Back_Cloak": ["Chest", "UpperArm_L", "UpperArm_R", "Cape_Upper", "Cape_Mid", "Cape_Lower"],
    "Chainmail_SleeveBase_L": ["UpperArm_L", "Forearm_L"],
    "Chainmail_Rings_Arm_L": ["UpperArm_L", "Forearm_L"],
    "Chainmail_SleeveBase_R": ["UpperArm_R", "Forearm_R"],
    "Chainmail_Rings_Arm_R": ["UpperArm_R", "Forearm_R"],
    "Chainmail_SkirtBase": ["Pelvis", "Thigh_L", "Thigh_R"],
    "Chainmail_Rings_Hauberk": ["Pelvis", "Thigh_L", "Thigh_R"],
    "Chainmail_Rings_Neck": ["Neck", "Chest"],
}


def _dist_point_to_segment(pt: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    len_sq = ab.length_squared
    if len_sq < 1e-8:
        return (pt - a).length
    t = max(0.0, min(1.0, (pt - a).dot(ab) / len_sq))
    proj = a + ab * t
    return (pt - proj).length


def _bind_rigid(obj, rig, bone_name: str):
    """Attach Armature modifier with 1.0 weight to single bone so mesh never distorts."""
    obj.parent = rig
    vg = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
    all_idx = [v.index for v in obj.data.vertices]
    if all_idx:
        vg.add(all_idx, 1.0, "REPLACE")
    mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = rig
    mod.use_vertex_groups = True


def _bind_smooth(obj, rig, bone_names: list, bone_segs: dict):
    """Assign smooth inverse-distance normalized vertex weights across allowed bones."""
    obj.parent = rig
    vgroups = {bn: (obj.vertex_groups.get(bn) or obj.vertex_groups.new(name=bn)) for bn in bone_names}
    for v in obj.data.vertices:
        co = v.co
        raw_w = {}
        total = 0.0
        for bn in bone_names:
            a, b = bone_segs[bn]
            d = _dist_point_to_segment(co, a, b)
            # Crisp inverse quartic falloff for clean anatomical articulation
            w = 1.0 / ((d + 0.045) ** 3.2)
            raw_w[bn] = w
            total += w
        if total > 1e-8:
            for bn, w in raw_w.items():
                nw = w / total
                if nw > 0.01:
                    vgroups[bn].add([v.index], nw, "REPLACE")
    mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = rig
    mod.use_vertex_groups = True


def build_rigging() -> dict:
    """Create Rig_ForgottenKnight armature and bind all character meshes cleanly
    without disturbing the sculpted static reference pose."""
    arm_data = bpy.data.armatures.new("Rig_ForgottenKnight_Data")
    arm_data.display_type = "OCTAHEDRAL"
    arm_obj = bpy.data.objects.new("Rig_ForgottenKnight", arm_data)
    config.link_object(arm_obj, "02_ARMATURE")

    # Populate edit bones cleanly
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    specs = _build_bone_specs()
    bone_segs = {}
    ebones = arm_data.edit_bones
    for bname, head, tail, _ in specs:
        eb = ebones.new(bname)
        eb.head = head
        eb.tail = tail if (tail - head).length > 0.005 else head + Vector((0.0, 0.0, 0.05))
        eb.use_connect = False
        bone_segs[bname] = (eb.head.copy(), eb.tail.copy())

    for bname, _, _, pname in specs:
        if pname and pname in ebones:
            ebones[bname].parent = ebones[pname]

    for bname, eb in ebones.items():
        eb.align_roll(Vector((0.0, -1.0, 0.0)))

    bpy.ops.object.mode_set(mode="OBJECT")

    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"

    # Bind rigid pieces via exact single-bone vertex weights (zero pose shift, GLB compatible)
    bound_rigid = 0
    bound_deform = 0
    for obj_name, bone_name in RIGID_OBJECT_BONE_MAP.items():
        obj = bpy.data.objects.get(obj_name)
        if obj and obj.type == "MESH":
            _bind_rigid(obj, arm_obj, bone_name)
            bound_rigid += 1

    # Bind soft cloth/underbody meshes smoothly
    for obj_name, bnames in DEFORM_GROUPS_MAP.items():
        obj = bpy.data.objects.get(obj_name)
        if obj and obj.type == "MESH":
            valid_bones = [bn for bn in bnames if bn in bone_segs]
            if valid_bones:
                _bind_smooth(obj, arm_obj, valid_bones, bone_segs)
                bound_deform += 1

    # Also parent Light_Lantern_Wick inside 14_LANTERN to root/lantern swing bone cleanly
    wick_light = bpy.data.objects.get("Light_Lantern_Wick")
    if wick_light:
        wick_light.parent = arm_obj
        wick_light.parent_type = "BONE"
        wick_light.parent_bone = "Lantern_Swing"
        # Preserve world position on bone parent
        pbone = arm_obj.pose.bones["Lantern_Swing"]
        # In Edit/Pose rest state, bone space origin is at bone TAIL!
        bone_mat = arm_obj.matrix_world @ pbone.matrix @ Matrix.Translation((0.0, pbone.length, 0.0))
        wick_light.matrix_parent_inverse = bone_mat.inverted()

    # Author clean multi-clip NLA skeletal animations while restoring neutral rest pose
    anim_clips = create_knight_animations(arm_obj)

    return {
        "armature": arm_obj,
        "bone_count": len(specs),
        "rigid_bound": bound_rigid,
        "deform_bound": bound_deform,
        "animations": anim_clips,
    }


def _reset_pose(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pb.location = Vector((0.0, 0.0, 0.0))


def _set_world_rot(arm_obj, bone_name: str, rx: float = 0.0, ry: float = 0.0, rz: float = 0.0, frame: int | None = None):
    """Apply world-space delta Euler around (+X left, -Y fwd, +Z up) converted cleanly into bone rest space."""
    pb = arm_obj.pose.bones.get(bone_name)
    if pb is None:
        return
    pb.rotation_mode = "QUATERNION"
    r_rest = pb.bone.matrix_local.to_3x3()
    r_world = (
        Matrix.Rotation(rz, 3, Vector((0.0, 0.0, 1.0)))
        @ Matrix.Rotation(ry, 3, Vector((0.0, -1.0, 0.0)))
        @ Matrix.Rotation(rx, 3, Vector((1.0, 0.0, 0.0)))
    )
    pb.rotation_quaternion = (r_rest.inverted() @ r_world @ r_rest).to_quaternion()
    if frame is not None:
        pb.keyframe_insert("rotation_quaternion", frame=frame)


def _set_world_loc(arm_obj, bone_name: str, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0, frame: int | None = None):
    pb = arm_obj.pose.bones.get(bone_name)
    if pb is None:
        return
    r_rest = pb.bone.matrix_local.to_3x3()
    pb.location = r_rest.inverted() @ Vector((dx, dy, dz))
    if frame is not None:
        pb.keyframe_insert("location", frame=frame)


def _push_nla_clip(arm_obj, clip_name: str, frame_start: int, builder_fn):
    ad = arm_obj.animation_data or arm_obj.animation_data_create()
    act = bpy.data.actions.new(clip_name)
    _reset_pose(arm_obj)
    ad.action = act
    builder_fn()
    slot = ad.action_slot
    if slot is not None and len(act.layers) > 0 and len(act.layers[0].strips) > 0:
        cb = act.layers[0].strips[0].channelbag(slot)
        if cb is not None:
            for fc in cb.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.handle_left_type = "AUTO_CLAMPED"
                    kp.handle_right_type = "AUTO_CLAMPED"
    track = ad.nla_tracks.new()
    track.name = clip_name
    strip = track.strips.new(clip_name, frame_start, act)
    if slot is not None and hasattr(strip, "action_slot"):
        strip.action_slot = slot
    strip.use_auto_blend = False
    ad.action = None
    _reset_pose(arm_obj)


def create_knight_animations(arm_obj) -> list[str]:
    """Author 9 skeletal NLA animation clips (Idle, Walk, Run, Jump/Land, Turn, Sword_Ready) at 24fps."""
    if bpy.context.scene:
        bpy.context.scene.render.fps = 24
    clips = []

    def _clip_idle():
        for f in range(0, 49, 6):
            ph = 2.0 * math.pi * (f / 48.0)
            b = math.sin(ph)
            _set_world_loc(arm_obj, "Pelvis", dz=-0.004 * (0.5 - 0.5 * math.cos(ph)), frame=f)
            _set_world_rot(arm_obj, "Spine", rx=0.012 * b, frame=f)
            _set_world_rot(arm_obj, "Chest", rx=0.016 * b, rz=0.012 * math.sin(ph * 0.5), frame=f)
            _set_world_rot(arm_obj, "Head", rx=0.016 * math.sin(ph), rz=0.045 * math.sin(ph), frame=f)
            _set_world_rot(arm_obj, "UpperArm_L", rx=0.015 * b, ry=-0.02 * b, frame=f)
            _set_world_rot(arm_obj, "UpperArm_R", rx=-0.012 * b, frame=f)
            _set_world_rot(arm_obj, "Cape_Upper", rx=0.028 + 0.014 * b, ry=0.012 * math.cos(ph), frame=f)
            _set_world_rot(arm_obj, "Cape_Mid", rx=0.035 + 0.025 * math.sin(ph - 0.7), ry=0.02 * math.cos(ph - 0.5), frame=f)
            _set_world_rot(arm_obj, "Cape_Lower", rx=0.045 + 0.036 * math.sin(ph - 1.4), ry=0.028 * math.cos(ph - 1.0), frame=f)
            _set_world_rot(arm_obj, "Lantern_Swing", rx=0.022 * math.sin(ph), ry=0.018 * math.cos(ph), frame=f)

    def _clip_walk():
        for f in range(0, 33, 2):
            ph = 2.0 * math.pi * (f / 32.0)
            s = math.sin(ph)
            c = math.cos(ph)
            # Grounded alternating stride without hyperextension
            thigh_l = -0.34 * s
            thigh_r = 0.34 * s
            shin_l = max(0.03, 0.50 * max(0.0, c) + 0.08 * max(0.0, -s))
            shin_r = max(0.03, 0.50 * max(0.0, -c) + 0.08 * max(0.0, s))
            foot_l = -0.22 * s - 0.14 * max(0.0, c)
            foot_r = 0.22 * s - 0.14 * max(0.0, -c)
            bob = -0.022 * (0.5 - 0.5 * math.cos(2.0 * ph))
            p_yaw = 0.055 * c
            p_roll = 0.032 * s
            _set_world_loc(arm_obj, "Pelvis", dz=bob, frame=f)
            _set_world_rot(arm_obj, "Pelvis", rx=0.02, ry=p_roll, rz=p_yaw, frame=f)
            _set_world_rot(arm_obj, "Spine", rx=0.045, ry=-p_roll * 0.5, rz=-p_yaw * 0.6, frame=f)
            _set_world_rot(arm_obj, "Chest", rx=0.040, rz=-p_yaw * 0.65, frame=f)
            _set_world_rot(arm_obj, "Neck", rx=-0.035, rz=p_yaw * 0.45, frame=f)
            _set_world_rot(arm_obj, "Head", rx=-0.020, rz=p_yaw * 0.40, frame=f)
            _set_world_rot(arm_obj, "Thigh_L", rx=thigh_l, frame=f)
            _set_world_rot(arm_obj, "Shin_L", rx=shin_l, frame=f)
            _set_world_rot(arm_obj, "Foot_L", rx=foot_l, frame=f)
            _set_world_rot(arm_obj, "Thigh_R", rx=thigh_r, frame=f)
            _set_world_rot(arm_obj, "Shin_R", rx=shin_r, frame=f)
            _set_world_rot(arm_obj, "Foot_R", rx=foot_r, frame=f)
            _set_world_rot(arm_obj, "UpperArm_L", rx=0.28 * s, frame=f)
            _set_world_rot(arm_obj, "Forearm_L", rx=-0.16 - 0.14 * max(0.0, -s), frame=f)
            # Keep right arm + longsword lifted cleanly above courtyard stone slabs
            _set_world_rot(arm_obj, "UpperArm_R", rx=-0.14 * s - 0.12, ry=0.04, frame=f)
            _set_world_rot(arm_obj, "Forearm_R", rx=-0.18, frame=f)
            _set_world_rot(arm_obj, "Weapon_Main_Bone", rx=-0.10, frame=f)
            _set_world_rot(arm_obj, "Cape_Upper", rx=0.14 + 0.04 * math.sin(ph - 0.4), ry=0.03 * s, frame=f)
            _set_world_rot(arm_obj, "Cape_Mid", rx=0.12 + 0.07 * math.sin(ph - 1.1), ry=0.04 * c, frame=f)
            _set_world_rot(arm_obj, "Cape_Lower", rx=0.10 + 0.09 * math.sin(ph - 1.8), ry=0.05 * s, frame=f)
            _set_world_rot(arm_obj, "Lantern_Swing", rx=0.12 * c, ry=0.08 * s, frame=f)

    def _clip_run():
        for f in range(0, 21, 2):
            ph = 2.0 * math.pi * (f / 20.0)
            s = math.sin(ph)
            c = math.cos(ph)
            thigh_l = -0.56 * s - 0.06
            thigh_r = 0.56 * s - 0.06
            shin_l = max(0.05, 0.92 * max(0.0, c) + 0.14)
            shin_r = max(0.05, 0.92 * max(0.0, -c) + 0.14)
            foot_l = -0.26 * s - 0.20 * max(0.0, c)
            foot_r = 0.26 * s - 0.20 * max(0.0, -c)
            bob = -0.042 * (0.5 - 0.5 * math.cos(2.0 * ph))
            p_yaw = 0.085 * c
            _set_world_loc(arm_obj, "Pelvis", dz=bob, frame=f)
            _set_world_rot(arm_obj, "Pelvis", rx=0.05, ry=0.05 * s, rz=p_yaw, frame=f)
            _set_world_rot(arm_obj, "Spine", rx=0.11, rz=-p_yaw * 0.65, frame=f)
            _set_world_rot(arm_obj, "Chest", rx=0.10, rz=-p_yaw * 0.70, frame=f)
            _set_world_rot(arm_obj, "Neck", rx=-0.10, rz=p_yaw * 0.5, frame=f)
            _set_world_rot(arm_obj, "Head", rx=-0.06, rz=p_yaw * 0.4, frame=f)
            _set_world_rot(arm_obj, "Thigh_L", rx=thigh_l, frame=f)
            _set_world_rot(arm_obj, "Shin_L", rx=shin_l, frame=f)
            _set_world_rot(arm_obj, "Foot_L", rx=foot_l, frame=f)
            _set_world_rot(arm_obj, "Thigh_R", rx=thigh_r, frame=f)
            _set_world_rot(arm_obj, "Shin_R", rx=shin_r, frame=f)
            _set_world_rot(arm_obj, "Foot_R", rx=foot_r, frame=f)
            _set_world_rot(arm_obj, "UpperArm_L", rx=0.46 * s, frame=f)
            _set_world_rot(arm_obj, "Forearm_L", rx=-0.52 - 0.18 * max(0.0, -s), frame=f)
            # Swept back combat carry clears blade tip above ground while sprinting
            _set_world_rot(arm_obj, "UpperArm_R", rx=0.16 * s + 0.12, ry=-0.08, frame=f)
            _set_world_rot(arm_obj, "Forearm_R", rx=-0.34, frame=f)
            _set_world_rot(arm_obj, "Weapon_Main_Bone", rx=0.22, frame=f)
            _set_world_rot(arm_obj, "Cape_Upper", rx=0.26 + 0.06 * s, ry=0.05 * c, frame=f)
            _set_world_rot(arm_obj, "Cape_Mid", rx=0.20 + 0.11 * math.sin(ph - 0.9), ry=0.07 * s, frame=f)
            _set_world_rot(arm_obj, "Cape_Lower", rx=0.18 + 0.14 * math.sin(ph - 1.7), ry=0.09 * c, frame=f)
            _set_world_rot(arm_obj, "Lantern_Swing", rx=0.24 + 0.16 * c, ry=0.12 * s, frame=f)

    def _clip_jump_start():
        poses = [
            (0,  0.00,  0.00,  0.04, -0.04, 0.08,  0.00,  0.00),
            (4, -0.075, 0.16,  0.14, -0.44, 0.74, -0.26, -0.18),
            (10, 0.035, -0.04, -0.05,  0.08, 0.08,  0.22,  0.28),
        ]
        for f, dz, chest_rx, sp_rx, th_rx, sh_rx, ft_rx, cape_rx in poses:
            _set_world_loc(arm_obj, "Pelvis", dz=dz, frame=f)
            _set_world_rot(arm_obj, "Spine", rx=sp_rx, frame=f)
            _set_world_rot(arm_obj, "Chest", rx=chest_rx, frame=f)
            _set_world_rot(arm_obj, "Thigh_L", rx=th_rx, frame=f)
            _set_world_rot(arm_obj, "Shin_L", rx=sh_rx, frame=f)
            _set_world_rot(arm_obj, "Foot_L", rx=ft_rx, frame=f)
            _set_world_rot(arm_obj, "Thigh_R", rx=th_rx * 0.9, frame=f)
            _set_world_rot(arm_obj, "Shin_R", rx=sh_rx * 0.9, frame=f)
            _set_world_rot(arm_obj, "Foot_R", rx=ft_rx, frame=f)
            _set_world_rot(arm_obj, "UpperArm_L", rx=-0.22 if f == 10 else 0.18, frame=f)
            _set_world_rot(arm_obj, "Forearm_R", rx=-0.25, frame=f)
            _set_world_rot(arm_obj, "Cape_Upper", rx=cape_rx, frame=f)

    def _clip_airborne():
        for f in range(0, 25, 6):
            ph = 2.0 * math.pi * (f / 24.0)
            s = math.sin(ph)
            _set_world_rot(arm_obj, "Chest", rx=0.06, frame=f)
            _set_world_rot(arm_obj, "Thigh_L", rx=-0.38 + 0.04 * s, frame=f)
            _set_world_rot(arm_obj, "Shin_L", rx=0.62 + 0.05 * s, frame=f)
            _set_world_rot(arm_obj, "Thigh_R", rx=0.14 - 0.04 * s, frame=f)
            _set_world_rot(arm_obj, "Shin_R", rx=0.22, frame=f)
            _set_world_rot(arm_obj, "UpperArm_L", rx=-0.28, ry=-0.12, frame=f)
            _set_world_rot(arm_obj, "Forearm_L", rx=-0.35, frame=f)
            _set_world_rot(arm_obj, "UpperArm_R", rx=-0.16, frame=f)
            _set_world_rot(arm_obj, "Forearm_R", rx=-0.26, frame=f)
            _set_world_rot(arm_obj, "Cape_Upper", rx=0.34 + 0.06 * s, frame=f)
            _set_world_rot(arm_obj, "Cape_Mid", rx=0.22 + 0.08 * math.cos(ph), frame=f)
            _set_world_rot(arm_obj, "Lantern_Swing", rx=0.24 + 0.08 * s, frame=f)

    def _clip_land():
        poses = [
            (0,  0.00, 0.06, -0.24, 0.42,  0.22, -0.10),
            (5, -0.09, 0.18, -0.44, 0.76,  0.14, -0.30),
            (14, 0.00, 0.00,  0.00, 0.00,  0.05,  0.00),
        ]
        for f, dz, chest_rx, th_rx, sh_rx, cape_rx, lant_rx in poses:
            _set_world_loc(arm_obj, "Pelvis", dz=dz, frame=f)
            _set_world_rot(arm_obj, "Spine", rx=chest_rx * 0.5, frame=f)
            _set_world_rot(arm_obj, "Chest", rx=chest_rx, frame=f)
            _set_world_rot(arm_obj, "Thigh_L", rx=th_rx, frame=f)
            _set_world_rot(arm_obj, "Shin_L", rx=sh_rx, frame=f)
            _set_world_rot(arm_obj, "Thigh_R", rx=th_rx * 0.9, frame=f)
            _set_world_rot(arm_obj, "Shin_R", rx=sh_rx * 0.9, frame=f)
            _set_world_rot(arm_obj, "Forearm_R", rx=-0.24 if f == 5 else -0.04, frame=f)
            _set_world_rot(arm_obj, "Cape_Upper", rx=cape_rx, frame=f)
            _set_world_rot(arm_obj, "Lantern_Swing", rx=lant_rx, frame=f)

    def _make_turn(sign: float):
        def _fn():
            for f in (0, 8, 16):
                a = 1.0 if f == 8 else 0.0
                _set_world_rot(arm_obj, "Chest", rz=0.14 * sign * a, frame=f)
                _set_world_rot(arm_obj, "Head", rz=0.20 * sign * a, frame=f)
                _set_world_rot(arm_obj, "Pelvis", ry=0.03 * sign * a, rz=0.06 * sign * a, frame=f)
                _set_world_rot(arm_obj, "Cape_Upper", ry=-0.10 * sign * a, frame=f)
                _set_world_rot(arm_obj, "Lantern_Swing", ry=0.09 * sign * a, frame=f)
        return _fn

    def _clip_sword_ready():
        keyframes = [
            (0,  0.00, 0.00,  0.00,  0.00,  0.00,  0.00,  0.00,  0.00),
            (10, 0.04, 0.14, -0.48, -0.72,  0.16, -0.18,  0.10, -0.12),
            (22, 0.05, 0.16, -0.52, -0.76,  0.18, -0.20,  0.12, -0.14),
            (36, 0.00, 0.00,  0.00,  0.00,  0.00,  0.00,  0.00,  0.00),
        ]
        for f, ch_rx, ch_rz, arm_rx, fa_rx, wp_rx, arm_l_rx, cape_rx, lant_ry in keyframes:
            _set_world_loc(arm_obj, "Pelvis", dz=-0.018 if 10 <= f <= 22 else 0.0, frame=f)
            _set_world_rot(arm_obj, "Chest", rx=ch_rx, rz=ch_rz, frame=f)
            _set_world_rot(arm_obj, "Head", rx=0.03 if 10 <= f <= 22 else 0.0, rz=-ch_rz * 0.5, frame=f)
            _set_world_rot(arm_obj, "UpperArm_R", rx=arm_rx, ry=0.10 if 10 <= f <= 22 else 0.0, frame=f)
            _set_world_rot(arm_obj, "Forearm_R", rx=fa_rx, frame=f)
            _set_world_rot(arm_obj, "Weapon_Main_Bone", rx=wp_rx, frame=f)
            _set_world_rot(arm_obj, "UpperArm_L", rx=arm_l_rx, frame=f)
            _set_world_rot(arm_obj, "Cape_Upper", rx=cape_rx, frame=f)
            _set_world_rot(arm_obj, "Lantern_Swing", ry=lant_ry, frame=f)

    clip_defs = [
        ("Idle", 0, _clip_idle),
        ("Walk", 0, _clip_walk),
        ("Run", 0, _clip_run),
        ("Jump_Start", 0, _clip_jump_start),
        ("Airborne", 0, _clip_airborne),
        ("Land", 0, _clip_land),
        ("Turn_Left", 0, _make_turn(1.0)),
        ("Turn_Right", 0, _make_turn(-1.0)),
        ("Sword_Ready", 0, _clip_sword_ready),
    ]
    for cname, fstart, fn in clip_defs:
        _push_nla_clip(arm_obj, cname, fstart, fn)
        clips.append(cname)
    return clips
