"""Reusable Cycles PBR texture-atlas baker & glTF-compatible ORM material builder.

Used by both The Drowned Sanctuary (`scripts/export_glb.py`) and
The Forgotten Knight (`forgotten_knight/scripts/build_character.py`) on isolated
export duplicates so original `.blend` files preserve their procedural shaders.
"""

import math
import os
import tempfile
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import bpy
import numpy as np


def find_node_by_bl_idname(
    node_tree: Optional[bpy.types.NodeTree], bl_idname: str
) -> Optional[bpy.types.Node]:
    """Locate a shader node by locale-independent `bl_idname`."""
    if node_tree is None:
        return None
    fallback = None
    for node in node_tree.nodes:
        if node.bl_idname == bl_idname:
            if getattr(node, "is_active_output", False):
                return node
            if fallback is None:
                fallback = node
    return fallback


def ensure_gltf_output_node_group() -> bpy.types.NodeTree:
    """Return or create the `glTF Material Output` node group exposing `Occlusion`."""
    name = "glTF Material Output"
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return ng


def convert_curves_to_meshes(objects: Sequence[bpy.types.Object]) -> None:
    """Convert any CURVE objects in `objects` to MESH datablocks in place."""
    curves = [o for o in objects if o.type == "CURVE"]
    if not curves:
        return
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in curves:
        bpy.ops.object.select_all(action="DESELECT")
        obj.hide_viewport = False
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")


def apply_non_armature_modifiers(objects: Sequence[bpy.types.Object]) -> None:
    """Apply constructive/subdiv modifiers while preserving ARMATURE skinning."""
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in objects:
        if obj.type != "MESH" or not obj.modifiers:
            continue
        non_arm = [m for m in obj.modifiers if m.type != "ARMATURE" and m.show_viewport]
        if not non_arm:
            continue
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        bpy.ops.object.select_all(action="DESELECT")
        obj.hide_viewport = False
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for mod in list(obj.modifiers):
            if mod.type == "ARMATURE":
                continue
            try:
                if mod.show_viewport:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                else:
                    obj.modifiers.remove(mod)
            except Exception as exc:
                print(f"[pbr_bake] Warning applying modifier {mod.name} on {obj.name}: {exc}")


def _pin_existing_uv_sources(
    materials: Iterable[bpy.types.Material], default_uv_name: Optional[str]
) -> List[bpy.types.Node]:
    """Pin any unlinked TexImage or TexCoord.UV outputs to `default_uv_name` before BakeUV."""
    created_nodes: List[bpy.types.Node] = []
    if not default_uv_name:
        return created_nodes
    for mat in materials:
        if not mat or not mat.use_nodes or mat.node_tree is None:
            continue
        nt = mat.node_tree
        uv_node = None

        def _get_uv_node():
            nonlocal uv_node
            if uv_node is None:
                uv_node = nt.nodes.new("ShaderNodeUVMap")
                uv_node.uv_map = default_uv_name
                created_nodes.append(uv_node)
            return uv_node

        for node in list(nt.nodes):
            if node.bl_idname == "ShaderNodeTexImage":
                vec_in = node.inputs.get("Vector")
                if vec_in is not None and not vec_in.is_linked:
                    nt.links.new(_get_uv_node().outputs["UV"], vec_in)
            elif node.bl_idname == "ShaderNodeTexCoord":
                uv_out = node.outputs.get("UV")
                if uv_out is not None and uv_out.is_linked:
                    for link in list(uv_out.links):
                        to_sock = link.to_socket
                        nt.links.remove(link)
                        nt.links.new(_get_uv_node().outputs["UV"], to_sock)
    return created_nodes


def dedupe_by_mesh_data(objects: Sequence[bpy.types.Object]) -> List[bpy.types.Object]:
    """Return one representative MESH object per unique Mesh datablock."""
    seen: Set[bpy.types.Mesh] = set()
    reps: List[bpy.types.Object] = []
    for obj in objects:
        if obj.type != "MESH" or obj.data is None or len(obj.data.polygons) == 0:
            continue
        if obj.data in seen:
            continue
        seen.add(obj.data)
        reps.append(obj)
    return reps


def prepare_atlas_uvs(
    rep_objs: Sequence[bpy.types.Object],
    uv_layer_name: str = "BakeUV",
    island_margin: float = 0.008,
    angle_limit_deg: float = 66.0,
) -> Dict[bpy.types.Mesh, Optional[str]]:
    """Create non-overlapping `uv_layer_name` across all `rep_objs` via multi-object Edit Mode."""
    if not rep_objs:
        return {}
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    orig_uv_map: Dict[bpy.types.Mesh, Optional[str]] = {}
    for obj in rep_objs:
        mesh = obj.data
        orig_uv_map[mesh] = mesh.uv_layers.active.name if mesh.uv_layers.active else None
        bake_uv = mesh.uv_layers.get(uv_layer_name)
        if bake_uv is None:
            bake_uv = mesh.uv_layers.new(name=uv_layer_name)
        mesh.uv_layers.active = bake_uv
        bake_uv.active_render = True

    bpy.ops.object.select_all(action="DESELECT")
    for obj in rep_objs:
        obj.hide_viewport = False
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rep_objs[0]

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(
        angle_limit=math.radians(angle_limit_deg),
        island_margin=island_margin,
        area_weight=0.15,
        correct_aspect=True,
        scale_to_bounds=False,
    )
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(
        margin=island_margin,
        rotate=True,
        scale=True,
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    return orig_uv_map


def _create_target_tex_nodes(
    materials: Sequence[bpy.types.Material],
) -> Dict[bpy.types.Material, bpy.types.Node]:
    """Add an active selected Image Texture target node to each material."""
    targets: Dict[bpy.types.Material, bpy.types.Node] = {}
    for mat in materials:
        if not mat.use_nodes:
            mat.use_nodes = True
        nt = mat.node_tree
        for n in nt.nodes:
            n.select = False
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.name = "__PBR_BAKE_TARGET__"
        tex.select = True
        nt.nodes.active = tex
        targets[mat] = tex
    return targets


def _set_target_image(
    targets: Dict[bpy.types.Material, bpy.types.Node], image: bpy.types.Image
) -> None:
    """Assign `image` to every material's active bake target node."""
    for mat, tex in targets.items():
        tex.image = image
        for n in mat.node_tree.nodes:
            n.select = n == tex
        mat.node_tree.nodes.active = tex


def _ensure_solid_object_materials(obj: bpy.types.Object) -> None:
    """Guarantee at least one valid material slot so Cycles bake never skips a mesh."""
    if len(obj.data.materials) == 0 or all(m is None for m in obj.data.materials):
        fallback = bpy.data.materials.get("__BakeDefaultMat__")
        if fallback is None:
            fallback = bpy.data.materials.new("__BakeDefaultMat__")
            fallback.use_nodes = True
        if len(obj.data.materials) == 0:
            obj.data.materials.append(fallback)
        else:
            obj.data.materials[0] = fallback


def _run_emit_pass(
    temp_mats: Sequence[bpy.types.Material],
    targets: Dict[bpy.types.Material, bpy.types.Node],
    socket_name: str,
    target_image: bpy.types.Image,
    uv_layer: str,
    margin: int,
    default_scalar: float = 0.0,
) -> None:
    """Temporarily wire a Principled BSDF input to Emission, bake EMIT, and restore links."""
    saved: List[Tuple[bpy.types.NodeTree, Optional[bpy.types.NodeSocket], bpy.types.Node, bpy.types.Node]] = []
    try:
        for mat in temp_mats:
            nt = mat.node_tree
            out = find_node_by_bl_idname(nt, "ShaderNodeOutputMaterial")
            bsdf = find_node_by_bl_idname(nt, "ShaderNodeBsdfPrincipled")
            if out is None or bsdf is None:
                continue

            surf_in = out.inputs.get("Surface")
            orig_surf_from = surf_in.links[0].from_socket if (surf_in and surf_in.is_linked) else None

            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Strength"].default_value = 1.0
            inp = bsdf.inputs.get(socket_name)
            if inp is not None and inp.is_linked:
                nt.links.new(inp.links[0].from_socket, em.inputs["Color"])
            elif inp is not None:
                val = inp.default_value
                if isinstance(val, (float, int)):
                    f = float(val)
                    em.inputs["Color"].default_value = (f, f, f, 1.0)
                else:
                    tup = tuple(val)
                    em.inputs["Color"].default_value = (tup[0], tup[1], tup[2], 1.0)
            else:
                em.inputs["Color"].default_value = (default_scalar, default_scalar, default_scalar, 1.0)

            for link in list(surf_in.links):
                nt.links.remove(link)
            nt.links.new(em.outputs["Emission"], surf_in)
            saved.append((nt, orig_surf_from, out, em))

        _set_target_image(targets, target_image)
        bpy.ops.object.bake(
            type="EMIT",
            uv_layer=uv_layer,
            margin=margin,
            margin_type="EXTEND",
            use_clear=True,
        )
    finally:
        for nt, orig_surf_from, out, em in saved:
            surf_in = out.inputs.get("Surface")
            if surf_in is not None:
                for link in list(surf_in.links):
                    nt.links.remove(link)
                if orig_surf_from is not None:
                    nt.links.new(orig_surf_from, surf_in)
            if em.name in nt.nodes:
                nt.nodes.remove(em)


def _save_and_pack_png(image: bpy.types.Image, filepath: str) -> None:
    """Save image cleanly as PNG and pack into .blend so glTF embeds full pixel data."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    image.filepath_raw = filepath
    image.file_format = "PNG"
    image.save()
    image.pack()


def _read_image_pixels_np(image: bpy.types.Image) -> np.ndarray:
    """Read RGBA pixels from a Blender Image into an (N, 4) float32 numpy array quickly."""
    n_px = image.size[0] * image.size[1]
    buf = np.empty(n_px * 4, dtype=np.float32)
    image.pixels.foreach_get(buf)
    return buf.reshape(n_px, 4)


def build_baked_orm_material(
    mat_name: str,
    img_base: bpy.types.Image,
    img_normal: bpy.types.Image,
    img_orm: bpy.types.Image,
) -> bpy.types.Material:
    """Create a clean glTF-ready Principled BSDF material with BaseColor, Normal, and packed ORM."""
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (620, 0)

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (260, 0)
    bsdf.inputs["IOR"].default_value = 1.48
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    # BaseColor
    tex_base = nt.nodes.new("ShaderNodeTexImage")
    tex_base.image = img_base
    tex_base.location = (-360, 260)
    nt.links.new(tex_base.outputs["Color"], bsdf.inputs["Base Color"])

    # Packed ORM (R=AO, G=Roughness, B=Metallic)
    tex_orm = nt.nodes.new("ShaderNodeTexImage")
    tex_orm.image = img_orm
    tex_orm.location = (-440, -40)

    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-120, -40)
    nt.links.new(tex_orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])

    gltf_ng = ensure_gltf_output_node_group()
    gltf_out = nt.nodes.new("ShaderNodeGroup")
    gltf_out.node_tree = gltf_ng
    gltf_out.location = (260, -240)
    nt.links.new(sep.outputs["Red"], gltf_out.inputs["Occlusion"])

    # Normal Map
    tex_norm = nt.nodes.new("ShaderNodeTexImage")
    tex_norm.image = img_normal
    tex_norm.location = (-440, -360)

    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.location = (-80, -340)
    nmap.inputs["Strength"].default_value = 1.0
    nt.links.new(tex_norm.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def bake_pbr_atlas(
    atlas_name: str,
    objects: Sequence[bpy.types.Object],
    resolution: int = 1024,
    uv_layer: str = "BakeUV",
    samples_emit: int = 4,
    samples_normal: int = 4,
    samples_ao: int = 12,
    ao_distance: float = 2.4,
    island_margin: float = 0.008,
    texture_dir: Optional[str] = None,
    ao_occluders_hide: Sequence[bpy.types.Object] = (),
) -> Optional[bpy.types.Material]:
    """Bake BaseColor, Normal, and packed ORM atlas for `objects` and assign baked material."""
    if not objects:
        return None
    convert_curves_to_meshes(objects)
    apply_non_armature_modifiers(objects)

    rep_objs = dedupe_by_mesh_data(objects)
    if not rep_objs:
        return None
    for obj in rep_objs:
        _ensure_solid_object_materials(obj)

    orig_uv_map = prepare_atlas_uvs(rep_objs, uv_layer_name=uv_layer, island_margin=island_margin)

    # Gather original materials and clone them cleanly so procedural source materials stay untouched.
    orig_to_temp: Dict[bpy.types.Material, bpy.types.Material] = {}
    orig_slots_per_mesh: Dict[bpy.types.Mesh, List[Optional[bpy.types.Material]]] = {}
    first_orig_uv = next((u for u in orig_uv_map.values() if u and u != uv_layer), None)

    for obj in rep_objs:
        mesh = obj.data
        slots = list(mesh.materials)
        orig_slots_per_mesh[mesh] = slots
        for idx, mat in enumerate(slots):
            if mat is None:
                continue
            if mat not in orig_to_temp:
                clone = mat.copy()
                clone.name = f"__TempBake_{atlas_name}_{mat.name}"
                orig_to_temp[mat] = clone
            mesh.materials[idx] = orig_to_temp[mat]

    temp_mats = list(orig_to_temp.values())
    # Clamp heavy raytraced AO nodes inside procedural shaders during BaseColor EMIT bake
    # (dedicated ORM AO pass handles crisp macro occlusion cleanly at full speed).
    for tm in temp_mats:
        if tm and tm.use_nodes and tm.node_tree:
            for node in tm.node_tree.nodes:
                if node.bl_idname == "ShaderNodeAmbientOcclusion":
                    node.samples = min(getattr(node, "samples", 4), 2)
    _pin_existing_uv_sources(temp_mats, first_orig_uv)
    targets = _create_target_tex_nodes(temp_mats)

    scene = bpy.context.scene
    prev_engine = scene.render.engine
    prev_device = scene.cycles.device
    prev_samples = scene.cycles.samples
    prev_adaptive = scene.cycles.use_adaptive_sampling
    prev_denoise = scene.cycles.use_denoising
    prev_vt = scene.view_settings.view_transform
    prev_look = scene.view_settings.look
    prev_exp = scene.view_settings.exposure
    created_world = None
    if scene.world is None:
        created_world = bpy.data.worlds.new("__BakeTempWorld__")
        scene.world = created_world
    prev_ao_dist = scene.world.light_settings.distance

    margin = max(6, min(24, resolution // 96))
    save_dir = texture_dir or os.path.join(tempfile.gettempdir(), "echoes_bake", atlas_name)

    img_base = bpy.data.images.new(f"{atlas_name}_BaseColor", width=resolution, height=resolution, alpha=False, float_buffer=False)
    img_base.colorspace_settings.name = "sRGB"
    img_norm = bpy.data.images.new(f"{atlas_name}_Normal", width=resolution, height=resolution, alpha=False, float_buffer=False)
    img_norm.colorspace_settings.name = "Non-Color"
    img_ao_tmp = bpy.data.images.new(f"__{atlas_name}_AO_Tmp", width=resolution, height=resolution, alpha=True, float_buffer=True)
    img_ao_tmp.colorspace_settings.name = "Non-Color"
    img_rough_tmp = bpy.data.images.new(f"__{atlas_name}_Rough_Tmp", width=resolution, height=resolution, alpha=True, float_buffer=True)
    img_rough_tmp.colorspace_settings.name = "Non-Color"
    img_metal_tmp = bpy.data.images.new(f"__{atlas_name}_Metal_Tmp", width=resolution, height=resolution, alpha=True, float_buffer=True)
    img_metal_tmp.colorspace_settings.name = "Non-Color"
    img_orm = bpy.data.images.new(f"{atlas_name}_ORM", width=resolution, height=resolution, alpha=False, float_buffer=False)
    img_orm.colorspace_settings.name = "Non-Color"

    try:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.use_denoising = False

        # Ensure all representative objects are selectable & renderable.
        bpy.ops.object.select_all(action="DESELECT")
        prev_hide: List[Tuple[bpy.types.Object, bool, bool]] = []
        for obj in rep_objs:
            prev_hide.append((obj, obj.hide_viewport, obj.hide_render))
            obj.hide_viewport = False
            obj.hide_set(False)
            obj.hide_render = False
            obj.select_set(True)
        bpy.context.view_layer.objects.active = rep_objs[0]

        print(f"[pbr_bake:{atlas_name}] 1/5 Baking NORMAL ({resolution}px)...", flush=True)
        # 1. Tangent-Space Normal Map (captures geometry + procedural Bump nodes)
        scene.cycles.samples = samples_normal
        _set_target_image(targets, img_norm)
        bpy.ops.object.bake(
            type="NORMAL",
            normal_space="TANGENT",
            uv_layer=uv_layer,
            margin=margin,
            margin_type="EXTEND",
            use_clear=True,
        )

        print(f"[pbr_bake:{atlas_name}] 2/5 Baking AO ({resolution}px)...", flush=True)
        # 2. Ambient Occlusion (hide fog/water helpers temporarily so submerged areas keep crevices)
        ao_hidden: List[Tuple[bpy.types.Object, bool]] = []
        for h_obj in ao_occluders_hide:
            if h_obj.name in bpy.data.objects:
                ao_hidden.append((h_obj, h_obj.hide_render))
                h_obj.hide_render = True
        try:
            scene.world.light_settings.distance = ao_distance
            scene.cycles.samples = samples_ao
            _set_target_image(targets, img_ao_tmp)
            bpy.ops.object.bake(
                type="AO",
                uv_layer=uv_layer,
                margin=margin,
                margin_type="EXTEND",
                use_clear=True,
            )
        finally:
            for h_obj, was_hidden in ao_hidden:
                h_obj.hide_render = was_hidden

        # 3. Raw Emit Bakes (Base Color, Roughness, Metallic)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0.0
        scene.cycles.samples = samples_emit

        print(f"[pbr_bake:{atlas_name}] 3/5 Baking BaseColor/Roughness/Metallic...", flush=True)
        _run_emit_pass(temp_mats, targets, "Base Color", img_base, uv_layer, margin, 0.5)
        _run_emit_pass(temp_mats, targets, "Roughness", img_rough_tmp, uv_layer, margin, 0.65)
        _run_emit_pass(temp_mats, targets, "Metallic", img_metal_tmp, uv_layer, margin, 0.0)

        print(f"[pbr_bake:{atlas_name}] 4/5 Packing ORM...", flush=True)
        # 4. Pack ORM (R=AO, G=Roughness, B=Metallic) using numpy
        n_px = resolution * resolution
        ao_arr = _read_image_pixels_np(img_ao_tmp)
        rough_arr = _read_image_pixels_np(img_rough_tmp)
        metal_arr = _read_image_pixels_np(img_metal_tmp)

        empty_mask = ao_arr[:, 3] < 0.01
        ao_ch = np.where(empty_mask, 1.0, ao_arr[:, 0])
        rough_ch = np.where(empty_mask, 0.65, rough_arr[:, 0])
        metal_ch = np.where(empty_mask, 0.0, metal_arr[:, 0])

        orm_arr = np.empty((n_px, 4), dtype=np.float32)
        orm_arr[:, 0] = np.clip(ao_ch, 0.0, 1.0)
        orm_arr[:, 1] = np.clip(rough_ch, 0.0, 1.0)
        orm_arr[:, 2] = np.clip(metal_ch, 0.0, 1.0)
        orm_arr[:, 3] = 1.0
        img_orm.pixels.foreach_set(orm_arr.ravel())
        img_orm.update()

        print(f"[pbr_bake:{atlas_name}] 5/5 Saving & packing PNGs...", flush=True)
        _save_and_pack_png(img_base, os.path.join(save_dir, f"{atlas_name}_BaseColor.png"))
        _save_and_pack_png(img_norm, os.path.join(save_dir, f"{atlas_name}_Normal.png"))
        _save_and_pack_png(img_orm, os.path.join(save_dir, f"{atlas_name}_ORM.png"))

        # 5. Clean UV layers down to single TEXCOORD_0 ("UVMap") and assign consolidated baked material.
        for obj in rep_objs:
            mesh = obj.data
            for uv in list(mesh.uv_layers):
                if uv.name != uv_layer:
                    mesh.uv_layers.remove(uv)
            if uv_layer in mesh.uv_layers:
                mesh.uv_layers[uv_layer].name = "UVMap"
                mesh.uv_layers["UVMap"].active = True
                mesh.uv_layers["UVMap"].active_render = True

        baked_mat = build_baked_orm_material(
            f"MAT_Baked_{atlas_name}", img_base, img_norm, img_orm
        )
        for obj in rep_objs:
            obj.data.materials.clear()
            obj.data.materials.append(baked_mat)

        return baked_mat
    finally:
        for obj, hv, hr in locals().get("prev_hide", []):
            obj.hide_viewport = hv
            obj.hide_render = hr
        for img in (img_ao_tmp, img_rough_tmp, img_metal_tmp):
            if img.name in bpy.data.images:
                bpy.data.images.remove(img)
        for mat in temp_mats:
            if mat.users == 0:
                bpy.data.materials.remove(mat)
        scene.render.engine = prev_engine
        scene.cycles.device = prev_device
        scene.cycles.samples = prev_samples
        scene.cycles.use_adaptive_sampling = prev_adaptive
        scene.cycles.use_denoising = prev_denoise
        scene.view_settings.view_transform = prev_vt
        scene.view_settings.look = prev_look
        scene.view_settings.exposure = prev_exp
        if created_world is not None:
            scene.world = None
            bpy.data.worlds.remove(created_world)
        elif scene.world:
            scene.world.light_settings.distance = prev_ao_dist
