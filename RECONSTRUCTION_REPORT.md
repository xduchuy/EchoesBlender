# Reconstruction Report — The Drowned Sanctuary

## 1. Executive Summary
- **Project**: The Drowned Sanctuary (`output/drowned_sanctuary.blend`)
- **Blender Version**: `Blender 5.3.0` (hash `02f0899d78e3`)
- **Renderer & Hardware**: Cycles (`CPU`, `12th Gen Intel Core i7-1265U`) with `OpenImageDenoise` (`AgX` color management, `Exposure = -0.38`)
- **Deterministic Seed**: `SEED = 42`
- **Scene Statistics** (`output/drowned_sanctuary.blend`, `geom=high`):
  - Objects: `163` (`146` Meshes, `6` Curves, `1` Control Empty, `4` Tracked Cameras + `4` Target Empties, `2` Lights)
  - Materials: `17` data-block entries (`16` procedural PBR / Volume shaders + Blender default)
  - Base Geometry: `127,436` vertices, `126,997` polygons (plus non-destructive Subsurf / Curve bevel modifiers)
- **Hero Reference Render**: `renders/drowned_sanctuary_final.png` (`2560x1440`, `128` Cycles samples, adaptive threshold `0.02`, completed in `1320.9s` after a `6.9s` procedural build)
- **Visual Validation Sheet**: `renders/comparison_final.png` (`Reference`, `Blender Render`, `50/50 Silhouette Overlay`, `2.2x Tonal/Silhouette Difference`)

---

## 2. Camera & Composition Fidelity (`CAM_HERO_REFERENCE`)
- **Active Hero Camera**: `CAM_HERO_REFERENCE` at `(30.0, -104.0, 41.0)` tracking target `(-1.5, 6.5, 7.6)` with `lens = 33.5 mm`, `sensor_width = 36.0 mm`.
- **Foreground Diagonal Lead-In**: `Causeway_Stone_Bridge` runs diagonally from lower-left `(0.0, -78.0)` across the dark water to the circular courtyard entrance `(0.0, -11.4)`, with broken slab gaps and `Causeway_Scale_Figure` standing near `Y = -42.5` for monumental scale.
- **Framing & Depth Layers**:
  - Foreground left (`X < 0`) is anchored by `Cliff_Left_Foreground`, `Cliffs_Foreground_Outcrops`, `Ruin_Shore_Shrine_1..2`, and `Ruin_Submerged_Slab_*`.
  - Foreground right (`X > 0`) is framed by the darker shadowed `Cliff_Right_Foreground` slope and fallen/submerged slabs and columns.
  - Midground holds the asymmetrical four-tower ruined complex (`LeftFront`, `LeftRear`, `RightRear`, `RightFront`), outer stepped left wall (`ARCH_ConnectingWalls`), rear semicircular arcade (`ARCH_RearArcade`), and central robed statue island (`05_STATUE`).
  - Background horizon features the distant misty spire (`45.0, 150.0, -2.0`), distant left mountain range pushed cleanly left of `LeftRear` so an open hazy bay remains behind the central arcade, and calm horizon water fading into bright aerial haze.

---

## 3. Architectural Fidelity (`03_ARCHITECTURE`, `04_COURTYARD`, `05_STATUE`)
- **Four Primary Tower Groups**:
  - `ARCH_LeftFront` (`(-21.0, -2.5, -2.0)`), `ARCH_LeftRear` (`(-14.5, 22.0, -2.0)`), `ARCH_RightRear` (`(11.2, 22.5, -2.0)`), and `ARCH_RightFront` (`(26.5, -9.5, -2.0)`) are constructed procedurally from parametric piers, corner buttresses, stringcourses/cornices, two-centered pointed Gothic arch openings (`gothic_arch_points`), recessed lancet tracery, ashlar stone courses, and jagged collapsed battlements (`gothic_architecture.py`).
  - True architectural apertures and interior wall thicknesses allow sunlight, background water, and mist to pass through upper belfries and lower nave arches.
- **Rear Semicircular Arcade & Connecting Walls**:
  - `ARCH_RearArcade` spans `146°` to `34°` across `6` pointed Gothic arch bays centered at `(0.0, 12.5, -2.0)` (`radius = 16.0 m`), enclosing the central statue courtyard without creating an intact palace roof.
  - `ARCH_ConnectingWalls` adds the lower-left stepped arcade wall extending toward the left cliff bastion (`(-51.0, 9.5, -1.0)`).
- **Central Monumental Statue (`05_STATUE`)**:
  - Centered at `(0.0, 2.0, 0.0)` rotated `-16°` around Z on a stepped stone pedestal (`pedestal_height = 4.0 m`) above the octagonal/circular courtyard island (`island_radius = 4.2 m`).
  - Sculpted procedurally (`statue.py`) with vertically pleated drapery folds, folded arms/hands, shoulder mantle, hooded cowl, and facial planes catching warm golden sidelight on the right and cool shadow on the left.

---

## 4. Material, Terrain, Root & Water Quality
- **Procedural PBR Materials (`materials.py`)**: All materials (`MAT_Limestone_Base`, `MAT_Limestone_Light`, `MAT_Limestone_Wet`, `MAT_Limestone_Eroded`, `MAT_Limestone_Moss`, `MAT_Rock_Cliff`, `MAT_Rock_Dark`, `MAT_Bark_Ancient`, `MAT_Water_Dark`, `MAT_Statue_Weathered`, `MAT_Submerged_Stone`, etc.) are procedural shader networks requiring zero external image textures.
- **Stratified Cliffs (`02_CLIFFS`)**: `MAT_Rock_Cliff` uses dual anisotropic noise + horizontal bedding strata + slope-driven moss blending, avoiding cellular Voronoi artifacts on the main cliff faces in the final render.
- **Ancient Root Systems (`07_ROOTS`)**: `6` non-destructive NURBS/Bezier Curve objects with tapered bevel radii wrap around `LeftFront`, the left/right arcade joints, and `RightFront`, including hanging aerial tendrils over the courtyard.
- **Flooded Basin Water (`06_WATER`)**: Set at `Z = 0.0` with deep green-black base albedo `(0.004, 0.012, 0.011, 1.0)`, controlled specular IOR (`0.24`), and gentle multi-scale normal ripples producing crisp dark silhouettes and elongated reflections of the statue and towers.

---

## 5. Lighting & Volumetric Atmosphere (`10_ATMOSPHERE`, `11_LIGHTING`, `12_CAMERAS`)
- **Sky & Directional Lighting**:
  - Blender 5.3 procedural `MULTIPLE_SCATTERING` sky (`sky_strength = 0.24`, `air_density = 1.15`, `aerosol_density = 2.0`, `ozone_density = 1.15`) mixed with subtle cool-left to warm-right ambient balance.
  - `SUN_Key_LateAfternoon` (`elevation = 21.5°`, `azimuth = 84.0°`, `energy = 24.0`, `angle = 3.2°`, `sun_color = (1.0, 0.80, 0.52)`) creates warm sunlit highlights across the right-facing stone faces and causeway edges, balanced against `AREA_CoolSky_Fill` and cool shadowed recesses.
- **Multi-Layer Volumetrics**:
  - `4` wireframe volumetric domains (`visible_shadow = False` to prevent infinite sun occlusion) provide right-channel mist (`0.024`), courtyard haze (`0.016`), left-channel fog, and distant horizon aerial perspective (`0.0068`).
- **Compositor**: Built on Blender 5.3 `scene.compositing_node_group` (`Fog Glow` glare + subtle split-tone `ColorBalance`).

---

## 6. Iterative Passes & Observed Render Benchmarks
1. **Pass 1–5 Visual Refinements**:
   - Disabled shadow casting on fog bounding boxes (`visible_shadow = False`) so sun rays reached foreground ruins cleanly.
   - Calibrated `SUN_Key_LateAfternoon` (`energy = 24.0`) against `MULTIPLE_SCATTERING` sky luminance + `AgX` `exposure = -0.38`.
   - Darkened `MAT_Water_Dark` (`Transmission Weight = 0.0`, `Specular IOR Level = 0.24`) so water stayed dark green-black rather than mirror-silver.
   - Added pleated drapery & facial plane definition on `05_STATUE`, fixed `bmesh.ops.create_icosphere` normals (`bm.normal_update()`), and shifted `Mountains_Distant_Left` to keep the bay behind the rear arcade open.
   - Pass 6 replaced `Voronoi DISTANCE_TO_EDGE` with anisotropic bedding noise on `MAT_Rock_Cliff`, eliminating circular rock patterns seen in earlier previews.
2. **Observed Render Benchmarks (Verified on `12th Gen Intel Core i7-1265U` CPU)**:
   - `preview` (`960x540`, `48` samples, `geom=fast`): build `6.7s`, render `46.3s` -> `renders/preview.png`.
   - `final` (`2560x1440`, `128` samples, `geom=high`): build `6.9s`, render `1320.9s` (~22m 01s) -> `renders/drowned_sanctuary_final.png`.

---

## 7. Honest Comparison vs. Reference & Known Limitations
Comparing `renders/drowned_sanctuary_final.png` and `renders/comparison_final.png` directly against `references/sanctuary_reference.png`:
- **Strengths**:
  - Primary tower skyline proportions, diagonal causeway + scale silhouette, circular flooded courtyard, central statue placement, curved rear arcade, distant right spire, golden/cool lighting direction, and open hazy bay behind the arcade match the reference framing closely (`50/50 Silhouette Overlay`).
- **Known Limitations**:
  1. **Foreground Left Outcrop Faceting**: `Cliffs_Foreground_Outcrops` in the extreme lower-left corner show visible polygonal faceting (`icosphere` displacement) compared to photographic fractured cliff rocks in the reference.
  2. **Volumetric Mist Uniformity**: Procedural shader volume noise creates smooth, atmospheric gradient mist, whereas the reference shows slightly more localized wispy cloud wisps skimming the water surface in the foreground right channel.
  3. **Fine Erosion & Foliage Density**: While shrines, cornice slabs, fallen columns, ashlar stone variation, and `105` instanced reed clusters provide clear scale and debris, ultra-fine weathered moss patches, micro-cracks, and small grass tufts along cliff ledges are simpler than the matte-painted detail of the reference.
  4. **Vegetation & Sculpture Detail Level**: The statue reads clearly in medium/wide shots with draped folds and hood, though close-up camera inspection (`CAM_STATUE_COURTYARD`) would benefit from high-poly sculpting if inspected at portrait distance.
  5. **Animation Not Pre-Rendered**: `--animate` (`setup_cinematic_animation` for 8s @ 24 fps = 192 frames) is implemented and verified in `scripts/cameras.py` and `scripts/build_scene.py`, but frames were not rendered by default due to CPU-only render time (~`22 min/frame` at full `2560x1440` quality, or ~`2.5 hours` even at preview settings).
