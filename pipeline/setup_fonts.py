"""
Font setup script for rasmiSocials.

Run once before using the pipeline:
    python3 pipeline/setup_fonts.py

Strategy (tried in order until at least one Arabic font is confirmed):
  1. Detect fonts already present on the system via fontconfig / file search
  2. Install via apt-get (Linux with apt)
  3. Download directly from Google Fonts GitHub releases (no API key needed)
  4. Download from jsDelivr CDN mirror (fallback)
  5. Warn clearly if everything fails

Fonts targeted (best → acceptable):
  - Noto Naskh Arabic       — best Arabic calligraphic quality, Google Fonts
  - Noto Sans Arabic        — clean sans-serif Arabic, Google Fonts
  - Amiri                   — traditional Arabic book font, Google Fonts
  - Cairo                   — modern Arabic/Latin, Google Fonts
  - DejaVu Sans             — already on most Linux systems, partial Arabic
"""

import glob
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import urllib.error

# ── Constants ────────────────────────────────────────────────────────────────

FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fonts",
)

# Each entry: (display_name, local_filename, direct_download_urls)
# URLs tried top-to-bottom; first that returns 200 wins.
FONT_TARGETS = [
    (
        "Noto Naskh Arabic",
        "NotoNaskhArabic-Regular.ttf",
        [
            "https://github.com/google/fonts/raw/main/ofl/notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf",
            "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf",
            # Static fallback (older repo layout)
            "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf",
            "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoNaskhArabic/NotoNaskhArabic-Regular.ttf",
        ],
    ),
    (
        "Noto Sans Arabic",
        "NotoSansArabic-Regular.ttf",
        [
            "https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf",
            "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf",
            "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf",
            "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSansArabic/NotoSansArabic-Regular.ttf",
        ],
    ),
    (
        "Amiri",
        "Amiri-Regular.ttf",
        [
            "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf",
            "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/amiri/Amiri-Regular.ttf",
        ],
    ),
    (
        "Cairo",
        "Cairo-Regular.ttf",
        [
            "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf",
            "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf",
        ],
    ),
    (
        "Noto Sans Arabic Bold",
        "NotoSansArabic-Bold.ttf",
        [
            "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansArabic/NotoSansArabic-Bold.ttf",
            "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSansArabic/NotoSansArabic-Bold.ttf",
        ],
    ),
]

# Known system paths where each font may already exist
SYSTEM_SEARCH_ROOTS = [
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
    "/Library/Fonts",                           # macOS system
    os.path.expanduser("~/Library/Fonts"),      # macOS user
    "C:\\Windows\\Fonts",                       # Windows
]

# Exact word/token matches to identify Arabic-capable fonts during system scan.
# We split the filename on common separators and check for exact token presence
# to avoid false positives like "freemono" matching "reem".
ARABIC_FONT_TOKENS = {
    "noto", "arabic", "amiri", "cairo", "scheherazade",
    "lateef", "harmattan", "reem", "mirza", "rakkas",
    "aref", "mada", "tajawal", "almarai", "changa",
    "markazi", "jomhuria", "katibeh", "kufam", "lalezar",
    "lemonada", "marhey", "naskh", "nastaliq", "jali",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print(msg, level="info"):
    prefix = {"info": "  ", "ok": "  ✓", "warn": "  ⚠", "error": "  ✗", "head": "\n─"}
    print(f"{prefix.get(level,'  ')} {msg}")


def _scan_system_fonts():
    """Return list of .ttf/.otf paths found on the system."""
    found = []
    for root in SYSTEM_SEARCH_ROOTS:
        if os.path.isdir(root):
            found += glob.glob(os.path.join(root, "**", "*.ttf"), recursive=True)
            found += glob.glob(os.path.join(root, "**", "*.otf"), recursive=True)
    # Also check fonts/ dir inside the project
    found += glob.glob(os.path.join(FONTS_DIR, "*.ttf"))
    found += glob.glob(os.path.join(FONTS_DIR, "*.otf"))
    return found


def _is_arabic_font(path):
    """
    Check for Arabic font by tokenising the filename (split on hyphens,
    underscores, spaces, and CamelCase boundaries) and matching whole tokens.
    This prevents 'freemono' from matching 'reem', etc.
    """
    import re
    name = os.path.basename(path)
    name = os.path.splitext(name)[0]                    # strip extension
    # Split on non-alpha runs AND CamelCase boundaries
    tokens = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    tokens = re.split(r"[^a-zA-Z]+", tokens)
    tokens_lower = {t.lower() for t in tokens if t}
    return bool(tokens_lower & ARABIC_FONT_TOKENS)


def _verify_renders_arabic(font_path):
    """Quick Pillow render test — returns True if Arabic text renders without tofu boxes."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import arabic_reshaper
        from bidi.algorithm import get_display

        font  = ImageFont.truetype(font_path, 32)
        text  = get_display(arabic_reshaper.reshape("صحيح البخاري"))
        img   = Image.new("RGB", (400, 60), (0, 0, 0))
        draw  = ImageDraw.Draw(img)
        draw.text((10, 10), text, font=font, fill=(255, 255, 255))

        # Simple heuristic: if more than 80% of pixels are black the font likely
        # didn't render anything (all tofu / missing glyphs)
        pixels = list(img.convert("L").tobytes())
        non_black = sum(1 for p in pixels if p > 20)
        return non_black > len(pixels) * 0.03   # at least 3% non-black

    except Exception:
        return False


def _try_apt_install():
    """Try to install fonts-noto-core via apt (Linux only)."""
    if platform.system() != "Linux":
        return False
    if not shutil.which("apt-get"):
        return False
    _print("Trying apt-get install fonts-noto-core …", "info")
    try:
        result = subprocess.run(
            ["apt-get", "install", "-y", "--no-install-recommends", "fonts-noto-core"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            subprocess.run(["fc-cache", "-fv"], capture_output=True, timeout=30)
            _print("fonts-noto-core installed via apt", "ok")
            return True
        else:
            _print(f"apt-get failed (may need sudo): {result.stderr.strip()[-200:]}", "warn")
            return False
    except Exception as e:
        _print(f"apt-get exception: {e}", "warn")
        return False


def _download_font(display_name, filename, urls):
    """Download the first reachable URL into FONTS_DIR. Returns path or None."""
    os.makedirs(FONTS_DIR, exist_ok=True)
    dest = os.path.join(FONTS_DIR, filename)

    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        _print(f"{display_name} already in fonts/ dir", "ok")
        return dest

    for url in urls:
        try:
            _print(f"Downloading {display_name} …")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "rasmiSocials-font-setup/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if len(data) < 10_000:
                _print(f"  Response too small ({len(data)} bytes), skipping", "warn")
                continue
            with open(dest, "wb") as f:
                f.write(data)
            _print(f"{display_name} → fonts/{filename}", "ok")
            return dest
        except urllib.error.HTTPError as e:
            _print(f"  HTTP {e.code} for {url}", "warn")
        except urllib.error.URLError as e:
            _print(f"  Network error: {e.reason}", "warn")
        except Exception as e:
            _print(f"  Error: {e}", "warn")

    _print(f"Could not download {display_name}", "error")
    return None


def _show_project_fonts():
    """List fonts currently in the project fonts/ directory."""
    fonts = (
        glob.glob(os.path.join(FONTS_DIR, "*.ttf")) +
        glob.glob(os.path.join(FONTS_DIR, "*.otf"))
    )
    if fonts:
        _print(f"Project fonts/ contains {len(fonts)} font file(s):")
        for f in sorted(fonts):
            _print(f"  {os.path.basename(f)}", "ok")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    _print("rasmiSocials Font Setup", "head")
    _print("─" * 50)

    # ── Step 1: scan system ───────────────────────────────────────────────────
    _print("Scanning system fonts …", "head")
    system_fonts = _scan_system_fonts()
    arabic_system = [f for f in system_fonts if _is_arabic_font(f)]

    if arabic_system:
        _print(f"Found {len(arabic_system)} Arabic-capable font(s) on system:")
        for f in arabic_system[:8]:
            renders = _verify_renders_arabic(f)
            tag = "✓ renders" if renders else "? uncertain"
            _print(f"  [{tag}]  {f}")
        if len(arabic_system) > 8:
            _print(f"  … and {len(arabic_system) - 8} more")
    else:
        _print("No Arabic fonts detected on system", "warn")

    # Check if any of them actually render Arabic correctly
    good_system = [f for f in arabic_system if _verify_renders_arabic(f)]

    # ── Step 2: check project fonts/ dir ────────────────────────────────────
    _print("Checking project fonts/ directory …", "head")
    project_fonts = (
        glob.glob(os.path.join(FONTS_DIR, "*.ttf")) +
        glob.glob(os.path.join(FONTS_DIR, "*.otf"))
    )
    good_project = [f for f in project_fonts if _verify_renders_arabic(f)]

    if good_project:
        _print(f"Project fonts/ already has {len(good_project)} working Arabic font(s):")
        for f in good_project:
            _print(f"  {os.path.basename(f)}", "ok")

    # ── Decision: do we need to fetch anything? ───────────────────────────────
    # "Preferred" fonts are purpose-built Arabic fonts (Noto, Amiri, Cairo).
    # FreeFont / DejaVu can render Arabic but are not ideal for title cards.
    PREFERRED_NAMES = {"noto", "amiri", "cairo", "scheherazade", "lateef",
                       "harmattan", "tajawal", "almarai", "reem"}

    def _is_preferred(path):
        import re
        name = os.path.splitext(os.path.basename(path))[0]
        tokens = {t.lower() for t in re.split(r"[^a-zA-Z]+", name) if t}
        return bool(tokens & PREFERRED_NAMES)

    has_preferred = any(_is_preferred(f) for f in good_system + good_project)

    if has_preferred:
        _print("High-quality Arabic font already present — no downloads needed.", "head")
    elif good_system or good_project:
        _print("Basic Arabic rendering available but higher-quality fonts are preferred.", "head")
        _print("Attempting to obtain Noto / Amiri for better title card quality …")
    else:
        _print("No working Arabic font found — will attempt to obtain one.", "head")

    # ── Step 3: try apt (always attempt if preferred fonts are missing) ───────
    if not has_preferred:
        apt_ok = _try_apt_install()
        if apt_ok:
            system_fonts = _scan_system_fonts()
            new_good = [f for f in system_fonts if _is_arabic_font(f) and _verify_renders_arabic(f)]
            for f in new_good:
                if f not in good_system:
                    good_system.append(f)
            has_preferred = any(_is_preferred(f) for f in good_system)

    # ── Step 4: download from Google Fonts if preferred still missing ─────────
    if not has_preferred:
        _print("Downloading fonts from Google Fonts …", "head")
        for name, filename, urls in FONT_TARGETS:
            dest = _download_font(name, filename, urls)
            if dest and _verify_renders_arabic(dest):
                _print(f"{name} renders Arabic correctly", "ok")
                if dest not in good_project:
                    good_project.append(dest)
            elif dest:
                _print(f"{name} downloaded but Arabic rendering uncertain "
                       "(may still work at runtime)", "warn")
                if dest not in good_project:
                    good_project.append(dest)

    # ── Step 5: show project fonts summary ────────────────────────────────────
    _show_project_fonts()

    # ── Summary ───────────────────────────────────────────────────────────────
    _print("Summary", "head")
    _print("─" * 50)
    all_confirmed = good_project + good_system
    if all_confirmed:
        _print(f"{len(all_confirmed)} working Arabic font(s) available.", "ok")
        _print("You can now run the pipeline:")
        _print("  python3 pipeline/run_pipeline.py --all --stages 1")
    else:
        _print("No confirmed Arabic font could be obtained.", "error")
        _print("Manual fix options:", "warn")
        _print("  Ubuntu/Debian : sudo apt install fonts-noto-core")
        _print("  macOS         : brew install font-noto-sans-arabic")
        _print("  Windows       : Download from fonts.google.com/noto")
        _print("  Any platform  : Place any Arabic .ttf in the fonts/ folder")
        sys.exit(1)

    # ── Quick render preview ──────────────────────────────────────────────────
    best = all_confirmed[0] if all_confirmed else None
    if best:
        try:
            from PIL import Image, ImageDraw, ImageFont
            import arabic_reshaper
            from bidi.algorithm import get_display

            preview_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "outputs", "images", "font_preview.png"
            )
            os.makedirs(os.path.dirname(preview_path), exist_ok=True)

            img  = Image.new("RGB", (900, 180), (12, 22, 50))
            draw = ImageDraw.Draw(img)

            samples = [
                ("صحيح البخاري", 52),
                ("الشيخ حسن بن محمد منصور الدغريري", 34),
                ("١٤٤٨ - ١ - ٢ هـ", 28),
            ]
            y = 12
            for text, size in samples:
                try:
                    font = ImageFont.truetype(best, size)
                except Exception:
                    font = ImageFont.load_default()
                shaped = get_display(arabic_reshaper.reshape(text))
                draw.text((20, y), shaped, font=font, fill=(201, 168, 76))
                y += size + 14

            img.save(preview_path)
            _print(f"Render preview saved → outputs/images/font_preview.png", "ok")
        except Exception as e:
            _print(f"Preview generation skipped: {e}", "warn")


if __name__ == "__main__":
    run()
