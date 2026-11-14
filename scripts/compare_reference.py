"""Generate visual side-by-side comparison sheets and image metrics for EchoesBlender."""

import argparse
import json
import math
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_font(size: int):
    candidates = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _to_luma(arr: np.ndarray) -> np.ndarray:
    return 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]


def _sobel_mag(luma: np.ndarray) -> np.ndarray:
    gx = (
        -luma[:-2, :-2] + luma[:-2, 2:]
        - 2.0 * luma[1:-1, :-2] + 2.0 * luma[1:-1, 2:]
        - luma[2:, :-2] + luma[2:, 2:]
    )
    gy = (
        -luma[:-2, :-2] - 2.0 * luma[:-2, 1:-1] - luma[:-2, 2:]
        + luma[2:, :-2] + 2.0 * luma[2:, 1:-1] + luma[2:, 2:]
    )
    return np.hypot(gx, gy)


def _block_mean(img: np.ndarray, block: int = 8) -> np.ndarray:
    h, w = img.shape
    bh = (h // block) * block
    bw = (w // block) * block
    trimmed = img[:bh, :bw]
    return trimmed.reshape(bh // block, block, bw // block, block).mean(axis=(1, 3))


def compute_image_metrics(ref_img: Image.Image, cand_img: Image.Image) -> dict:
    """Compute RMSE, PSNR, block SSIM, gradient similarity, and luminance stats."""
    w, h = ref_img.size
    cand = cand_img.resize((w, h), Image.Resampling.LANCZOS)
    a = np.asarray(ref_img, dtype=np.float64) / 255.0
    b = np.asarray(cand, dtype=np.float64) / 255.0

    diff = a - b
    mse = float(np.mean(diff * diff))
    rmse = math.sqrt(mse)
    psnr = 20.0 * math.log10(1.0 / max(rmse, 1e-8))

    la = _to_luma(a)
    lb = _to_luma(b)

    # 8x8 local window SSIM on luminance
    ba = _block_mean(la, 8)
    bb = _block_mean(lb, 8)
    h8 = (la.shape[0] // 8) * 8
    w8 = (la.shape[1] // 8) * 8
    pa = la[:h8, :w8].reshape(h8 // 8, 8, w8 // 8, 8)
    pb = lb[:h8, :w8].reshape(h8 // 8, 8, w8 // 8, 8)
    var_a = pa.var(axis=(1, 3))
    var_b = pb.var(axis=(1, 3))
    cov_ab = ((pa - ba[:, None, :, None]) * (pb - bb[:, None, :, None])).mean(axis=(1, 3))
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    ssim_map = ((2.0 * ba * bb + c1) * (2.0 * cov_ab + c2)) / (
        (ba * ba + bb * bb + c1) * (var_a + var_b + c2)
    )
    ssim = float(np.mean(ssim_map))

    # Edge magnitude cosine similarity + edge IoU (top 20% gradient energy)
    ea = _sobel_mag(la)
    eb = _sobel_mag(lb)
    denom = float(np.linalg.norm(ea) * np.linalg.norm(eb))
    grad_cos = float(np.sum(ea * eb) / denom) if denom > 1e-8 else 0.0
    ta = np.quantile(ea, 0.80)
    tb = np.quantile(eb, 0.80)
    ma = ea >= ta
    mb = eb >= tb
    inter = float(np.logical_and(ma, mb).sum())
    union = float(np.logical_or(ma, mb).sum())
    edge_iou = inter / union if union > 0 else 0.0

    return {
        "rmse": round(rmse, 4),
        "psnr_db": round(psnr, 2),
        "ssim_luma": round(ssim, 4),
        "grad_cosine": round(grad_cos, 4),
        "edge_iou": round(edge_iou, 4),
        "ref_luma_mean": round(float(np.mean(la)), 4),
        "cand_luma_mean": round(float(np.mean(lb)), 4),
        "ref_luma_std": round(float(np.std(la)), 4),
        "cand_luma_std": round(float(np.std(lb)), 4),
    }


def _fit_panel(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize preserving aspect ratio centered inside (target_w, target_h)."""
    canvas = Image.new("RGB", (target_w, target_h), (14, 17, 19))
    scale = min(target_w / img.width, target_h / img.height)
    nw = max(1, int(round(img.width * scale)))
    nh = max(1, int(round(img.height * scale)))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((target_w - nw) // 2, (target_h - nh) // 2))
    return canvas


def create_comparison_sheet(ref_path: Path, render_path: Path, out_path: Path) -> None:
    ref = Image.open(ref_path).convert("RGB")
    ren = Image.open(render_path).convert("RGB")

    # Match render size to reference dimensions for clean visual overlay
    w, h = ref.size
    ren_resized = ren.resize((w, h), Image.Resampling.LANCZOS)

    # Create 2x2 comparison sheet
    pad = 12
    header = 34
    sheet_w = w * 2 + pad * 3
    sheet_h = h * 2 + header * 2 + pad * 3
    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 26, 28))
    draw = ImageDraw.Draw(sheet)

    # Top-left: Reference
    sheet.paste(ref, (pad, header))
    draw.text((pad, 8), f"REFERENCE ({ref_path.name})", fill=(230, 230, 220))

    # Top-right: Render
    sheet.paste(ren_resized, (w + pad * 2, header))
    draw.text((w + pad * 2, 8), f"BLENDER RENDER ({render_path.name})", fill=(230, 230, 220))

    # Bottom-left: 50/50 Overlay for silhouette alignment
    overlay = Image.blend(ref, ren_resized, alpha=0.5)
    y_bot = header * 2 + h + pad
    sheet.paste(overlay, (pad, y_bot))
    draw.text((pad, header + h + pad + 8), "50/50 SILHOUETTE OVERLAY", fill=(200, 220, 255))

    # Bottom-right: Difference / edge alignment map (amplified 2.2x)
    diff = ImageChops.difference(ref, ren_resized)
    diff_amp = diff.point(lambda x: min(255, int(x * 2.2)))
    sheet.paste(diff_amp, (w + pad * 2, y_bot))
    draw.text((w + pad * 2, header + h + pad + 8), "TONAL / SILHOUETTE DIFFERENCE (2.2x)", fill=(255, 200, 180))

    os.makedirs(out_path.parent, exist_ok=True)
    sheet.save(out_path)
    print(f"Saved comparison sheet: {out_path}")


def create_triptych_sheet(
    ref_path: Path,
    before_path: Path,
    after_path: Path,
    out_path: Path,
    title: str,
) -> dict:
    """Create a 3x2 Before / After / Reference comparison sheet + return quantitative metrics."""
    ref_raw = Image.open(ref_path).convert("RGB")
    before_raw = Image.open(before_path).convert("RGB")
    after_raw = Image.open(after_path).convert("RGB")

    panel_w, panel_h = 640, 360
    pad = 16
    top_banner = 46
    hdr = 28
    sheet_w = panel_w * 3 + pad * 4
    sheet_h = top_banner + panel_h * 2 + hdr * 2 + pad * 3

    sheet = Image.new("RGB", (sheet_w, sheet_h), (16, 19, 21))
    draw = ImageDraw.Draw(sheet)
    font_title = _load_font(20)
    font_hdr = _load_font(15)
    font_body = _load_font(15)

    draw.text((pad, 12), title, fill=(224, 218, 200), font=font_title)

    ref_p = _fit_panel(ref_raw, panel_w, panel_h)
    bef_p = _fit_panel(before_raw, panel_w, panel_h)
    aft_p = _fit_panel(after_raw, panel_w, panel_h)

    overlay_ref_v2 = Image.blend(ref_p, aft_p, alpha=0.5)
    diff_v1_v2 = ImageChops.difference(bef_p, aft_p).point(lambda x: min(255, int(x * 2.5)))

    m_before = compute_image_metrics(ref_p, bef_p)
    m_after = compute_image_metrics(ref_p, aft_p)
    m_delta = compute_image_metrics(bef_p, aft_p)

    # Row 1
    y1_hdr = top_banner
    y1_img = y1_hdr + hdr
    panels_r1 = [
        ("REFERENCE", ref_p, (230, 226, 212)),
        (f"BASELINE V1 ({before_path.name})", bef_p, (210, 195, 175)),
        (f"UPGRADED V2 ({after_path.name})", aft_p, (175, 224, 195)),
    ]
    for i, (label, im, col) in enumerate(panels_r1):
        x = pad + i * (panel_w + pad)
        draw.text((x, y1_hdr + 4), label, fill=col, font=font_hdr)
        sheet.paste(im, (x, y1_img))

    # Row 2
    y2_hdr = y1_img + panel_h + pad
    y2_img = y2_hdr + hdr
    x0 = pad
    x1 = pad * 2 + panel_w
    x2 = pad * 3 + panel_w * 2

    draw.text((x0, y2_hdr + 4), "50/50 OVERLAY (REFERENCE vs V2)", fill=(180, 210, 240), font=font_hdr)
    sheet.paste(overlay_ref_v2, (x0, y2_img))

    draw.text((x1, y2_hdr + 4), "VISUAL DELTA V1 -> V2 (2.5x AMPLIFIED)", fill=(245, 195, 165), font=font_hdr)
    sheet.paste(diff_v1_v2, (x1, y2_img))

    draw.text((x2, y2_hdr + 4), "QUANTITATIVE IMAGE METRICS", fill=(212, 222, 200), font=font_hdr)
    stats_card = Image.new("RGB", (panel_w, panel_h), (22, 26, 29))
    sd = ImageDraw.Draw(stats_card)
    lines = [
        ("Metric              Baseline V1    Upgraded V2", (232, 226, 208)),
        ("-----------------------------------------------", (90, 100, 105)),
        (f"Luma SSIM vs Ref    {m_before['ssim_luma']:<14.4f} {m_after['ssim_luma']:.4f}", (180, 230, 195)),
        (f"RMSE vs Ref         {m_before['rmse']:<14.4f} {m_after['rmse']:.4f}", (205, 215, 220)),
        (f"PSNR vs Ref (dB)    {m_before['psnr_db']:<14.2f} {m_after['psnr_db']:.2f}", (205, 215, 220)),
        (f"Edge Cosine vs Ref  {m_before['grad_cosine']:<14.4f} {m_after['grad_cosine']:.4f}", (180, 230, 195)),
        (f"Edge IoU vs Ref     {m_before['edge_iou']:<14.4f} {m_after['edge_iou']:.4f}", (205, 215, 220)),
        (f"Mean Luma           {m_before['cand_luma_mean']:<14.4f} {m_after['cand_luma_mean']:.4f}  (Ref {m_after['ref_luma_mean']:.3f})", (205, 215, 220)),
        (f"Luma StdDev         {m_before['cand_luma_std']:<14.4f} {m_after['cand_luma_std']:.4f}  (Ref {m_after['ref_luma_std']:.3f})", (205, 215, 220)),
        ("-----------------------------------------------", (90, 100, 105)),
        (f"V1 -> V2 Direct RMSE : {m_delta['rmse']:.4f}  (PSNR {m_delta['psnr_db']:.2f} dB)", (245, 205, 170)),
        (f"V1 -> V2 Direct SSIM : {m_delta['ssim_luma']:.4f}", (245, 205, 170)),
    ]
    yy = 24
    for text, color in lines:
        sd.text((22, yy), text, fill=color, font=font_body)
        yy += 26
    sheet.paste(stats_card, (x2, y2_img))

    os.makedirs(out_path.parent, exist_ok=True)
    sheet.save(out_path)
    print(f"Saved V2 triptych sheet: {out_path}")
    return {"baseline_vs_ref": m_before, "v2_vs_ref": m_after, "v2_vs_baseline": m_delta}


def run_v2_suite() -> dict:
    sanctuary_metrics = create_triptych_sheet(
        ref_path=PROJECT_ROOT / "references" / "sanctuary_reference.png",
        before_path=PROJECT_ROOT / "renders" / "baseline" / "drowned_sanctuary_final.png",
        after_path=PROJECT_ROOT / "renders" / "v2" / "drowned_sanctuary_hero_v2.png",
        out_path=PROJECT_ROOT / "renders" / "v2" / "comparison_sanctuary_v2.png",
        title="ECHOESBLENDER V2 — THE DROWNED SANCTUARY (REFERENCE vs V1 BASELINE vs V2)",
    )
    knight_metrics = create_triptych_sheet(
        ref_path=PROJECT_ROOT / "forgotten_knight" / "references" / "forgotten_knight.png",
        before_path=PROJECT_ROOT / "forgotten_knight" / "renders" / "baseline" / "character_sheet.png",
        after_path=PROJECT_ROOT / "forgotten_knight" / "renders" / "v2" / "character_sheet.png",
        out_path=PROJECT_ROOT / "forgotten_knight" / "renders" / "v2" / "comparison_knight_v2.png",
        title="ECHOESBLENDER V2 — THE FORGOTTEN KNIGHT (REFERENCE vs V1 BASELINE vs V2)",
    )
    metrics = {"sanctuary": sanctuary_metrics, "knight": knight_metrics}
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["single", "v2"], default="single")
    parser.add_argument("--ref", default=str(PROJECT_ROOT / "references" / "sanctuary_reference.png"))
    parser.add_argument("--render", default=str(PROJECT_ROOT / "renders" / "preview.png"))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "renders" / "comparison_preview.png"))
    args = parser.parse_args()
    if args.suite == "v2":
        run_v2_suite()
    else:
        create_comparison_sheet(Path(args.ref), Path(args.render), Path(args.out))
