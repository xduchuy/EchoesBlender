# The Rootbound Saint (V3) — World & WebGL Integration Guide

- **Branch**: `feat/rootbound-saint-v3`
- **Target World**: `EchoesBlender` — The Drowned Sanctuary
- **Primary Reference**: [`references/rootbound_saint_reference.png`](../references/rootbound_saint_reference.png)

---

## 1. Blender Asset & Scene Pipeline

1. **Modular Hero Monument Generator (`scripts/rootbound_saint.py`)**
   - Builds the circular flooded Gothic sanctuary terrace (`Terrace_*`), twin radial stairs (`Stairs_*`), curved Gothic balustrades, central blind-arcaded octagonal pedestal (`Pedestal_*`), shrouded Saint sculpture (`Saint_*`, Gothic halo, hooded crown dome, carved face/chin shadow, folded praying hands, draped stone robe), ancient multi-tier roots (`Root_Primary`, `Root_Secondary`, `Root_Tendrils` extruded with continuous parallel transport), scattered broken slabs/parapets/rubble, terrace water surface, and simplified collision volumes (`Collision_Terrace`, `Collision_Stairs`, `Collision_Pedestal`).
   - Built-in validator `validate_rootbound_saint()` checks presence of all required mesh objects, material assignment, legacy central statue removal (`legacy_statue_present: False`), bounding extents, and vertex/polygon budget (`46,272` vertices, `47,185` polygons, `bbox_min_z: -0.856`, `bbox_max_z: 15.933`, `max_radius_m: 10.381`).
   - Standalone source blend & isolated GLB output:
     - `output/rootbound_saint/rootbound_saint_source.blend` (`1,237,363` bytes)
     - `output/rootbound_saint/rootbound_saint.glb` (`1,806,104` bytes, Draco + `1536px` `Sanctuary_RootboundSaint` PBR atlas)

2. **Sanctuary Scene Integration (`scripts/config.py`, `scripts/terrain.py`, `scripts/build_scene.py`)**
   - `scripts/config.py` sets `MONUMENT_MODE = "ROOTBOUND_SAINT"`, extends `LAYOUT["causeway"]["end_xy"]` to `(0.0, -5.65)` when in `ROOTBOUND_SAINT` mode, and registers `CAM_ROOTBOUND_*` verification cameras.
   - `scripts/terrain.py` updates `build_courtyard_and_causeway` to skip the legacy statue island, keep outer courtyard flagstones at `r >= 8.55`, and slope the extended causeway bridge cleanly to `0.16 m` at the terrace entry (`y = -5.65`); `build_flooded_rubble_and_reeds` clears reeds inside `r < 8.6` and along the extended causeway path.
   - `scripts/build_scene.py` switches step 4/9 on `LAYOUT.get("monument_mode", "ROOTBOUND_SAINT")` to run `build_rootbound_saint` and `validate_rootbound_saint()`, saving `output/drowned_sanctuary_v2.blend` (`4,370,936` bytes).

3. **PBR Atlas Baking & glTF Export (`scripts/export_glb.py`)**
   - Adds `_simplify_collision_for_gltf()` so `Collision_*` meshes export cleanly as lightweight hidden collision proxies without occupying bake UV space (`ao_occluders_hide` excludes collision proxies from shadow/AO baking).
   - `_collect_atlas_groups()` packs the monumental complex into a dedicated `2048x2048` PBR atlas `("Sanctuary_RootboundSaint", 2048, rootbound_objs, 2.0)` (`ao_samples = 6`) alongside `Sanctuary_HeroArch`, `Sanctuary_Cliffs`, `Sanctuary_RootsRubble`, and `Sanctuary_SecondaryTrim`.
   - Produces [`public/models/drowned_sanctuary.glb`](../public/models/drowned_sanctuary.glb) (`7,376,004` bytes, `8` materials, `15` `image/webp` textures, `67` meshes / `67` primitives, Draco compressed).

---

## 2. Three.js Viewer & Knight Navigation (`src/scene/`)

- **Camera Preset (`src/scene/config.js`)**:
  - Updated `CAMERA_PRESETS.statue` to `position: [3.5, 17.8, 25.8]`, `target: [0.0, 7.4, -2.0]`, `fov: 36` to frame the monumental statue, halo ring, terrace balustrades, and Gothic rear arches cleanly.
- **Hidden Collision & PBR Material Tuning (`src/scene/materials.js`)**:
  - Forces `Collision_*` meshes to `visible = false`, `castShadow = false`, and `receiveShadow = false`.
  - Sets `envMapIntensity = 0.68` on `RootboundSaint` baked materials to prevent over-bright specular washout against overcast sanctuary fog.
- **Walkability & Obstacle Binding (`src/scene/KnightCharacter.js`)**:
  - Binds hidden `Collision_Terrace` and `Collision_Stairs` as walkable `groundMeshes`.
  - Binds `Collision_Pedestal`, `Terrace_OuterWall`, and `Terrace_Balustrades` to `solidMeshes` for accurate player blocking.
  - Excludes detailed decorative meshes (`Saint_*`, `Root_*`, `Pedestal_*`, `Stairs_*`, `Terrace_Floor`, `Rubble`, `Broken_Stone`, `Fallen_Parapets`) from raycast `groundMeshes` to keep stepping smooth across complex stonework and draped roots.

---

## 3. Reproducible CLI Commands

```powershell
# 1. Build integrated Blender 5.3 scene & render hero verification frame
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" --background --python scripts/build_scene.py -- --quality review --camera CAM_HERO_REFERENCE --output-blend output/drowned_sanctuary_v2.blend --output-render renders/rootbound_saint/integrated_sanctuary.png

# 2. Bake PBR atlases & export Draco + WebP Sanctuary GLB
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" --background output/drowned_sanctuary_v2.blend --python scripts/export_glb.py -- --output public/models/drowned_sanctuary.glb --max-subdiv 1

# 3. Verify tests & production web build
npm test
npm run build
```
