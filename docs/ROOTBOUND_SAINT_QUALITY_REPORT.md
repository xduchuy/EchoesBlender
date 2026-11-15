# The Rootbound Saint (V3) — Quality Verification Report

- **Branch**: `feat/rootbound-saint-v3`
- **Verification Date**: 2026-11-15
- **Blender Version**: Blender `5.3.0` (`Cycles`, CPU `12th Gen Intel Core i7-1265U`)
- **Automated Tests**: `npm test` (`6/6` passing via `tests/verify_v2.mjs`)
- **Production Build**: `npm run build` (`vite build` succeeded in `1.11s`, `29` modules)

---

## 1. Asset & Export Verification

| Artifact | Path | Measured Output | Status |
|---|---|---|---|
| Isolated Source Blend | `output/rootbound_saint/rootbound_saint_source.blend` | `1,237,363` bytes (`46,272` verts, `47,185` polys, `max_radius_m: 10.38`) | Passed |
| Isolated GLB | `output/rootbound_saint/rootbound_saint.glb` | `1,806,104` bytes, Draco + WebP (`Sanctuary_RootboundSaint` `1536px`) | Passed (`tests/verify_v2.mjs`) |
| Integrated Scene Blend | `output/drowned_sanctuary_v2.blend` | `4,370,936` bytes (`MONUMENT_MODE = "ROOTBOUND_SAINT"`) | Passed |
| Integrated Web GLB | `public/models/drowned_sanctuary.glb` | `7,376,004` bytes, `8` materials, `15` `image/webp` images, `67` meshes / `67` primitives, Draco | Passed (`tests/verify_v2.mjs`) |

---

## 2. Geometry, Silhouette & Material Fixes Verified

1. **Upper-Body Anatomy & Halo Silhouette (`scripts/rootbound_saint.py`)**
   - Terminated `Saint_Robe` cleanly inside `Saint_Torso` (`robe_h = fig_h * 0.565`), removing shoulder protrusions.
   - Refined `_build_saint_hood` crown dome (`tv = 0.74..1.00`), `_build_saint_face_and_head` jaw/throat shadow recess, and `_build_saint_hands` flat layered overlapping fingers without wrist bulging.
   - Smoothed the Gothic halo (`segs = 80`, centered at `ped_top_z + fig_h * 0.784`) so it silhouettes cleanly against the ruined abbey lancet arches.
2. **Continuous Root Extrusion (`_add_tapered_root_tube`)**
   - Replaced discontinuous `abs(tan.z) < 0.92` tangent-frame flipping with continuous parallel transport and grounded `Root_Primary`, `Root_Secondary`, and `Root_Tendrils` endpoints cleanly onto stone masonry without bow-tie pinching.
3. **Monument Validation (`validate_rootbound_saint()`)**
   - `passed: True`
   - `missing_objects: []`
   - `unshaded_objects: []`
   - `legacy_statue_present: False`
   - `total_vertices: 46272`, `total_polygons: 47185`
   - `bbox_min_z: -0.856`, `bbox_max_z: 15.933`, `max_radius_m: 10.381`

---

## 3. Visual Renders & Live WebGL QA

### Cycles Verification Renders (`renders/rootbound_saint/`)
- `statue_closeup.png` (`982,436` bytes) — `CAM_ROOTBOUND_FRONT` close-up verifying hood dome, face shadow, folded hands, drape folds, and continuous bark roots.
- `hero.png` (`1,080,138` bytes) — `CAM_ROOTBOUND_HERO` monument overview checking balustrade symmetry, twin staircases, terrace water, and root grounding.
- `staircase_detail.png` (`1,328,170` bytes) — `CAM_ROOTBOUND_DETAIL` inspection of masonry bevels, submerged slabs, and baluster contact.
- `integrated_sanctuary.png` (`2,939,625` bytes) — Full `1920x1080` (`128` samples, `915.0s` CPU) `CAM_HERO_REFERENCE` render verifying seamless placement between cathedral towers, clear causeway connection at `y = -5.65`, reed clearance (`r >= 8.6`), and water reflections.

### Live Three.js WebGL Verification (`http://127.0.0.1:4173/`)
- **Screenshot**: [`renders/rootbound_saint/web_comparison.png`](../renders/rootbound_saint/web_comparison.png) (`439,302` bytes, `1440x900` desktop viewport)
- **Runtime Errors**: `0` `console.error`, `0` `pageerror`
- **Scene Stats (HUD)**: `226 meshes · 710k tris · AgX · High · 611 draws`
- **Verified Behaviors**:
  - `Hero View` renders the integrated Drowned Sanctuary with The Rootbound Saint centered in the flooded courtyard and the extended causeway reaching the terrace threshold.
  - `Collision_Terrace`, `Collision_Stairs`, and `Collision_Pedestal` remain completely invisible (`visible = false`).
  - `Play Knight` mode + forward movement (`W`) advances The Forgotten Knight cleanly along the causeway toward the terrace threshold without stuttering or shader errors.
  - `Statue` camera preset (`[3.5, 17.8, 25.8]` -> `[0.0, 7.4, -2.0]`, `fov: 36`) frames the full monument unobstructed against the rear cathedral arches.

---

## 4. Test & Build Output Summary

- `npm test`: `6/6` tests passed in `105.17 ms` (`0` failed, `0` skipped), validating both `public/models/drowned_sanctuary.glb` and `output/rootbound_saint/rootbound_saint.glb` contain all 25 Rootbound Saint nodes + collision proxies and `MAT_Baked_Sanctuary_RootboundSaint`, alongside Forgotten Knight rig/clips and viewer config checks.
- `npm run build`: succeeded cleanly in `1.11s` (`dist/index.html` `5.16 kB`, `dist/assets/index-Bh7_JEEe.css` `6.58 kB`, `dist/assets/index-0CymYJ75.js` `210.61 kB`, `dist/assets/three-CnFNF5WR.js` `539.21 kB`).
