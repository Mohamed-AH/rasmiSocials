"""Stage 1: Generate branded title card images for each lecture."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from pipeline.config import (
    EXCEL_FILE, IMAGES_DIR, CONTRAST_THRESHOLD, find_arabic_font
)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False
    print("[WARN] arabic_reshaper / python-bidi not installed. Arabic text may render incorrectly.")


# Brand colours
COLOR_BG_TOP    = (13,  27,  42)   # deep navy
COLOR_BG_BOTTOM = (27,  67,  50)   # dark teal
COLOR_GOLD      = (201, 168, 76)   # gold accent
COLOR_WHITE     = (255, 255, 255)
COLOR_LIGHT     = (220, 220, 220)


def _reshape(text: str) -> str:
    if not text or not ARABIC_SUPPORT:
        return text or ""
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_gradient(draw, width, height):
    for y in range(height):
        t = y / (height - 1)
        color = _lerp_color(COLOR_BG_TOP, COLOR_BG_BOTTOM, t)
        draw.line([(0, y), (width, y)], fill=color)


def _draw_star_decoration(img, cx, cy, radius, points=8, alpha=30):
    """Draw a subtle geometric star overlay in the corner."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    import math
    poly = []
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2
        r = radius if i % 2 == 0 else radius * 0.45
        poly.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    d.polygon(poly, outline=(201, 168, 76, alpha), fill=None)
    # Inner ring
    poly2 = []
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2
        r = (radius * 0.6) if i % 2 == 0 else (radius * 0.25)
        poly2.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    d.polygon(poly2, outline=(201, 168, 76, alpha), fill=None)
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0))


def _relative_luminance(rgb):
    """WCAG relative luminance of an sRGB colour tuple."""
    def ch(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _contrast_ratio(lum1, lum2):
    l1, l2 = max(lum1, lum2), min(lum1, lum2)
    return (l1 + 0.05) / (l2 + 0.05)


def _avg_luminance_under_box(img, bbox):
    """Sample average luminance of image pixels inside bbox (x0,y0,x1,y1)."""
    x0, y0, x1, y1 = [int(v) for v in bbox]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    region = img.crop((x0, y0, x1, y1)).convert("L")
    pixels = list(region.convert("L").tobytes())
    avg = sum(pixels) / len(pixels)
    # Convert average greyscale to approximate relative luminance
    return _relative_luminance((avg, avg, avg))


def _draw_text_safe(img, draw, xy, text, font, fill=COLOR_WHITE, pad=12):
    """
    Draw text at xy, first checking contrast and painting a semi-transparent
    dark overlay behind it if contrast ratio < CONTRAST_THRESHOLD.
    """
    if not text:
        return
    x, y = xy
    try:
        bbox = draw.textbbox((x, y), text, font=font)
    except AttributeError:
        # Pillow < 9 fallback
        w, h = draw.textsize(text, font=font)
        bbox = (x, y, x + w, y + h)

    bg_lum = _avg_luminance_under_box(img, bbox)
    text_lum = _relative_luminance(fill)
    ratio = _contrast_ratio(text_lum, bg_lum)

    if ratio < CONTRAST_THRESHOLD:
        overlay_box = (
            bbox[0] - pad, bbox[1] - pad,
            bbox[2] + pad, bbox[3] + pad,
        )
        # Draw semi-transparent dark rectangle
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle(overlay_box, fill=(0, 0, 0, 180))
        img.paste(
            Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"),
            (0, 0),
        )
        # Re-bind draw to updated img
        draw._image = img

    draw.text((x, y), text, font=font, fill=fill)


def generate_title_card(row, orientation="landscape"):
    """Generate a branded title card PNG for one lecture row."""
    os.makedirs(IMAGES_DIR, exist_ok=True)

    if orientation == "landscape":
        W, H = 1920, 1080
        font_sizes = {"series": 52, "seq": 38, "title": 44, "sheikh": 30, "date": 24}
    else:
        W, H = 1080, 1920
        font_sizes = {"series": 56, "seq": 40, "title": 48, "sheikh": 34, "date": 26}

    fonts = {k: find_arabic_font(v) for k, v in font_sizes.items()}

    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _draw_gradient(draw, W, H)

    # Decorative star top-right
    _draw_star_decoration(img, W - 160, 160, 120)
    _draw_star_decoration(img, 160, H - 160, 80)
    draw = ImageDraw.Draw(img)   # refresh after paste

    # Gold separator line at 60% height
    sep_y = int(H * 0.60)
    draw.line([(W * 0.1, sep_y), (W * 0.9, sep_y)], fill=COLOR_GOLD, width=3)

    sno         = int(row.get("S.No", 0))
    series      = _reshape(row.get("SeriesName", ""))
    seq         = _reshape(row.get("SequenceInSeries", ""))
    title_en    = str(row.get("TitleEnglish", ""))
    sheikh      = str(row.get("Sheikh", ""))
    date_val    = str(row.get("DateInGreg", ""))

    # ── Above separator: Arabic series + sequence ──
    top_zone_mid = int(H * 0.30)
    if series:
        try:
            sw = draw.textbbox((0, 0), series, font=fonts["series"])[2]
        except AttributeError:
            sw, _ = draw.textsize(series, font=fonts["series"])
        _draw_text_safe(img, draw, ((W - sw) // 2, top_zone_mid - 60),
                        series, fonts["series"], fill=COLOR_GOLD)
        draw = ImageDraw.Draw(img)

    if seq:
        try:
            qw = draw.textbbox((0, 0), seq, font=fonts["seq"])[2]
        except AttributeError:
            qw, _ = draw.textsize(seq, font=fonts["seq"])
        _draw_text_safe(img, draw, ((W - qw) // 2, top_zone_mid + 20),
                        seq, fonts["seq"], fill=COLOR_LIGHT)
        draw = ImageDraw.Draw(img)

    # ── Below separator: English title ──
    below_y = sep_y + 40
    if title_en:
        # Word-wrap at ~60 chars
        words = title_en.split()
        lines, line = [], []
        for w in words:
            if sum(len(x) + 1 for x in line) + len(w) > 60:
                lines.append(" ".join(line))
                line = [w]
            else:
                line.append(w)
        if line:
            lines.append(" ".join(line))

        for i, ln in enumerate(lines[:3]):
            try:
                lw = draw.textbbox((0, 0), ln, font=fonts["title"])[2]
            except AttributeError:
                lw, _ = draw.textsize(ln, font=fonts["title"])
            _draw_text_safe(img, draw,
                            ((W - lw) // 2, below_y + i * (font_sizes["title"] + 10)),
                            ln, fonts["title"], fill=COLOR_WHITE)
            draw = ImageDraw.Draw(img)

    # ── Sheikh name ──
    if sheikh:
        try:
            shw = draw.textbbox((0, 0), sheikh, font=fonts["sheikh"])[2]
        except AttributeError:
            shw, _ = draw.textsize(sheikh, font=fonts["sheikh"])
        _draw_text_safe(img, draw, ((W - shw) // 2, H - 120),
                        sheikh, fonts["sheikh"], fill=COLOR_GOLD)
        draw = ImageDraw.Draw(img)

    # ── Date bottom-right ──
    if date_val and date_val != "nan":
        _draw_text_safe(img, draw, (W - 200, H - 60),
                        date_val, fonts["date"], fill=COLOR_LIGHT)
        draw = ImageDraw.Draw(img)

    out_path = os.path.join(IMAGES_DIR, f"{sno}_{orientation}.png")
    img.save(out_path)
    return out_path


def generate_all_title_cards(excel_df):
    results = []
    total = len(excel_df)
    for i, (_, row) in enumerate(excel_df.iterrows(), 1):
        sno = int(row.get("S.No", i))
        print(f"  [{i}/{total}] Generating title cards for S.No {sno} …")
        land = generate_title_card(row, "landscape")
        port = generate_title_card(row, "portrait")
        results.append({"sno": sno, "landscape": land, "portrait": port})
    return results


if __name__ == "__main__":
    df = pd.read_excel(EXCEL_FILE)
    # Quick test: first 2 rows
    for _, row in df.head(2).iterrows():
        l = generate_title_card(row, "landscape")
        p = generate_title_card(row, "portrait")
        print(f"  ✓ {l}")
        print(f"  ✓ {p}")
    print("Stage 1 test complete.")
