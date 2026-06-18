import glob
import os

ROOT_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS_DIR      = os.path.join(ROOT_DIR, "inputs")
AUDIO_DIR       = os.path.join(INPUTS_DIR, "audio")
TRANSCRIPTS_DIR = os.path.join(INPUTS_DIR, "transcripts")
OUTPUTS_DIR     = os.path.join(ROOT_DIR, "outputs")
IMAGES_DIR      = os.path.join(OUTPUTS_DIR, "images")
BASE_VIDEOS_DIR = os.path.join(OUTPUTS_DIR, "base_videos")
CLIPS_DIR       = os.path.join(OUTPUTS_DIR, "clips")
ENCODED_DIR     = os.path.join(OUTPUTS_DIR, "encoded")
METADATA_DIR    = os.path.join(OUTPUTS_DIR, "metadata")
EXCEL_FILE      = os.path.join(ROOT_DIR, "testUpdatedData10June.xlsx")

# Platform encoding specifications
PLATFORM_SPECS = {
    "youtube_full": {
        "width": 1920, "height": 1080, "aspect_ratio": "16:9",
        "max_duration_sec": None, "fps": 30,
    },
    "youtube_shorts": {
        "width": 1080, "height": 1920, "aspect_ratio": "9:16",
        "max_duration_sec": 60, "fps": 30,
    },
    "tiktok": {
        "width": 1080, "height": 1920, "aspect_ratio": "9:16",
        "max_duration_sec": 600, "fps": 30,
    },
    "instagram_reels": {
        "width": 1080, "height": 1920, "aspect_ratio": "9:16",
        "max_duration_sec": 90, "fps": 30,
    },
    "instagram_feed": {
        "width": 1080, "height": 1080, "aspect_ratio": "1:1",
        "max_duration_sec": 60, "fps": 30,
    },
    "x_twitter": {
        "width": 1280, "height": 720, "aspect_ratio": "16:9",
        "max_duration_sec": 140, "fps": 30,
    },
    "facebook": {
        "width": 1280, "height": 720, "aspect_ratio": "16:9",
        "max_duration_sec": None, "fps": 30,
    },
    "snapchat": {
        "width": 1080, "height": 1920, "aspect_ratio": "9:16",
        "max_duration_sec": 60, "fps": 30,
    },
}

# Clip extraction settings
CLIP_DURATION_MIN = 30   # seconds
CLIP_DURATION_MAX = 90   # seconds
CLIPS_PER_LECTURE = 4

# WCAG AA contrast ratio threshold
CONTRAST_THRESHOLD = 4.5

# Short-form platforms (clips are encoded for these only)
SHORT_FORM_PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels", "snapchat"]


def find_arabic_font(size=48):
    """
    Return an ImageFont that can render Arabic.

    Priority order:
      1. Fonts downloaded into the project fonts/ directory (Noto, Amiri, Cairo …)
      2. Known system font paths
      3. Full recursive system font scan
      4. Pillow default (warns — Arabic may not render)
    """
    from PIL import ImageFont

    # Preferred font filenames in quality order
    PREFERRED_ORDER = [
        "NotoNaskhArabic-Regular.ttf",   # best calligraphic quality
        "NotoSansArabic-Regular.ttf",
        "NotoSansArabic-Bold.ttf",
        "Amiri-Regular.ttf",
        "Cairo-Regular.ttf",
    ]

    # 1. Project fonts/ directory (populated by setup_fonts.py)
    project_fonts_dir = os.path.join(ROOT_DIR, "fonts")
    candidates = [os.path.join(project_fonts_dir, f) for f in PREFERRED_ORDER]

    # 2. Known system paths
    candidates += [
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/Library/Fonts/GeezaPro.ttc",                # macOS built-in Arabic
        "/Library/Fonts/Arial Unicode.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]

    # 3. Dynamic system scan (slower, last resort)
    candidates += glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    candidates += glob.glob(os.path.expanduser("~/.fonts/**/*.ttf"), recursive=True)
    candidates += glob.glob(os.path.expanduser("~/.local/share/fonts/**/*.ttf"), recursive=True)

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    print("[WARN] No TTF font found — falling back to default (Arabic may not render correctly)")
    print("[HINT] Run:  python3 pipeline/setup_fonts.py")
    return ImageFont.load_default()
