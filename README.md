# EchoesBlender V2 — The Drowned Sanctuary & The Forgotten Knight (Blender 5.3 + WebGL/Vercel)

A complete, editable, reproducible **Blender 5.3+** procedural reconstruction of **The Drowned Sanctuary** and playable **Forgotten Knight**, paired with **Cycles-baked WebP PBR atlases**, **Draco `.glb` exports**, **9 glTF NLA animation clips**, and a **Three.js + Vite interactive 3D web viewer** ready for deployment on **Vercel**.

---

## Project Structure

```text
EchoesBlender/
├── index.html                           # Three.js WebGL HUD, quality selector & mobile touch UI
├── package.json                         # Vite + Three.js dependencies & npm test / build scripts
├── vite.config.js                       # Vite build & manual chunk config
├── vercel.json                          # Vercel static Vite deployment & GLB cache headers
├── tests/
│   └── verify_v2.mjs                    # Node test suite validating GLBs, animations, presets & assets
├── docs/
│   ├── QUALITY_AUDIT.md                 # V2 pre-overhaul baseline engineering audit
│   ├── QUALITY_REPORT.md                # V2 visual, geometry & quantitative SSIM/RMSE verification
│   └── PERFORMANCE_REPORT.md            # V2 bundle sizes, draw calls, presets & timings
├── src/
│   ├── main.js                          # HUD state, quality/mood cycling, compare modal & touch bindings
│   ├── styles/main.css                  # Minimalist dark glass desktop + responsive mobile HUD
│   └── scene/
│       ├── config.js                    # Blender-synced Y-up camera presets & lighting moods
│       ├── quality.js                   # Low/Medium/High/Ultra presets, GPU tiering & PerfMonitor
│       ├── materials.js                 # Baked PBR preservation + 5-octave physical water & ripple shader
│       ├── knightMaterials.js           # Knight baked PBR atlases + Void/Glass/Flame lookdev materials
│       ├── KnightCharacter.js           # AnimationMixer (9 GLB clips) + causeway/water collision & wading
│       ├── atmosphere.js                # Sky cloud bands, dark-ground PMREM bounce, wispy mist & dust
│       └── SanctuaryViewer.js           # AgX tone mapping, Bloom + SMAA, dynamic shadows & controls
├── public/
│   ├── models/
│   │   ├── drowned_sanctuary.glb        # V2 Draco GLB (148 nodes, 15 WebP baked textures, 5.70 MB)
│   │   └── forgotten_knight.glb         # V2 Draco GLB (30 bones, 9 animations, 12 WebP textures, 2.57 MB)
│   ├── draco/                           # Local Draco WASM/JS decoder (zero external CDN dependency)
│   └── images/                          # Reference & V2 Cycles hero render for in-app comparison
├── references/
│   └── sanctuary_reference.png          # Original sanctuary reference artwork
├── scripts/                             # Drowned Sanctuary procedural modules, PBR baker & comparison tools
├── forgotten_knight/                    # Forgotten Knight generators, 30-bone rig, 9 actions & renders
├── output/                              # Baseline (.blend) & V2 (_v2.blend) Blender scenes
└── renders/                             # Baseline & V2 Cycles renders + comparison triptychs
```

---

## 1. Web 3D Viewer, Tests & Vercel Deployment

### Run Locally (Node.js 20+ / 22+)
```bash
npm install
npm test
npm run dev
```

### Build & Preview Production Bundle
```bash
npm run build
npm run preview
```

### Deploy on Vercel
1. Connect **`https://github.com/xduchuy/EchoesBlender`** in the Vercel dashboard.
2. Leave **Framework Preset** as `Vite`, **Root Directory** as `./`, **Build Command** as `npm run build`, and **Output Directory** as `dist` (configured in `vercel.json`).
3. Deploy — `public/models/*.glb` and `/draco/*` load directly from Vercel's CDN.

### Web Viewer Controls
- **Camera Presets**: `Hero View`, `Knight`, `Architecture`, `Statue`, `Causeway` (converted cleanly from Blender Z-up to glTF Y-up).
- **Play Knight (`K`)**: Third-person playable **Forgotten Knight** with `WASD`/Arrows movement, `Shift` sprint, `Space` leap, **`E` Sword Ready stance**, water wading ripples, and responsive mobile virtual joystick + Stance/Sprint/Leap buttons on touchscreens.
- **Lighting Moods**: Cycle between `Afternoon`, `Moonlight`, and `Dawn`.
- **Quality Presets (`Q`)**: Cycle `Low` / `Medium` / `High` / `Ultra` with live `#perf-stats` FPS, frame-time, and draw-call telemetry.
- **Explore (`WASD`)**: Free fly/walk exploration (`Shift` sprint, `Q`/`E` down/up, drag mouse to look, `Esc` to exit).
- **Cycles Render**: Side-by-side comparison modal between `sanctuary_reference.png` and `drowned_sanctuary_final.png`.
- **Hide UI (`H`)**: Toggle minimal HUD overlay.

---

## 2. Blender 5.3 Procedural Build & GLB Export

### Requirements
- **Blender**: 4.x or newer (verified on **Blender 5.3.0**).
- **Renderer**: Cycles (auto-selects GPU OPTIX/CUDA/HIP/ONEAPI if available; falls back cleanly to CPU + OpenImageDenoise).
- **Comparison tool (optional)**: Python 3 with `Pillow` (`PIL`) for `scripts/compare_reference.py`.

### CLI Usage (Windows)
On Windows when `blender` is not on `PATH`, replace `blender` with `"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"`.

```powershell
# 1. Build & render fast preview (960x540, 48 samples)
blender -b --python scripts/build_scene.py -- --quality preview

# 2. Build & render review quality (1920x1080, 128 samples)
blender -b --python scripts/build_scene.py -- --quality review

# 3. Build & render final presentation image (2560x1440, 128 samples)
blender -b --python scripts/build_scene.py -- --quality final

# 4. Re-export optimized web GLB from the saved .blend file
blender -b output/drowned_sanctuary.blend --python scripts/export_glb.py

# 5. Open editable scene in Blender GUI
blender output/drowned_sanctuary.blend
```

---

## 3. Blender Scene Collections

- `00_REFERENCE` — `Sanctuary_Control` empty with scene metadata custom properties
- `01_TERRAIN` — Seabed and distant coastal mountain ridges
- `02_CLIFFS` — Foreground stratified limestone cliffs and midground crags
- `03_ARCHITECTURE` — Subcollections `ARCH_LeftFront`, `ARCH_LeftRear`, `ARCH_RightRear`, `ARCH_RightFront`, `ARCH_RearArcade`, `ARCH_ConnectingWalls`
- `04_COURTYARD` — Flooded courtyard stone ring, statue island, diagonal causeway, scale figure
- `05_STATUE` — Pedestal and sculpted robed central monument
- `06_WATER` — Flooded basin water plane (`Z = 0.0`)
- `07_ROOTS` — Non-destructive Curve-based ancient root networks
- `08_RUBBLE` — Shoreline ruined shrines, tilted cornice slabs, fallen columns, rubble clusters
- `09_VEGETATION` — Instanced reed/grass tufts
- `10_ATMOSPHERE` — Bounded wireframe volumetric mist and distant haze domains (excluded from WebGL `.glb` export and replaced by Three.js fog/mist sprites)
- `11_LIGHTING` — `SUN_Key_LateAfternoon` and `AREA_CoolSky_Fill`
- `12_CAMERAS` — Tracked cameras and target empties
