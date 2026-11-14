# EchoesBlender V2 — Performance & Delivery Report

- **Target Runtime**: Static Vite (`^6.2.0`) + Three.js (`^0.171.0`) WebGL 2 viewer (`vercel.json` compatible)
- **Telemetry Source**: Live `#perf-stats` (`createPerfMonitor` in `src/scene/quality.js`) & Vite `dist/` production build output

---

## 1. Web Asset & Bundle Footprint

| Artifact | Size (Bytes) | Size (Human) | Notes |
|---|---|---|---|
| `public/models/drowned_sanctuary.glb` | `5,977,152` | `5.70 MB` | Draco mesh compression + `15` embedded WebP textures |
| `public/models/forgotten_knight.glb` | `2,696,808` | `2.57 MB` | Draco mesh compression + `12` embedded WebP textures + `9` NLA clips |
| **Combined 3D Payload** | `8,673,960` | **`8.27 MB`** | Zero external CDN dependencies (local `public/draco/`) |
| `dist/assets/three-CnFNF5WR.js` | `539,211` | `539.21 kB` | Gzip: `136.66 kB` (`three` manual chunk) |
| `dist/assets/index-DknNFyLO.js` | `209,961` | `209.96 kB` | Gzip: `81.46 kB` (app + viewer logic) |
| `dist/assets/index-Bh7_JEEe.css` | `6,578` | `6.58 kB` | Gzip: `2.13 kB` |
| `dist/index.html` | `5,058` | `5.06 kB` | Gzip: `1.61 kB` |

Local Draco runtime decoders included in `dist/draco/`:
- `draco_decoder.js`: `512,465` bytes (`0.49 MB`)
- `draco_decoder.wasm`: `192,420` bytes (`0.18 MB`)
- `draco_wasm_wrapper.js`: `58,456` bytes (`0.06 MB`)

---

## 2. Scalable Quality Tiers (`src/scene/quality.js`)

Auto-detection (`detectDefaultQuality`) selects `low` on software renderers (`SwiftShader`, `llvmpipe`) or constrained mobile (`<=3 GB` RAM / `<=4` cores), `medium` on standard mobile or `<=4`-core/`<=4 GB` devices, and `high` on desktop GPUs. Users can cycle presets anytime via `#btn-quality` or key `Q` (outside Explore mode).

| Preset | `maxPixelRatio` | `shadowMapSize` | `smaa` | `bloomScale` | `fogCount` | `fireflyCount` | `waterQuality` | `envIntensityScale` |
|---|---|---|---|---|---|---|---|---|
| **Low** | `1.0` | `1024` | `false` | `0.55` | `24` | `45` | `0` | `0.92` |
| **Medium** | `1.35` | `2048` | `false` | `0.85` | `44` | `95` | `1` | `1.00` |
| **High** | `1.75` | `2048` | `true` | `1.00` | `68` | `150` | `2` | `1.00` |
| **Ultra** | `2.0` | `4096` | `true` | `1.08` | `84` | `210` | `3` | `1.05` |

---

## 3. Observed Runtime Telemetry (`1280x720`, Chromium Live QA)

Scene complexity loaded at runtime: **`224` meshes, `551k` triangles**.

- **Hero View (Initial, `High`, SMAA + Bloom + `2048px` shadows)**:
  - `#perf-stats`: `AgX · High · 28 FPS (35.9ms) · 757 draws`
- **Play Knight Mode (`High`, tight `[-18, 18]` dynamic shadow box)**:
  - `#perf-stats`: `AgX · High · 22 FPS (45.8ms) · 621 draws`
- **Hero View (Returned)**:
  - `#perf-stats`: `AgX · High · 20 FPS (50ms) · 757 draws`

> **Telemetry Fix**: During live QA, `renderer.info.render.calls` initially reported `1 draws` because `OutputPass` inside `EffectComposer` reset per-pass draw counters at frame end. Setting `this.renderer.info.autoReset = false` and calling `this.renderer.info.reset()` immediately before `this.composer.render()` in `src/scene/SanctuaryViewer.js` restored accurate cumulative frame draw call counting (`757 draws` / `621 draws`).

---

## 4. Offline Blender Build & Bake Execution Times

Measured directly on local CPU Cycles + OpenImageDenoise (Blender `5.3.0`, `--quality preview --detail MEDIUM`):
- **Drowned Sanctuary V2** (`scripts/build_scene.py` + `scripts/export_glb.py` multi-atlas WebP Cycles bake): `1015.1s` (exit `0`).
- **Forgotten Knight V2** (`forgotten_knight/scripts/build_character.py --quality preview --detail MEDIUM --closeups --sync-web`, `52,264` verts, `4` baked atlases + `6` renders + GLB sync): `269.71s` (exit `0`).
