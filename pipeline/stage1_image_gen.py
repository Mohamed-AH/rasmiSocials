"""Stage 1: Generate ornate Islamic-style title card images for each lecture."""

import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pipeline.config import EXCEL_FILE, IMAGES_DIR, CONTRAST_THRESHOLD, find_arabic_font

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False
    print("[WARN] arabic_reshaper / python-bidi not installed.")


# ─── Palette ────────────────────────────────────────────────────────────────

GOLD        = (201, 168,  76)
GOLD_LIGHT  = (234, 210, 120)
GOLD_DARK   = (140, 110,  40)
WHITE       = (255, 255, 255)
OFF_WHITE   = (245, 238, 215)
CREAM       = (255, 248, 220)

# Per-series accent palettes  (bg_top, bg_bottom, accent)
# Keyed by substring match against SeriesName Arabic text
SERIES_PALETTES = {
    "البخاري":   ((10,  20,  50),  (25,  55, 100), (201, 168,  76)),   # deep navy/gold
    "مسلم":      ((15,  40,  20),  (30,  80,  45), (180, 220, 160)),   # forest green
    "رياض":      ((50,  15,  15),  (100, 35,  30), (220, 170, 100)),   # deep burgundy
    "الأربعين":  ((20,  20,  50),  (50,  30,  80), (190, 160, 230)),   # indigo/purple
    "نخبة":      ((10,  35,  50),  (20,  70,  90), (100, 200, 210)),   # teal
    "DEFAULT":   ((10,  20,  45),  (25,  50,  80), (201, 168,  76)),   # default navy/gold
}


def _palette(series_name: str):
    for key, pal in SERIES_PALETTES.items():
        if key != "DEFAULT" and key in str(series_name):
            return pal
    return SERIES_PALETTES["DEFAULT"]


# ─── Arabic text helpers ─────────────────────────────────────────────────────

def _ar(text) -> str:
    if not text or not ARABIC_SUPPORT:
        return str(text or "")
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def _text_size(draw, text, font):
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]
    except AttributeError:
        return draw.textsize(text, font=font)


def _centered_x(draw, text, font, canvas_w, offset_x=0):
    w, _ = _text_size(draw, text, font)
    return (canvas_w - w) // 2 + offset_x


# ─── Contrast safety ─────────────────────────────────────────────────────────

def _relative_luminance(rgb):
    def ch(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])


def _contrast_ratio(l1, l2):
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _ensure_contrast(img, draw, bbox, fill, pad=14):
    """Paint a dark overlay behind bbox if contrast ratio < threshold."""
    x0, y0, x1, y1 = [int(v) for v in bbox]
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(img.width, x1 + pad), min(img.height, y1 + pad)
    region = img.crop((x0, y0, x1, y1)).convert("L")
    px = list(region.tobytes())
    avg = sum(px) / max(len(px), 1)
    bg_lum  = _relative_luminance((avg, avg, avg))
    txt_lum = _relative_luminance(fill[:3])
    if _contrast_ratio(txt_lum, bg_lum) < CONTRAST_THRESHOLD:
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov).rectangle((x0, y0, x1, y1), fill=(0, 0, 0, 170))
        img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))
        draw._image = img


def draw_text_safe(img, draw, xy, text, font, fill=WHITE, pad=14):
    if not text:
        return
    x, y = xy
    try:
        bb = draw.textbbox((x, y), text, font=font)
    except AttributeError:
        w, h = draw.textsize(text, font=font)
        bb = (x, y, x + w, y + h)
    _ensure_contrast(img, draw, bb, fill, pad)
    draw.text((x, y), text, font=font, fill=fill)


# ─── Drawing primitives ──────────────────────────────────────────────────────

def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_gradient(draw, W, H, top, bottom):
    for y in range(H):
        draw.line([(0, y), (W, y)], fill=_lerp(top, bottom, y / (H - 1)))


def draw_outer_border(draw, W, H, accent, margin=22, thickness=3):
    """Double-line ornate border with corner squares."""
    m, t = margin, thickness
    # Outer rectangle
    draw.rectangle([m, m, W - m, H - m], outline=accent, width=t)
    # Inner rectangle (offset by gap)
    gap = 10
    draw.rectangle([m + gap, m + gap, W - m - gap, H - m - gap], outline=accent, width=t)
    # Corner squares
    sq = 18
    for cx, cy in [(m, m), (W - m - sq, m), (m, H - m - sq), (W - m - sq, H - m - sq)]:
        draw.rectangle([cx, cy, cx + sq, cy + sq], fill=accent)


def draw_star(draw, cx, cy, r, points=8, fill=None, outline=None, width=1):
    poly = []
    for i in range(points * 2):
        angle = math.pi / points * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.42
        poly.append((cx + rr * math.cos(angle), cy + rr * math.sin(angle)))
    draw.polygon(poly, fill=fill, outline=outline)


def draw_corner_medallions(draw, W, H, accent, margin=32, r=55):
    """8-pointed star medallions at each corner."""
    positions = [
        (margin + r, margin + r),
        (W - margin - r, margin + r),
        (margin + r, H - margin - r),
        (W - margin - r, H - margin - r),
    ]
    for cx, cy in positions:
        draw_star(draw, cx, cy, r,      points=8, fill=accent + (60,),  outline=None)
        draw_star(draw, cx, cy, r * .7, points=8, fill=None,            outline=accent + (120,), width=1)
        draw_star(draw, cx, cy, r * .4, points=8, fill=accent + (180,), outline=None)


def draw_arch(draw, W, H, accent, accent_light):
    """
    Pointed Islamic arch framing the top section.
    The arch is drawn as two arcs meeting at a central point.
    """
    arch_cx   = W // 2
    arch_top  = int(H * 0.04)
    arch_bot  = int(H * 0.52)
    arch_w    = int(W * 0.52)
    arch_h    = arch_bot - arch_top

    # Each semicircle has its centre offset left/right
    radius = arch_w // 2
    lc = (arch_cx - radius // 2, arch_top + radius)   # left arc centre
    rc = (arch_cx + radius // 2, arch_top + radius)   # right arc centre

    def arc_points(cx, cy, r, start_deg, end_deg, steps=60):
        pts = []
        for i in range(steps + 1):
            a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    left_arc  = arc_points(lc[0], lc[1], radius, 180, 300, 60)
    right_arc = arc_points(rc[0], rc[1], radius, 240, 360, 60)

    # Tip point at the top centre
    tip = (arch_cx, arch_top + 10)

    # Arch side points at the bottom
    bot_left  = (arch_cx - arch_w // 2, arch_bot)
    bot_right = (arch_cx + arch_w // 2, arch_bot)

    # Build the full arch outline: left side up → tip → right side down
    arch_poly = [bot_left] + left_arc + [tip] + list(reversed(right_arc)) + [bot_right]

    # Fill arch with a slightly lighter overlay
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.polygon(arch_poly, fill=(255, 255, 255, 18))
    # Outline in gold
    od.line(arch_poly + [arch_poly[0]], fill=accent + (220,), width=3)
    # Inner arch outline (smaller, inset 12px)
    inner = []
    inset = 12
    for x, y in arch_poly:
        # Push each point slightly towards the arch centroid
        dx, dy = arch_cx - x, (arch_top + arch_h * .45) - y
        dist = math.hypot(dx, dy) or 1
        inner.append((x + dx / dist * inset, y + dy / dist * inset))
    od.line(inner + [inner[0]], fill=accent_light + (140,), width=1)

    img_tmp = Image.new("RGBA", (W, H))
    img_tmp.paste(ov)
    return img_tmp   # caller composites this


def draw_decorative_divider(draw, W, y, accent, width_pct=0.75):
    """Horizontal divider with a central diamond ornament."""
    x0 = int(W * (1 - width_pct) / 2)
    x1 = W - x0
    cx = W // 2

    draw.line([(x0, y), (cx - 30, y)], fill=accent, width=2)
    draw.line([(cx + 30, y), (x1, y)], fill=accent, width=2)

    # Diamond
    d = 14
    draw.polygon([(cx, y - d), (cx + d, y), (cx, y + d), (cx - d, y)],
                 fill=accent, outline=None)
    # Small dots either side
    for dx in [55, 80]:
        draw.ellipse([(cx - dx - 3, y - 3), (cx - dx + 3, y + 3)], fill=accent)
        draw.ellipse([(cx + dx - 3, y - 3), (cx + dx + 3, y + 3)], fill=accent)


def draw_sheikh_panel(draw, img, W, panel_y, panel_h, accent, sheikh_text, title_text,
                      font_name, font_small):
    """Styled panel at the bottom with sheikh name and optional title."""
    px0, px1 = int(W * 0.1), int(W * 0.9)
    # Panel fill
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rectangle([(px0, panel_y), (px1, panel_y + panel_h)],
                 fill=(0, 0, 0, 120), outline=None)
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))

    draw = ImageDraw.Draw(img)
    # Top border line of panel
    draw.line([(px0, panel_y), (px1, panel_y)], fill=accent, width=2)
    draw.line([(px0, panel_y + panel_h), (px1, panel_y + panel_h)], fill=accent, width=2)

    # Label "لفضيلة الشيخ" above the name
    label = _ar("لفضيلة الشيخ")
    lw, lh = _text_size(draw, label, font_small)
    label_y = panel_y + 12
    draw.text(((W - lw) // 2, label_y), label, font=font_small, fill=GOLD_LIGHT)

    # Sheikh name
    name = _ar(sheikh_text)
    nw, nh = _text_size(draw, name, font_name)
    name_y = label_y + lh + 8
    _ensure_contrast(img, draw, (
        (W - nw) // 2, name_y,
        (W + nw) // 2, name_y + nh
    ), WHITE)
    draw = ImageDraw.Draw(img)
    draw.text(((W - nw) // 2, name_y), name, font=font_name, fill=WHITE)

    # "حفظه الله" below name
    blessing = _ar("حفظه الله")
    bw, _ = _text_size(draw, blessing, font_small)
    draw.text(((W - bw) // 2, name_y + nh + 6), blessing, font=font_small, fill=GOLD_LIGHT)

    return draw


def draw_date_badge(draw, W, y, date_text, font, accent):
    """Pill-shaped badge containing the date."""
    if not date_text or date_text == "nan":
        return
    text = _ar(date_text)
    tw, th = _text_size(draw, text, font)
    pad_x, pad_y = 28, 10
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x0 = (W - bw) // 2
    x1 = x0 + bw
    y0, y1 = y, y + bh
    r = bh // 2
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r,
                            fill=(0, 0, 0, 0), outline=accent, width=2)
    draw.text((x0 + pad_x, y0 + pad_y), text, font=font, fill=accent)


def draw_tiling_pattern(img, W, H, accent, margin=33):
    """
    Subtle repeating geometric tile pattern along the border strips.
    Draws small 8-pointed stars in a grid within the border margin.
    """
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    step = 48
    r    = 14

    # Top / bottom strips
    for strip_y in [margin // 2, H - margin // 2]:
        x = margin + step // 2
        while x < W - margin:
            draw_star(od, x, strip_y, r, points=8,
                      fill=accent + (50,), outline=accent + (90,))
            x += step

    # Left / right strips
    for strip_x in [margin // 2, W - margin // 2]:
        y = margin + step // 2
        while y < H - margin:
            draw_star(od, strip_x, y, r, points=8,
                      fill=accent + (50,), outline=accent + (90,))
            y += step

    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


# ─── Main generator ──────────────────────────────────────────────────────────

def generate_title_card(row, orientation="landscape"):
    os.makedirs(IMAGES_DIR, exist_ok=True)

    if orientation == "landscape":
        W, H    = 1920, 1080
        fsizes  = {"huge": 96, "large": 72, "med": 52, "small": 36, "tiny": 28}
        margins = {"border": 28, "arch_margin": 80}
    else:   # portrait 9:16
        W, H    = 1080, 1920
        fsizes  = {"huge": 108, "large": 80, "med": 58, "small": 40, "tiny": 30}
        margins = {"border": 28, "arch_margin": 80}

    bg_top, bg_bottom, accent = _palette(row.get("SeriesName", ""))
    accent_rgba  = accent + (255,)
    accent_light = tuple(min(255, c + 60) for c in accent)

    # ── Base canvas ──────────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, W, H, bg_top, bg_bottom)

    # ── Arch overlay ─────────────────────────────────────────────────────────
    arch_ov = draw_arch(draw, W, H, accent, accent_light)
    img.paste(Image.alpha_composite(img.convert("RGBA"), arch_ov).convert("RGB"))

    # ── Tiling border pattern ─────────────────────────────────────────────────
    draw_tiling_pattern(img, W, H, accent, margin=margins["border"] + 4)

    # ── Outer border ─────────────────────────────────────────────────────────
    draw = ImageDraw.Draw(img)
    draw_outer_border(draw, W, H, accent, margin=margins["border"], thickness=3)

    # ── Corner medallions ─────────────────────────────────────────────────────
    corner_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_corner_medallions(ImageDraw.Draw(corner_ov), W, H, accent,
                           margin=margins["border"] + 10, r=50 if orientation == "landscape" else 60)
    img.paste(Image.alpha_composite(img.convert("RGBA"), corner_ov).convert("RGB"))
    draw = ImageDraw.Draw(img)

    # ── Fonts ──────────────────────────────────────────────────────────────
    f_huge  = find_arabic_font(fsizes["huge"])
    f_large = find_arabic_font(fsizes["large"])
    f_med   = find_arabic_font(fsizes["med"])
    f_small = find_arabic_font(fsizes["small"])
    f_tiny  = find_arabic_font(fsizes["tiny"])

    # ── Extract row data ────────────────────────────────────────────────────
    sno      = int(row.get("S.No", 0))
    series   = _ar(row.get("SeriesName",       ""))
    seq      = _ar(row.get("SequenceInSeries", ""))
    title_en = str(row.get("TitleEnglish",     ""))
    sheikh   = str(row.get("Sheikh",           ""))
    date_val = str(row.get("DateInGreg",       ""))

    # ── Layout zones ────────────────────────────────────────────────────────
    # The arch occupies roughly 0–52% of height.
    # Sheikh panel: bottom 18% of canvas.
    # Content zone: between arch base and sheikh panel.

    arch_zone_bot  = int(H * 0.51)
    sheikh_panel_y = int(H * 0.80)
    sheikh_panel_h = int(H * 0.14)
    content_top    = int(H * 0.10)   # inside arch

    # ── Series name (inside arch, top) ──────────────────────────────────────
    if series:
        sw, sh = _text_size(draw, series, f_small)
        sy = content_top + int(H * 0.01)
        draw_text_safe(img, draw, ((W - sw) // 2, sy), series, f_small, fill=GOLD_LIGHT)
        draw = ImageDraw.Draw(img)

    # ── Divider below series name ────────────────────────────────────────────
    div1_y = content_top + int(H * 0.07)
    draw_decorative_divider(draw, W, div1_y, accent, width_pct=0.45)

    # ── Main title (Arabic series — large, centred in arch) ──────────────────
    # Use SeriesName as the hero text in Arabic, sequence as subtitle
    hero      = series   # e.g. "صحيح البخاري"
    hero_font = f_huge

    if hero:
        hw, hh = _text_size(draw, hero, hero_font)
        # If too wide, fall back to large font
        if hw > W * 0.80:
            hero_font = f_large
            hw, hh = _text_size(draw, hero, hero_font)
        hero_y = div1_y + int(H * 0.04)
        draw_text_safe(img, draw, ((W - hw) // 2, hero_y), hero, hero_font, fill=WHITE)
        draw = ImageDraw.Draw(img)

        if seq:
            # Sequence number below hero
            qw, qh = _text_size(draw, seq, f_med)
            seq_y = hero_y + hh + int(H * 0.02)
            draw_text_safe(img, draw, ((W - qw) // 2, seq_y), seq, f_med, fill=GOLD_LIGHT)
            draw = ImageDraw.Draw(img)
            div2_y = seq_y + qh + int(H * 0.02)
        else:
            div2_y = hero_y + hh + int(H * 0.03)

        draw_decorative_divider(draw, W, div2_y, accent, width_pct=0.40)

    # ── English title (below arch, in content zone) ──────────────────────────
    title_zone_top = arch_zone_bot + int(H * 0.02)

    if title_en:
        # Word-wrap
        words = title_en.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            tw, _ = _text_size(draw, test, f_small)
            if tw > W * 0.75 and cur:
                lines.append(" ".join(cur))
                cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(" ".join(cur))

        line_h = fsizes["small"] + 8
        block_h = len(lines) * line_h
        ty = title_zone_top + (sheikh_panel_y - title_zone_top - block_h) // 2

        for i, ln in enumerate(lines[:3]):
            lw, _ = _text_size(draw, ln, f_small)
            draw_text_safe(img, draw, ((W - lw) // 2, ty + i * line_h),
                           ln, f_small, fill=OFF_WHITE)
            draw = ImageDraw.Draw(img)

    # ── Date badge ────────────────────────────────────────────────────────────
    date_y = sheikh_panel_y - int(H * 0.06)
    draw_date_badge(draw, W, date_y, date_val, f_tiny, accent)

    # ── Sheikh panel ─────────────────────────────────────────────────────────
    draw = draw_sheikh_panel(draw, img, W, sheikh_panel_y, sheikh_panel_h,
                             accent, sheikh, title_en, f_med, f_small)

    # ── Bottom organisation strip ─────────────────────────────────────────────
    strip_y = sheikh_panel_y + sheikh_panel_h + int(H * 0.01)
    strip_h = H - strip_y - margins["border"] - 10

    if strip_h > 20:
        ov2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ov2).rectangle(
            [(margins["border"] + 12, strip_y),
             (W - margins["border"] - 12, strip_y + strip_h)],
            fill=accent + (40,)
        )
        img.paste(Image.alpha_composite(img.convert("RGBA"), ov2).convert("RGB"))
        draw = ImageDraw.Draw(img)

        org_text = _ar("المجموعة العلمية")
        ow, oh = _text_size(draw, org_text, f_tiny)
        org_y = strip_y + (strip_h - oh) // 2
        draw.text(((W - ow) // 2, org_y), org_text, font=f_tiny, fill=accent)

    out_path = os.path.join(IMAGES_DIR, f"{sno}_{orientation}.png")
    img.save(out_path, quality=95)
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
    for _, row in df.head(2).iterrows():
        l = generate_title_card(row, "landscape")
        p = generate_title_card(row, "portrait")
        print(f"  ✓ {l}")
        print(f"  ✓ {p}")
    print("Stage 1 test complete.")
