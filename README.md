# EchoesBlender — The Drowned Sanctuary (Blender 5.3 + WebGL/Vercel)

A complete, editable, reproducible **Blender 5.3+** procedural reconstruction of **The Drowned Sanctuary**, paired with an **optimized Draco `.glb` export pipeline** and a **Three.js + Vite interactive 3D web viewer** ready for one-click deployment on **Vercel**.

---

## Project Structure

```text
EchoesBlender/
├── index.html                           # Three.js interactive WebGL app entry
├── package.json                         # Vite + Three.js dependencies & scripts
├── vite.config.js                       # Vite build & manual chunk config
├── vercel.json                          # Vercel static Vite deployment & GLB cache headers
├── src/
│   ├── main.js                          # HUD state, camera presets, compare modal & keyboard bindings
│   ├── styles/main.css                  # Minimalist dark glass UI styling
│   └── scene/
│       ├── config.js                    # Blender-synced Y-up camera presets & lighting moods
│       ├── materials.js                 # Procedural canvas PBR normals & animated water shader
│       ├── atmosphere.js                # Gradient sky dome, PMREM reflections, mist & dust motes
│       └── SanctuaryViewer.js           # Three.js renderer, Draco GLTFLoader, Orbit/WASD & Bloom
├── public/
│   ├── models/drowned_sanctuary.glb     # Draco-compressed 3D export (148 meshes, 4.10 MB)
│   ├── draco/                           # Local Draco WASM/JS decoder (zero external CDN dependency)
│   └── images/                          # Reference & final Cycles render for in-app comparison
├── references/
│   └── sanctuary_reference.png          # Original reference artwork
├── scripts/
│   ├── config.py                        # Quality presets, palette, spatial layout, lighting & cameras
│   ├── geometry_utils.py                # Collection setup, deterministic RNG, pointed arch & BMesh utils
│   ├── materials.py                     # Procedural PBR materials (limestone, cliffs, bark, water, fog)
│   ├── gothic_architecture.py           # Reusable Gothic arch/window/buttress/tower/destruction system
│   ├── statue.py                        # Multi-layered sculpted central robed stone statue & pedestal
│   ├── terrain.py                       # Stratified cliffs, flooded basin, courtyard, causeway, shrines & reeds
│   ├── roots.py                         # Recursive tapered 3D spline root bundles & hanging tendrils
│   ├── water.py                         # Flooded basin & distant horizon water mesh
│   ├── atmosphere.py                    # Multi-layer volumetric mist & distant aerial perspective
│   ├── lighting.py                      # Late-afternoon procedural sky + directional sun + cool fill
│   ├── cameras.py                       # Tracked cameras, AgX compositor, optional flythrough animation
│   ├── build_scene.py                   # Master Blender CLI entry point
│   ├── export_glb.py                    # Blender -> Draco GLB web exporter with baked vertex colors
│   └── compare_reference.py             # Side-by-side & 50/50 overlay reference comparison generator
├── output/
│   └── drowned_sanctuary.blend          # Editable Blender 5.3 project file (163 objects)
├── renders/
│   ├── preview.png                      # Fast preview render (960x540)
│   ├── drowned_sanctuary_final.png      # Final high-resolution Cycles render (2560x1440)
│   └── comparison_*.png                 # Visual validation comparison sheets
├── README.md
└── RECONSTRUCTION_REPORT.md
```

---

## 1. Web 3D Viewer & Vercel Deployment

### Run Locally (Node.js 20+ / 22+)
```bash
npm install
npm run dev
```

### Build Production Bundle
```bash
npm run build
npm run preview
```

### Deploy on Vercel
1. Connect **`https://github.com/xduchuy/EchoesBlender`** in the Vercel dashboard.
2. Leave **Framework Preset** as `Vite`, **Root Directory** as `./`, **Build Command** as `npm run build`, and **Output Directory** as `dist` (configured in `vercel.json`).
3. Deploy — `public/models/drowned_sanctuary.glb` and `/draco/*` load directly from Vercel's CDN.

### Web Viewer Controls
- **Camera Presets**: `Hero View`, `Architecture`, `Statue`, `Causeway` (converted cleanly from Blender Z-up to glTF Y-up).
- **Lighting Moods**: Cycle between `Afternoon` (matching the Cycles reference), `Moonlight`, and `Dawn`.
- **Explore (`WASD`)**: Free fly/walk exploration (`Shift` sprint, `Q`/`E` down/up, drag mouse to look, `Esc` to exit).
- **Cycles Render**: Side-by-side comparison modal between `sanctuary_reference.png` and the `2560x1440` Cycles render.
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
