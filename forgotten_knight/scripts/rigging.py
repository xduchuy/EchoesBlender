"""Functional humanoid + secondary equipment armature & non-destructive skinning
for THE FORGOTTEN KNIGHT in collection 02_ARMATURE (Section 18).
Preserves the exact static reference pose while supporting future posing/animation
and clean GLB export:
- Rigid steel plates, gauntlets, helmet, weapons, belts -> 1.0 rigid bone weight
- Soft cloth garments, chainmail sleeves/skirt, underbody -> smooth inverse-distance weights
"""

import bpy
from mathutils import Vector, Matrix
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

    bpy.ops.object.mode_set(mode="OBJECT")

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

    return {
        "armature": arm_obj,
        "bone_count": len(specs),
        "rigid_bound": bound_rigid,
        "deform_bound": bound_deform,
    }
