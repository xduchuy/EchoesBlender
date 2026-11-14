# RECONSTRUCTION REPORT — THE FORGOTTEN KNIGHT

## 1. Visual Reference Breakdown (`references/forgotten_knight.png`)

Target reference: side-by-side dark-fantasy knight concept sheet (`1024 x 572 px`), **Left = Front 3/4 view**, **Right = Rear 3/4 view**.

- **Proportion & Stance**: Tall grounded medieval warrior (`1.8608 m` reconstructed height from `Armor_Boot_L/R` soles at `Z = 0.000` to `Helm_Skull` crown), slightly asymmetrical weight distribution, right arm extended down-outward resting the longsword tip onto the pedestal floor, left arm relaxed near waist/lantern.
- **Silhouette Signature**:
  - Pointed closed medieval helmet with center ridge crest, horizontal brow overhang, riveted rim, dark vertical breathing slats, and pitch-black inner eye void (`MAT_Helm_Void`).
  - Strongly asymmetrical shoulders: prominent left gothic pauldron (`Armor_Pauldron_L`) with upturned neck lip, aged brass border trim (`Armor_Pauldron_Rim_L`), and 4 articulated shoulder lames (`Armor_ShoulderLames_L`); right shoulder draped under a thick folded tattered pine-green scarf apron (`Hood_Scarf_Drape`) with articulated steel shoulder lames emerging beneath.
  - Globose dark steel cuirass (`Armor_Cuirass`), thin cross emblem (`Armor_Chest_Heraldry`), double waist leather belts (`Belts_Waist_Assembly`), center buckle, utility pouches, hip iron loop, split pleated ragged front tabard (`Tabard_Front_R/L`) carrying a weathered shield/rampant-beast crest decal (`tex_tabard_crest.png`) on the lower left panel.
  - Steel fluted shin greaves (`Armor_Greave_Front_L/R`) with brass knee bands (`Armor_Greave_Trim_L/R`) in front; dark leather rear calf sleeves (`Armor_Greave_Leather_L/R`) strapped by twin brown bands (`Armor_Calf_Straps_L/R`) in rear view; laminar sabaton toe/instep plates on flat-soled boots (`Z = 0.0`).
  - Diagonal wrapped leather/brass scabbard & hilt mounted across the back (`SWORD_BACK`), cleanly resting over the heavy folded, torn, and punctured back cloak (`Cape_Back_Cloak`).
  - Compact brass cage hip lantern (`14_LANTERN`) suspended clear of the back scabbard tip with a warm muted amber inner wick (`Light_Lantern_Wick` `0.35W`).
  - Stepped circular cracked stone pedestal (`Pedestal_Stone_Base`, `radius_top = 0.80 m`, `radius_rim_outer = 0.88 m`, `radius_base = 0.96 m`, `height = 0.44 m`) with flat-surface rainwater puddles (`Normal.Z > 0.88`), olive moss tufts (`Pedestal_Moss_Tufts`), and organic climbing roots (`Pedestal_Creeping_Roots`) draping across the curb rim.

## 2. Final Verified Metrics (`output/build_stats.json`)

Executed cleanly in Blender 5.3.0 (`--quality final --closeups`):

- **Quality / Detail Preset**: `final` / `HIGH` (`radial_segs=26`, `cloth_subdiv=3`, `chainmail_rings_per_zone=540`, `pedestal_segs=96`, `root_count=26`)
- **Total Build + Export + Render Time**: `2490.9s` (~41.5 minutes on 12-thread CPU Cycles)
- **Evaluated Character Height**: `1.8608 m` (`boot_l_min_z = -0.0`, `boot_r_min_z = -0.0`, `sword_tip_z = 0.0039 m`, `pedestal_top_z = 0.0404 m`)
- **Evaluated Geometry**: `75,868` vertices, `76,054` polygons (including 3D chainmail torus rings & solidified cloth/plate layers)
- **Scene Hygiene**: `0` missing collections (all 19 collections `00_REFERENCE`..`18_PRESENTATION` present), `0` missing primary materials (all 14 PBR materials present), `0` unshaded renderable meshes, `0` validation warnings, `passed: true`.
- **Rigging**: `Rig_ForgottenKnight` with `30` bones, `60` rigid single-bone bound meshes, and `16` smooth inverse-distance deform bound meshes.
- **Exports**:
  - `output/forgotten_knight.blend`: `4,557,568` bytes (with `tex_tabard_crest.png` packed)
  - `output/forgotten_knight.glb`: `2,091,904` bytes (~1.99 MiB, Draco mesh compression enabled, skinned armature)
- **Renders** (Cycles CPU, `256` max adaptive samples, `adaptive_threshold=0.015`, `OPENIMAGEDENOISE`, `AgX - Medium High Contrast`):
  - `renders/character_sheet.png`: `2560 x 1440` (`4,306,649` bytes)
  - `renders/front_view.png`: `1280 x 1440` (`2,212,306` bytes)
  - `renders/back_view.png`: `1280 x 1440` (`2,148,134` bytes)
  - `renders/helmet_closeup.png`: `1200 x 1200` (`1,858,908` bytes)
  - `renders/equipment_closeup.png`: `1200 x 1200` (`1,848,348` bytes)
  - `renders/preview.png`: `960 x 540` (`667,741` bytes, `MEDIUM` preview pass)

## 3. Iterative Improvements Completed Across Visual Passes

1. **Leg Plate Orientation Fix**: Fixed right-handed frame axes inside `_orient_from_segment` (`armor_generator.py`) so steel front greaves, brass knee trims, and thigh cuisses orient cleanly forward (`-Y`) while rear calf leather sleeves and horizontal brown straps face back (`+Y`).
2. **Hero Pauldron & Helmet Hood Transitions**: Re-curved `Armor_Pauldron_L` closer inward/downward over `Armor_ShoulderLames_L` to remove flat shelf overhang, recessed `Hood_Rear_Cowl` cleanly behind `Helm_Skull` nape to avoid skull clipping, and bridged `Cape_Back_Cloak` smoothly up beneath the cowl collar.
3. **Pedestal Surface, Puddles & Roots**: Restricted puddle gloss (`Roughness=0.08`) strictly via `Normal.Z > 0.88`, added Voronoi fracture slab lines + broader cool zenith sky light (`Light_Pedestal_Sheen`) for misty reflections instead of black blobs, and anchored `Pedestal_Creeping_Roots` along `_pedestal_surface_z(r)` so roots hug the outer curb lip instead of protruding radially.
4. **Backdrop & Silhouette Separation**: Separated `LANTERN_ANCHOR` and `SWORD_BACK["scabbard_tip"]` cleanly in front 3/4 view, and removed hard vertical background monolith edges so both studio angles sit in consistent dark slate-teal atmosphere.

## 4. Honest Limitations & Approximations Remaining

- **Close-Up Micro-Intersections**: In tight `1200x1200` close-up renders (`helmet_closeup.png` & `equipment_closeup.png`), two minor overlaps remain visible up close: a sliver of the brown `Knight_UnderBody` shoulder pad shows in the deep armpit gap under the left/right collar joints, `Armor_Chest_Heraldry` partially tucks under the right edge of `Hood_Scarf_Drape`, and two cape fold ridges graze through `Weapon_Back_Scabbard` midway down the back. At full character framing (`character_sheet.png`), these read naturally within shadowed folds, though further cloth-to-scabbard shrinkwrap clearance and deeper underbody inset at the collarbone would polish macro close-ups further.
- **Procedural vs Sculpted Concept Micro-Damage**: Battle dents, rust streaks, textile weave, and masonry cracks are generated procedurally via Blender noise/Voronoi/AO/pointiness shader nodes rather than baked high-poly ZBrush sculpt displacement maps or hand-painted 4K UDIM albedo/roughness maps.
- **Heraldry Emblem Fidelity**: The shield & rampant-beast emblem on `Tabard_Front_L` (`tex_tabard_crest.png`, `256x256`) is procedurally rasterized in Python rather than high-resolution hand-illustrated heraldry.
- **Blender vs Real-Time `.glb` Parity**: Cycles procedural shader networks (`ShaderNodeAmbientOcclusion`, `ShaderNodeNewGeometry.Pointiness`, procedural bump mixes) do not translate 1:1 to standard glTF 2.0 PBR textures without explicit texture baking; therefore `forgotten_knight.glb` carries clean metallic/roughness material assignments and packed UV decals, whereas maximum surface grime and puddle richness appear inside `forgotten_knight.blend` and the Cycles renders.
- **Armature Scope**: `Rig_ForgottenKnight` is built for clean posing and engine export without advanced IK/FK pole-target control widgets or automated cloth physics simulation.
