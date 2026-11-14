"""Generate a visual side-by-side comparison sheet between reference and Blender render."""

import argparse
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_comparison_sheet(ref_path: Path, render_path: Path, out_path: Path) -> None:
    ref = Image.open(ref_path).convert("RGB")
    ren = Image.open(render_path).convert("RGB")

    # Match render size to reference dimensions for clean visual overlay
    w, h = ref.size
    ren_resized = ren.resize((w, h), Image.Resampling.LANCZOS)

    # Create 2x2 or 2-top + 1-bottom comparison sheet
    pad = 12
    header = 34
    sheet_w = w * 2 + pad * 3
    sheet_h = h * 2 + header * 2 + pad * 3
    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 26, 28))
    draw = ImageDraw.Draw(sheet)

    # Top-left: Reference
    sheet.paste(ref, (pad, header))
    draw.text((pad, 8), "REFERENCE (sanctuary_reference.png)", fill=(230, 230, 220))

    # Top-right: Render
    sheet.paste(ren_resized, (w + pad * 2, header))
    draw.text((w + pad * 2, 8), f"BLENDER RENDER ({render_path.name})", fill=(230, 230, 220))

    # Bottom-left: 50/50 Overlay for silhouette alignment
    overlay = Image.blend(ref, ren_resized, alpha=0.5)
    y_bot = header * 2 + h + pad
    sheet.paste(overlay, (pad, y_bot))
    draw.text((pad, header + h + pad + 8), "50/50 SILHOUETTE OVERLAY", fill=(200, 220, 255))

    # Bottom-right: Difference / edge alignment map (amplified 2x)
    diff = ImageChops.difference(ref, ren_resized)
    diff_amp = diff.point(lambda x: min(255, int(x * 2.2)))
    sheet.paste(diff_amp, (w + pad * 2, y_bot))
    draw.text((w + pad * 2, header + h + pad + 8), "TONAL / SILHOUETTE DIFFERENCE (2.2x)", fill=(255, 200, 180))

    os.makedirs(out_path.parent, exist_ok=True)
    sheet.save(out_path)
    print(f"Saved comparison sheet: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", default=str(PROJECT_ROOT / "references" / "sanctuary_reference.png"))
    parser.add_argument("--render", default=str(PROJECT_ROOT / "renders" / "preview.png"))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "renders" / "comparison_preview.png"))
    args = parser.parse_args()
    create_comparison_sheet(Path(args.ref), Path(args.render), Path(args.out))
