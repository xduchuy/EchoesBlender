# THE FORGOTTEN KNIGHT — Blender 5.3 Procedural 3D Character Reconstruction

Procedural AAA dark-fantasy 3D character reconstruction of **The Forgotten Knight** built from `references/forgotten_knight.png` in **Blender 5.3** (`bpy` + `bmesh` + Cycles + OpenImageDenoise + AgX) and exported to both an editable `.blend` project and a Draco-compressed rigged `.glb` asset.

## Repository Structure (`forgotten_knight/`)

```text
forgotten_knight/
├── references/
│   └── forgotten_knight.png          # Two-view character reference (1024x572)
├── scripts/
│   ├── config.py                     # Seed (42), joints, presets, collections, BMesh helpers
│   ├── materials.py                  # Procedural PBR shader library & heraldic crest texture
│   ├── character_body.py             # Proportional 1.85m slimmed anatomical underbody
│   ├── helmet_generator.py           # Closed pointed helmet, brow brim, vertical slats, dark interior void
│   ├── armor_generator.py            # Asymmetric cuirass, hero left pauldron/lames, tassets, greaves & boots
│   ├── chainmail_generator.py        # 3D staggered 4-in-1 chainmail ring strips & dark mail liners
│   ├── cloth_generator.py            # Draped neck scarf, rear cowl, split heraldic tabard, torn back cape
│   ├── equipment_generator.py        # Double waist belts, buckles, hip pouches, chest baldric
│   ├── sword_generator.py            # Held right-hand longsword & diagonal back-mounted wrapped scabbard
│   ├── lantern_generator.py          # Hanging hip brass lantern with subtle non-magical inner flame
│   ├── pedestal.py                   # Cracked circular stepped stone pedestal, puddles, moss, creeping roots
│   ├── rigging.py                    # 30-bone Rig_ForgottenKnight armature & hybrid rigid/deform skinning
│   ├── lighting.py                   # 5-light dark-fantasy Cycles area rig & misty slate-teal World
│   ├── cameras.py                    # CAM_FRONT_3Q, CAM_REAR_3Q (75mm), detail cameras & ref plane
│   ├── render.py                     # Cycles CPU + OpenImageDenoise + AgX render & 16:9 sheet stitching
│   └── build_character.py            # End-to-end CLI builder, validation, .blend/.glb export
├── output/
│   ├── forgotten_knight.blend        # Packed self-contained Blender 5.3 scene (~4.35 MiB / 4.56 MB)
│   ├── forgotten_knight.glb          # Rigged Draco-compressed glTF 2.0 binary (~1.99 MiB)
│   ├── build_stats.json              # Verified build, geometry, grounding & render report
│   └── textures/
│       └── tex_tabard_crest.png      # Procedural faded shield/rampant-beast crest decal
├── renders/
│   ├── character_sheet.png           # 2560x1440 side-by-side Front 3/4 & Rear 3/4 sheet
│   ├── front_view.png                # 1280x1440 CAM_FRONT_3Q render
│   ├── back_view.png                 # 1280x1440 CAM_REAR_3Q render
│   ├── helmet_closeup.png            # 1200x1200 CAM_FRONT_DETAIL closeup
│   ├── equipment_closeup.png         # 1200x1200 CAM_BACK_DETAIL closeup
│   └── preview.png                   # 960x540 quick preview character sheet
├── README.md
└── RECONSTRUCTION_REPORT.md
```

## Quick Start (Blender 5.3 CLI)

Run from inside `forgotten_knight/`:

```powershell
# Fast verification preview (960x540 sheet, MEDIUM detail, 48 samples)
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --python-exit-code 1 --python scripts/build_character.py -- --quality preview

# Review quality (1920x1080 sheet, MEDIUM detail, 128 samples)
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --python-exit-code 1 --python scripts/build_character.py -- --quality review

# Final production quality (2560x1440 sheet, HIGH detail, 256 samples) + closeups
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --python-exit-code 1 --python scripts/build_character.py -- --quality final --closeups

# Build .blend + .glb only (skip rendering)
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --python-exit-code 1 --python scripts/build_character.py -- --quality final --skip-render
```

Supported CLI flags (`scripts/build_character.py`):
- `--quality {preview,review,final}` — resolution, samples, and default detail density preset.
- `--detail {LOW,MEDIUM,HIGH}` — override mesh subdivision, chainmail ring density (`140`/`320`/`540` per zone), pedestal segments, and root count.
- `--view {front,back,sheet,all}` — choose which studio camera(s) to render.
- `--samples N` — explicit Cycles sample count override.
- `--closeups` — also render `CAM_FRONT_DETAIL` (`helmet_closeup.png`) and `CAM_BACK_DETAIL` (`equipment_closeup.png`).
- `--skip-render` / `--skip-glb` — skip image rendering or `.glb` export.

## Inspecting, Material Editing, Posing & Exporting in Blender UI

1. Open `forgotten_knight/output/forgotten_knight.blend` in Blender 5.3+.
2. **Orbit & Inspect**: Press **Middle Mouse Button (MMB)** to orbit, `Shift+MMB` to pan, `Scroll` to zoom, or `Numpad 0` (`View -> Cameras -> Set Active Object as Camera`) with `CAM_FRONT_3Q` / `CAM_REAR_3Q` in collection `17_CAMERAS`. Switch Viewport Shading to **Material Preview** or **Rendered**.
3. **Edit Armor Materials**: Select any armor object (e.g. `Armor_Cuirass`, `Armor_Pauldron_L`, `Helm_Skull`), open **Shader Editor**, and tweak `MAT_Steel_Worn`, `MAT_Steel_Oxidized`, `MAT_Steel_Dark`, or `MAT_Brass_Aged` (color mixes, rust amount, AO distance, scratch bump strength, roughness ramps).
4. **Pose the Knight**: Select `Rig_ForgottenKnight` (`02_ARMATURE`), switch to **Pose Mode** (`Ctrl+Tab`), and rotate/pose humanoid bones (`Root`, `Pelvis`, `Spine`, `Chest`, `Neck`, `Head`, `Clavicle_L/R`, `UpperArm_L/R`, `Forearm_L/R`, `Hand_L/R`, `Thigh_L/R`, `Shin_L/R`, `Foot_L/R`) plus secondary equipment/cloth bones (`Cape_Upper`, `Cape_Mid`, `Cape_Lower`, `Weapon_Back_Bone`, `Weapon_Main_Bone`, `Lantern_Swing`). Rigid plates hold `1.0` single-bone weights so steel does not stretch.
5. **Re-export to Engine**: Use `File -> Export -> glTF 2.0 (.glb/.gltf)` or re-run `build_character.py` to regenerate Draco-compressed `output/forgotten_knight.glb` with armature skinning and PBR base properties.
