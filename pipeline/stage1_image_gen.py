"""Stage 1: Generate ornate Islamic-style title card images for each lecture."""

import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from pipeline.config import EXCEL_FILE, IMAGES_DIR, CONTRAST_THRESHOLD

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False
    print("[WARN] arabic_reshaper / python-bidi not installed.")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(ROOT_DIR, "fonts")

# ── Font loading ─────────────────────────────────────────────────────────────

# Priority order: best Arabic display fonts first
_FONT_PREFERENCE = [
    "Amiri-Regular.ttf",              # traditional, excellent connected forms
    "NotoNaskhArabic-Regular.ttf",
    "NotoSansArabic-Regular.ttf",
    "NotoSansArabic-Bold.ttf",
    "Cairo-Regular.ttf",
]

_SYSTEM_FALLBACKS = [
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

_font_cache = {}

def get_font(size: int) -> ImageFont.FreeTypeFont:
    if size in _font_cache:
        return _font_cache[size]
    candidates = (
        [os.path.join(FONTS_DIR, f) for f in _FONT_PREFERENCE]
        + _SYSTEM_FALLBACKS
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _font_cache[size] = font
                return font
            except Exception:
                continue
    print(f"[WARN] No suitable font found. Run: python3 pipeline/setup_fonts.py")
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font


# ── Arabic helpers ────────────────────────────────────────────────────────────

def ar(text) -> str:
    """Reshape + bidi-reorder Arabic text for correct Pillow rendering."""
    if not text or not ARABIC_SUPPORT:
        return str(text or "")
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def text_w(draw, text, font):
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    except AttributeError:
        return draw.textsize(text, font=font)[0]


def text_h(draw, text, font):
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[3] - bb[1]
    except AttributeError:
        return draw.textsize(text, font=font)[1]


def draw_centered(img, draw, text, font, y, fill, check_contrast=True, pad=10):
    """Draw text horizontally centred, with optional contrast-safety overlay."""
    if not text:
        return
    W = img.width
    tw = text_w(draw, text, font)
    th = text_h(draw, text, font)
    x = (W - tw) // 2

    if check_contrast:
        x0, y0, x1, y1 = max(0,x-pad), max(0,y-pad), min(W,x+tw+pad), min(img.height,y+th+pad)
        region = img.crop((x0, y0, x1, y1)).convert("L")
        px = list(region.tobytes())
        avg_lum = (sum(px) / max(len(px),1)) / 255
        def rl(c): s=c/255; return s/12.92 if s<=0.03928 else ((s+0.055)/1.055)**2.4
        txt_lum = 0.2126*rl(fill[0]) + 0.7152*rl(fill[1]) + 0.0722*rl(fill[2])
        hi,lo = max(txt_lum,avg_lum), min(txt_lum,avg_lum)
        ratio = (hi+0.05)/(lo+0.05)
        if ratio < CONTRAST_THRESHOLD:
            ov = Image.new("RGBA", img.size, (0,0,0,0))
            ImageDraw.Draw(ov).rectangle((x0,y0,x1,y1), fill=(0,0,0,160))
            img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))
            draw._image = img

    draw.text((x, y), text, font=font, fill=fill)
    return y + th


# ── Colour palettes (per-series) ─────────────────────────────────────────────

PALETTES = {
    # keyword → (dark_bg, mid_bg, accent_gold, arch_fill_rgba)
    "البخاري":   ((8, 16, 45),   (18, 40, 85),  (201,168, 76), (230,215,165,240)),
    "مسلم":      ((8, 30, 18),   (18, 65, 38),  (140,210,130), (195,235,195,240)),
    "رياض":      ((40, 10, 12),  (85, 28, 25),  (215,160, 90), (240,215,185,240)),
    "الأربعين":  ((18, 16, 45),  (40, 28, 80),  (175,150,220), (215,205,240,240)),
    "نخبة":      ((8,  30, 44),  (18, 62, 80),  ( 90,195,205), (185,225,235,240)),
    "DEFAULT":   ((8, 16, 45),   (18, 40, 85),  (201,168, 76), (230,215,165,240)),
}

def palette(series_name):
    for key, pal in PALETTES.items():
        if key != "DEFAULT" and key in str(series_name):
            return pal
    return PALETTES["DEFAULT"]


# ── Geometry helpers ──────────────────────────────────────────────────────────

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))


def arc_points(cx, cy, r, start_deg, end_deg, steps=80):
    pts = []
    for i in range(steps + 1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def pointed_arch_polygon(cx, bot_y, half_span, tip_y):
    """
    Return polygon points for a proper equilateral pointed (ogival) arch.

    Construction:
      - Left foot : (cx - half_span, bot_y)
      - Right foot: (cx + half_span, bot_y)
      - Left arc  : radius = 2*half_span, centre at right foot
      - Right arc : radius = 2*half_span, centre at left foot
      - Tip       : (cx, tip_y)  — the two arcs meet here
    """
    r = half_span * 2

    left_foot  = (cx - half_span, bot_y)
    right_foot = (cx + half_span, bot_y)
    tip        = (cx, tip_y)

    # Left arc: centre = right_foot, goes from left_foot → tip
    lc = right_foot
    la_start = math.degrees(math.atan2(left_foot[1] - lc[1],  left_foot[0] - lc[0]))   # 180°
    la_end   = math.degrees(math.atan2(tip[1]       - lc[1],  tip[0]       - lc[0]))   # ~120°
    # Arc must sweep counter-clockwise (decreasing angle, i.e. end < start)
    if la_end > la_start:
        la_end -= 360
    left_arc = arc_points(lc[0], lc[1], r, la_start, la_end)

    # Right arc: centre = left_foot, goes from tip → right_foot
    rc = left_foot
    ra_start = math.degrees(math.atan2(tip[1]        - rc[1], tip[0]        - rc[0]))  # ~60°
    ra_end   = math.degrees(math.atan2(right_foot[1] - rc[1], right_foot[0] - rc[0]))  # 0°
    if ra_end > ra_start:
        ra_end -= 360
    right_arc = arc_points(rc[0], rc[1], r, ra_start, ra_end)

    return left_arc + right_arc


# ── Drawing primitives ────────────────────────────────────────────────────────

def draw_gradient_bg(img, W, H, dark, mid):
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        draw.line([(0, y), (W, y)], fill=lerp_color(dark, mid, t))


def draw_border(draw, W, H, gold, margin=24):
    """Double-line border with filled corner squares."""
    m = margin
    # Outer line
    draw.rectangle([m, m, W-m, H-m], outline=gold, width=3)
    # Inner line (gap of 8)
    draw.rectangle([m+9, m+9, W-m-9, H-m-9], outline=gold+(180,), width=1)
    # Solid corner squares
    s = 16
    for bx, by in [(m, m), (W-m-s, m), (m, H-m-s), (W-m-s, H-m-s)]:
        draw.rectangle([bx, by, bx+s, by+s], fill=gold)


def draw_corner_stars(img, W, H, gold, margin=24, r=52):
    """8-pointed star medallions at corners, drawn on a transparent overlay."""
    ov = Image.new("RGBA", (W, H), (0,0,0,0))
    d  = ImageDraw.Draw(ov)
    for cx, cy in [(margin+r+4, margin+r+4), (W-margin-r-4, margin+r+4),
                   (margin+r+4, H-margin-r-4), (W-margin-r-4, H-margin-r-4)]:
        for radius, alpha, filled in [(r, 90, True), (r*.65, 150, False), (r*.32, 220, True)]:
            pts = []
            for i in range(16):
                a  = math.pi/8 * i - math.pi/2
                rr = radius if i%2==0 else radius*0.40
                pts.append((cx + rr*math.cos(a), cy + rr*math.sin(a)))
            fill_col   = gold + (alpha,) if filled else None
            outline_col= gold + (alpha,)
            d.polygon(pts, fill=fill_col, outline=outline_col)
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


def draw_arch_shape(img, W, H, gold, arch_fill_rgba, half_span, tip_y, bot_y):
    """
    Fill the arch with a warm cream colour and draw the gold outline.
    Returns (arch_cx, arch_half_span, tip_y, bot_y) for layout reference.
    """
    cx = W // 2
    poly = pointed_arch_polygon(cx, bot_y, half_span, tip_y)

    # 1. Fill arch interior (cream/warm tone)
    fill_ov = Image.new("RGBA", (W, H), (0,0,0,0))
    ImageDraw.Draw(fill_ov).polygon(poly, fill=arch_fill_rgba)
    img.paste(Image.alpha_composite(img.convert("RGBA"), fill_ov).convert("RGB"))

    # 2. Gold outline — outer
    d = ImageDraw.Draw(img)
    d.line(poly + [poly[0]], fill=gold, width=4)

    # 3. Inner echo line (inset ~14px toward centroid)
    centroid_x = cx
    centroid_y = tip_y + (bot_y - tip_y) * 0.55
    inset = 14
    inner = []
    for x, y in poly:
        dx, dy = centroid_x - x, centroid_y - y
        dist = math.hypot(dx, dy) or 1
        inner.append((x + dx/dist*inset, y + dy/dist*inset))
    d.line(inner + [inner[0]], fill=gold+(160,), width=1)


def draw_divider(draw, W, y, gold, width_ratio=0.55):
    """Horizontal ornamental divider with central diamond."""
    pad = int(W * (1 - width_ratio) / 2)
    cx  = W // 2
    draw.line([(pad, y), (cx-22, y)], fill=gold, width=2)
    draw.line([(cx+22, y), (W-pad, y)], fill=gold, width=2)
    d = 10
    draw.polygon([(cx,y-d),(cx+d,y),(cx,y+d),(cx-d,y)], fill=gold)
    for dx in [40, 60]:
        draw.ellipse([(cx-dx-3,y-3),(cx-dx+3,y+3)], fill=gold)
        draw.ellipse([(cx+dx-3,y-3),(cx+dx+3,y+3)], fill=gold)


def draw_border_tile_strip(img, W, H, gold, margin=24):
    """Thin row of small stars running along all four inner border edges."""
    ov  = Image.new("RGBA", (W, H), (0,0,0,0))
    d   = ImageDraw.Draw(ov)
    r, step = 10, 42
    strip_inset = margin + 4   # place stars on the inner gap between the two border lines

    def star(cx, cy, alpha=70):
        pts = []
        for i in range(16):
            a = math.pi/8 * i - math.pi/2
            rr = r if i%2==0 else r*0.42
            pts.append((cx + rr*math.cos(a), cy + rr*math.sin(a)))
        d.polygon(pts, fill=gold+(alpha,))

    # Top / bottom strips
    for sy in [strip_inset + 4, H - strip_inset - 4]:
        x = margin + step
        while x < W - margin - step:
            star(x, sy)
            x += step

    # Left / right strips
    for sx in [strip_inset + 4, W - strip_inset - 4]:
        y = margin + step
        while y < H - margin - step:
            star(sx, y)
            y += step

    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


def draw_sheikh_panel(img, draw, W, panel_y, panel_h, gold, sheikh, f_name, f_small):
    """Bottom panel: 'لفضيلة الشيخ' / sheikh name / 'حفظه الله'."""
    px0, px1 = int(W*0.08), int(W*0.92)

    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rectangle([(px0, panel_y),(px1, panel_y+panel_h)],
                                  fill=(0,0,0,140))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))
    draw = ImageDraw.Draw(img)

    draw.line([(px0, panel_y),    (px1, panel_y)],    fill=gold, width=2)
    draw.line([(px0, panel_y+panel_h),(px1, panel_y+panel_h)], fill=gold, width=2)

    lbl  = ar("لفضيلة الشيخ")
    name = ar(sheikh)
    bls  = ar("حفظه الله")

    lh = text_h(draw, lbl,  f_small)
    nh = text_h(draw, name, f_name)
    bh = text_h(draw, bls,  f_small)

    total_h = lh + 6 + nh + 6 + bh
    start_y = panel_y + (panel_h - total_h) // 2

    draw_centered(img, draw, lbl,  f_small, start_y,           fill=(220,200,130), check_contrast=False)
    draw_centered(img, draw, name, f_name,  start_y + lh + 6,  fill=(255,255,255), check_contrast=False)
    draw_centered(img, draw, bls,  f_small, start_y+lh+6+nh+6, fill=(220,200,130), check_contrast=False)
    return ImageDraw.Draw(img)


# ── Main generator ────────────────────────────────────────────────────────────

def generate_title_card(row, orientation="landscape"):
    os.makedirs(IMAGES_DIR, exist_ok=True)

    if orientation == "landscape":
        W, H = 1920, 1080
        FS   = {"hero":110, "sub":62, "en":44, "name":52, "small":34, "tiny":26}
    else:
        W, H = 1080, 1920
        FS   = {"hero":120, "sub":68, "en":48, "name":58, "small":38, "tiny":28}

    # Per-series colour scheme
    dark_bg, mid_bg, gold, arch_fill = palette(row.get("SeriesName",""))
    gold_light = tuple(min(255,c+55) for c in gold)

    # ── Canvas + gradient ────────────────────────────────────────────────────
    img = Image.new("RGB", (W, H))
    draw_gradient_bg(img, W, H, dark_bg, mid_bg)

    # ── Arch geometry ────────────────────────────────────────────────────────
    arch_cx     = W // 2
    arch_bot_y  = int(H * 0.60)
    arch_hs     = int(W * 0.38)   # half-span
    arch_tip_y  = int(H * 0.03)

    draw_arch_shape(img, W, H, gold, arch_fill, arch_hs, arch_tip_y, arch_bot_y)

    # ── Border tile strip (before border lines so border sits on top) ────────
    draw_border_tile_strip(img, W, H, gold)

    # ── Border + corner stars ────────────────────────────────────────────────
    draw = ImageDraw.Draw(img)
    draw_border(draw, W, H, gold)
    draw_corner_stars(img, W, H, gold)
    draw = ImageDraw.Draw(img)

    # ── Extract data ─────────────────────────────────────────────────────────
    sno      = int(row.get("S.No", 0))
    series   = ar(row.get("SeriesName", ""))
    seq      = ar(row.get("SequenceInSeries", ""))
    title_en = str(row.get("TitleEnglish", ""))
    sheikh   = str(row.get("Sheikh", ""))
    date_val = str(row.get("DateInGreg", ""))

    # ── Fonts ────────────────────────────────────────────────────────────────
    f_hero  = get_font(FS["hero"])
    f_sub   = get_font(FS["sub"])
    f_en    = get_font(FS["en"])
    f_name  = get_font(FS["name"])
    f_small = get_font(FS["small"])
    f_tiny  = get_font(FS["tiny"])

    # ── Determine text colours based on arch interior (light bg) ─────────────
    # Inside arch → dark text on light background
    # Below arch  → light text on dark background
    ARCH_DARK  = (30, 20, 10)      # dark text for inside arch
    ARCH_GOLD  = (130, 80, 10)     # gold-dark for subtitles on light bg
    BELOW_WHITE= (255, 255, 255)
    BELOW_GOLD = gold_light

    # ── Layout inside arch ───────────────────────────────────────────────────
    arch_inner_top  = arch_tip_y + int(H * 0.06)
    arch_inner_mid  = arch_tip_y + (arch_bot_y - arch_tip_y) * 0.40

    # Series name (small label at very top of arch, gold-dark)
    y = arch_inner_top
    if series:
        # Fit font to arch width
        f = f_small
        while text_w(draw, series, f) > arch_hs * 1.7 and f.size > 18:
            f = get_font(f.size - 4)
        draw_centered(img, draw, series, f, y, fill=ARCH_GOLD, check_contrast=False)
        y += text_h(draw, series, f) + int(H * 0.01)
        draw = ImageDraw.Draw(img)

    # Thin divider
    div_y1 = y + int(H * 0.01)
    draw_divider(draw, W, div_y1, gold, width_ratio=0.38)
    y = div_y1 + int(H * 0.025)

    # Hero: series name large (the main visual centrepiece)
    if series:
        f = f_hero
        while text_w(draw, series, f) > arch_hs * 1.85 and f.size > 40:
            f = get_font(f.size - 6)
        draw_centered(img, draw, series, f, y, fill=ARCH_DARK, check_contrast=False)
        y += text_h(draw, series, f) + int(H * 0.015)
        draw = ImageDraw.Draw(img)

    # Sequence (lesson number) below hero
    if seq:
        f = f_sub
        while text_w(draw, seq, f) > arch_hs * 1.7 and f.size > 20:
            f = get_font(f.size - 4)
        draw_centered(img, draw, seq, f, y, fill=ARCH_GOLD, check_contrast=False)
        y += text_h(draw, seq, f) + int(H * 0.01)
        draw = ImageDraw.Draw(img)

    # Divider at bottom of arch content
    draw_divider(draw, W, y + int(H*0.01), gold, width_ratio=0.35)

    # ── Layout below arch ────────────────────────────────────────────────────
    # Sheikh panel occupies bottom 16% of canvas
    sheikh_panel_h = int(H * 0.155)
    sheikh_panel_y = H - sheikh_panel_h - 30

    # English title centred between arch base and sheikh panel
    below_zone_top  = arch_bot_y + int(H * 0.03)
    below_zone_bot  = sheikh_panel_y - int(H * 0.02)
    below_zone_h    = below_zone_bot - below_zone_top

    if title_en:
        words = title_en.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            if text_w(draw, test, f_en) > W * 0.78 and cur:
                lines.append(" ".join(cur))
                cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(" ".join(cur))
        lines = lines[:3]

        lh       = text_h(draw, lines[0], f_en) + 8
        block_h  = len(lines) * lh
        start_ty = below_zone_top + max(0, (below_zone_h - block_h) // 2)

        for i, ln in enumerate(lines):
            draw_centered(img, draw, ln, f_en,
                          start_ty + i * lh, fill=BELOW_WHITE)
            draw = ImageDraw.Draw(img)

    # Date badge just above sheikh panel
    if date_val and date_val != "nan":
        date_text = ar(date_val)
        tw = text_w(draw, date_text, f_tiny)
        th = text_h(draw, date_text, f_tiny)
        bx0 = (W - tw) // 2 - 22
        by0 = sheikh_panel_y - th - 28
        draw.rounded_rectangle([bx0, by0, bx0+tw+44, by0+th+16],
                                radius=(th+16)//2, outline=gold, width=2, fill=None)
        draw.text((bx0+22, by0+8), date_text, font=f_tiny, fill=gold)

    # Sheikh panel
    draw = draw_sheikh_panel(img, draw, W, sheikh_panel_y, sheikh_panel_h,
                             gold, sheikh, f_name, f_small)

    # ── Save ─────────────────────────────────────────────────────────────────
    out_path = os.path.join(IMAGES_DIR, f"{sno}_{orientation}.png")
    img.save(out_path, quality=95)
    return out_path


def generate_all_title_cards(excel_df):
    results = []
    total = len(excel_df)
    for i, (_, row) in enumerate(excel_df.iterrows(), 1):
        sno = int(row.get("S.No", i))
        print(f"  [{i}/{total}] S.No {sno} …")
        land = generate_title_card(row, "landscape")
        port = generate_title_card(row, "portrait")
        results.append({"sno": sno, "landscape": land, "portrait": port})
    return results


if __name__ == "__main__":
    df = pd.read_excel(EXCEL_FILE)
    for _, row in df.head(3).iterrows():
        l = generate_title_card(row, "landscape")
        p = generate_title_card(row, "portrait")
        print(f"  ✓ {l}")
        print(f"  ✓ {p}")
    print("Stage 1 test complete.")
