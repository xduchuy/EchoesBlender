# EchoesBlender V2 — Quality Verification Report

- **Branch**: `feat/visual-quality-v2`
- **Audit Baseline**: [`docs/QUALITY_AUDIT.md`](./QUALITY_AUDIT.md)
- **Verification Date**: 2026-11-14
- **Automated Tests**: `npm test` (`5/5` passing via `tests/verify_v2.mjs`)
- **Production Build**: `npm run build` (`vite build` succeeded in `4.25s`, `29` modules)

---

## 1. Asset & Export Comparison (V1 Baseline vs V2)

| Asset / Artifact | Baseline V1 | Upgraded V2 | Verification Result |
|---|---|---|---|
| `public/models/drowned_sanctuary.glb` | `4,295,748` bytes (`4.10 MB`), vertex colors only, no UV textures | `5,977,152` bytes (`5.70 MB`), Draco, `148` nodes, `44` meshes / `44` primitives, `15` WebP textures across `5` PBR baked materials + `MAT_Water_Dark` + `MAT_Dark_Silhouette` | Passed GLB schema & `tests/verify_v2.mjs` |
| `public/models/forgotten_knight.glb` | `2,091,904` bytes (`1.99 MB`), `0` animation clips, single decal PNG | `2,696,808` bytes (`2.57 MB`), Draco, `12` WebP images across `4` PBR baked atlases + lookdev materials (`MAT_Helm_Void`, `MAT_Glass_Lantern`, `MAT_Lantern_Flame`), `1` skin (`Rig_ForgottenKnight`, `30` bones), `9` NLA animations | Passed GLB schema, bone/clip checks, & edge deformation check across all `9` clips |
| Editable Blender `.blend` files | `output/drowned_sanctuary.blend` (`3,201,802` bytes), `forgotten_knight/output/forgotten_knight.blend` (`4,557,568` bytes) | Preserved untouched alongside `output/drowned_sanctuary_v2.blend` (`3,592,209` bytes) and `forgotten_knight/output/forgotten_knight_v2.blend` (`3,183,378` bytes) | Non-destructive procedural trees preserved |
| Compare Modal Cycles Hero Render | `renders/baseline/drowned_sanctuary_final.png` | `renders/v2/drowned_sanctuary_hero_v2.png` synced to `public/images/drowned_sanctuary_final.png` | Visually verified in Compare modal (`551x309.9px`) |

---

## 2. Visual & Geometry Upgrades Completed

### A. The Drowned Sanctuary (`scripts/`)
- **Gothic Masonry & Silhouette (`S-03`, `S-04`, `S-05`, `S-06`)**: Replaced sealed solid tower cornices with hollow 4-sided perimeter molding frames (`gothic_architecture.py`), added continuous anchored lancet sub-arch tracery, weathered sloped buttress caps, and fixed post-bevel vertex tracking in `add_box_to_bmesh` (`geometry_utils.py`) so edge chipping and stone courses apply cleanly.
- **Cliffs, Causeway, Statue & Roots (`S-01`, `S-02`, `S-07`, `S-08`)**: Upgraded stratified bedrock cliffs and bedded foreground outcrops (`terrain.py`), rebuilt multi-tiered statue drapery/pedestal detail (`statue.py`), and anchored root splines to ruins/cliffs with organic taper (`roots.py`).
- **Cycles PBR Atlas Baking (`M-01`, `M-02`)**: Added `scripts/pbr_bake.py` and upgraded `scripts/export_glb.py` so `MAT_Baked_Sanctuary_HeroArch`, `MAT_Baked_Sanctuary_Statue`, `MAT_Baked_Sanctuary_Cliffs`, `MAT_Baked_Sanctuary_RootsRubble`, and `MAT_Baked_Sanctuary_SecondaryTrim` export BaseColor, ORM (Occlusion/Roughness/Metallic), and tangent Normal WebP atlases.

### B. The Forgotten Knight (`forgotten_knight/scripts/`)
- **Armor, Heraldry, Hood & Scabbard Clearance (`K-01`..`K-05`)**:
  - Seated `Armor_Pauldron_L` with skirt flare (`skirt_flare`) to clear underlying shoulder lames (`armor_generator.py`).
  - Brought tarnished brass `Armor_Chest_Heraldry` cross pattee forward cleanly out of `Armor_Cuirass` solidification (`armor_generator.py`).
  - Removed unintended rectangular gap in `Hood_Rear_Cowl` (`cloth_generator.py`) and routed `SWORD_BACK` (`config.py`) plus `Belts_Chest_Baldric` (`equipment_generator.py`) cleanly outside the folded cloak.
  - Verified zero stretched mesh edges (`<= 0.25 m` on all deforming cloth/armor parts; only rigid `Weapon_Back_Scabbard` at `0.438 m` and `Weapon_Longsword_Blade` at `0.305 m`) across all `9` exported actions (`Airborne`, `Idle`, `Jump_Start`, `Land`, `Run`, `Sword_Ready`, `Turn_Left`, `Turn_Right`, `Walk`) using Blender depsgraph evaluation.
- **Rigging, Animations & Baked Atlases (`K-06`, `M-01`)**: Exported `Rig_ForgottenKnight` (`30` bones, `61` rigid-bound + `16` deform-bound meshes, height `1.8606 m`) with `9` glTF NLA animation clips and `4` Cycles-baked WebP PBR atlases (`MAT_Baked_Knight_Pedestal`, `MAT_Baked_Knight_Leather_Gear`, `MAT_Baked_Knight_Armor_Steel`, `MAT_Baked_Knight_Cloth_Garments`).

### C. Three.js WebGL Viewer (`src/`)
- **Tone Mapping, Antialiasing & Lighting (`R-03`)**: Enabled `THREE.AgXToneMapping`, added `SMAAPass` for `High`/`Ultra` quality presets, and implemented dynamic directional shadow frustum switching (`[-18, 18]` tight Knight box vs `[-85, 85]` wide Sanctuary view in `SanctuaryViewer.js`).
- **Physical Water & Atmosphere (`R-01`, `R-02`)**: Upgraded `MAT_Water_Dark` (`materials.js`) with `MeshPhysicalMaterial` + 5-octave `sanctuaryWaveGrad`, shoreline shallow-depth tinting (`uDeepColor`, `uShallowColor`), and dynamic Knight wade ripple uniforms (`uKnightPos`, `uKnightWade`); added dark lower-hemisphere PMREM occlusion and preset-scaled wispy cloud/mist sprites and dust motes (`atmosphere.js`).
- **Playable Knight & Mobile UX**: Driven by `THREE.AnimationMixer` (`KnightCharacter.js`) supporting `W/A/S/D` movement, `Shift` sprint, `Space` jump, `E` Sword Stance (`Sword_Ready`), plus mobile virtual joystick and touch action buttons (`#mobile-controls` in `index.html`, `src/main.js`, `src/styles/main.css`).

---

## 3. Quantitative Visual Comparison (`scripts/compare_reference.py --suite v2`)

Generated boards:
- `renders/v2/comparison_sanctuary_v2.png`
- `forgotten_knight/renders/v2/comparison_knight_v2.png`

### The Drowned Sanctuary (`renders/v2/drowned_sanctuary_hero_v2.png` vs Baseline V1 & Reference)
| Metric | Baseline V1 vs Ref | Upgraded V2 vs Ref | Delta / Interpretation |
|---|---|---|---|
| Luma SSIM | `0.3320` | `0.3193` | Minor shift from richer stone relief/bounce luma |
| RMSE | `0.1721` | `0.1805` | V2 slightly brighter (`Mean Luma 0.3606` vs Ref `0.3377`) |
| PSNR (dB) | `15.29` | `14.87` | Compare direct V1->V2: `RMSE 0.0809`, `PSNR 21.84 dB`, `SSIM 0.7582` |
| Edge Cosine | `0.3332` | **`0.3406`** | Improved architectural silhouette/edge alignment |
| Luma StdDev | `0.2262` | **`0.2183`** | Closer contrast spread toward Ref (`0.1992`) |

### The Forgotten Knight (`forgotten_knight/renders/v2/character_sheet.png` vs Baseline V1 & Reference)
| Metric | Baseline V1 vs Ref | Upgraded V2 vs Ref | Delta / Interpretation |
|---|---|---|---|
| Luma SSIM | `0.2789` | **`0.2801`** | Structural similarity improved over V1 |
| RMSE | `0.1946` | **`0.1915`** | Lower error vs reference artwork |
| PSNR (dB) | `14.22` | **`14.35`** | Higher fidelity (`V1 -> V2 Direct RMSE 0.0692`, `SSIM 0.8274`) |
| Edge Cosine / IoU | `0.4063` / `0.2666` | `0.3918` / `0.2596` | Added cloth folds & flush brass heraldry geometry |
| Luma StdDev | `0.1489` | **`0.1417`** | Closer tonal balance toward Ref (`0.1132`) |

---

## 4. End-to-End QA Summary

- **Automated Suite (`npm test`)**: `5/5` tests passed (`87.4ms` standalone, `422.4ms` post-telemetry patch).
- **Live Browser QA (`http://localhost:4173/`, Vite Preview)**:
  - **Console Errors**: `0`
  - **Page Errors**: `0`
  - **Failed Network Requests**: `0`
  - **Desktop (`1280x720`)**: Verified all 5 camera presets (`Hero View`, `Knight`, `Architecture`, `Statue`, `Causeway`), 3 moods (`Afternoon`, `Moonlight`, `Dawn`), quality cycling (`#btn-quality`), Compare modal image loading, and Play Knight movement + Sword Stance (`KeyE`) + Leap (`Space`).
  - **Mobile (`390x844`)**: Verified `#mobile-controls` layout (`#touch-joystick` `116x116px` bottom-left, `#touch-btn-sword`/`#touch-btn-sprint`/`#touch-btn-jump` `72x38px` bottom-right) with clean touch usability during Play Knight mode.
