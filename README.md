# rasmiSocials — Automated Islamic Lecture Publishing Pipeline

Turn M4A audio lectures into fully-formatted, platform-ready videos for YouTube, TikTok, Instagram, X, Facebook, and Snapchat — automatically.

---

## What This Pipeline Does

```
Your M4A audio files
      +
Excel sheet (titles, sheikh names, dates)
      +
CSV transcripts (word-by-word timecodes)
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  Stage 1  │  Branded title card images (PNG)        │
│  Stage 2  │  Full-length base video (MP4)           │
│  Stage 3  │  Viral short clips extracted (30–90s)   │
│  Stage 4  │  Encoded for every platform             │
│  Stage 5  │  Captions, hashtags & post schedule     │
└─────────────────────────────────────────────────────┘
      │
      ▼
outputs/encoded/      ← ready-to-upload MP4s
outputs/metadata/     ← captions, hashtags, schedule JSON
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.9+ | [python.org/downloads](https://python.org/downloads) |
| FFmpeg | Any recent | [ffmpeg.org/download](https://ffmpeg.org/download.html) — must be on your PATH |
| pip | Bundled with Python | Used to install libraries |

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Mohamed-AH/rasmiSocials.git
cd rasmiSocials

# 2. Install Python dependencies
pip install -r requirements.txt
```

---

## Input File Layout

```
rasmiSocials/
├── testUpdatedData10June.xlsx      ← your master Excel sheet (already here)
├── inputs/
│   ├── audio/
│   │   ├── AUDIO-2026-02-13-17-49-55.m4a   ← M4A files go here
│   │   ├── AUDIO-2026-04-03-19-40-32.m4a
│   │   └── ...
│   └── transcripts/
│       ├── 1.csv    ← transcript for row S.No = 1
│       ├── 2.csv    ← transcript for row S.No = 2
│       └── ...
```

### Audio files (`inputs/audio/`)
- The filename must **exactly match** the `TelegramFileName` column in the Excel sheet.
- Example: if the Excel cell says `AUDIO-2026-02-13-17-49-55.m4a`, the file must be named identically.

### Transcript CSVs (`inputs/transcripts/`)
- One CSV per lecture, named by its row number in the Excel sheet (`S.No` column).
- Row 1 → `1.csv`, row 2 → `2.csv`, …, row 80 → `80.csv`.
- Each CSV must have exactly three columns:

| Column | Format | Example |
|---|---|---|
| `start` | milliseconds (integer) | `61920` |
| `end` | milliseconds (integer) | `66020` |
| `text` | Arabic transcript text | `مرحبا بكم في محاضرتي` |

- TurboScribe exports match this format directly.

### Excel sheet (`testUpdatedData10June.xlsx`)
Used columns:

| Column | Purpose |
|---|---|
| `S.No` | Row number — links to transcript CSV filename |
| `TelegramFileName` | Links to audio file in `inputs/audio/` |
| `TitleEnglish` | Used on title cards and in post captions |
| `SeriesName` | Arabic series name on title card |
| `SequenceInSeries` | Arabic lesson number on title card |
| `Sheikh` | Speaker name — appears on title card and in metadata |
| `DateInGreg` | Used to schedule posts (format: DD.MM.YYYY) |

---

## Running the Pipeline

### Process a single lecture (recommended for first run)
```bash
python3 pipeline/run_pipeline.py --sno 78
```
Replace `78` with any `S.No` value from your Excel sheet.

### Process all 80 lectures
```bash
python3 pipeline/run_pipeline.py --all
```

### Run only specific stages
```bash
# Stage 1 only — generate title cards (fast, no FFmpeg)
python3 pipeline/run_pipeline.py --all --stages 1

# Stages 1 and 3 only — title cards + clip extraction
python3 pipeline/run_pipeline.py --all --stages 1,3

# Skip FFmpeg encoding (useful for testing metadata)
python3 pipeline/run_pipeline.py --all --skip-encode
```

### Stage reference

| Stage | Name | What it does | Needs FFmpeg? |
|---|---|---|---|
| 1 | Image Generation | Creates branded PNG title cards | No |
| 2 | Base Video Assembly | Combines audio + title card into MP4 | Yes |
| 3 | Clip Extraction | Finds best 30–90s segments from transcript | No |
| 4 | Platform Encoding | Exports video in each platform's exact format | Yes |
| 5 | Metadata & Scheduling | Generates captions, hashtags, schedule JSON | No |

---

## Output Files

```
outputs/
├── images/
│   ├── 1_landscape.png     ← 1920×1080 title card
│   ├── 1_portrait.png      ← 1080×1920 title card (for Shorts etc.)
│   └── ...
├── base_videos/
│   ├── 1_base.mp4          ← full-length video (audio + title card)
│   └── ...
├── clips/
│   ├── 1_clip1_raw.mp4     ← raw cut of best clip #1
│   └── ...
├── encoded/
│   ├── 1_youtube_full.mp4
│   ├── 1_youtube_shorts_clip1.mp4
│   ├── 1_tiktok_clip1.mp4
│   ├── 1_instagram_reels_clip1.mp4
│   ├── 1_instagram_feed.mp4
│   ├── 1_x_twitter.mp4
│   ├── 1_facebook.mp4
│   ├── 1_snapchat_clip1.mp4
│   └── ...
└── metadata/
    ├── 1_clips.json         ← scored clip candidates for lecture 1
    ├── 1_schedule.json      ← full post schedule + captions for lecture 1
    ├── master_manifest.json ← combined manifest for ALL lectures
    └── run_log.json         ← per-lecture status from last run
```

### Platform encoding specifications

| Platform | Resolution | Aspect | Max Duration |
|---|---|---|---|
| YouTube Full | 1920 × 1080 | 16:9 | Unlimited |
| YouTube Shorts | 1080 × 1920 | 9:16 | 60s |
| TikTok | 1080 × 1920 | 9:16 | 10 min |
| Instagram Reels | 1080 × 1920 | 9:16 | 90s |
| Instagram Feed | 1080 × 1080 | 1:1 | 60s |
| X (Twitter) | 1280 × 720 | 16:9 | 140s |
| Facebook | 1280 × 720 | 16:9 | Unlimited |
| Snapchat | 1080 × 1920 | 9:16 | 60s |

---

## Clip Extraction Logic

Stage 3 scores every possible 30–90 second window in the transcript:

| Signal found in window | Score bonus |
|---|---|
| Arabic question mark `؟` | +2.0 |
| Hadith citation (`قال النبي`, `رسول الله`, etc.) | +2.0 |
| Direct address (`اعلموا`, `أنتم`, `انتبه`, etc.) | +1.5 |
| Enumeration (`أولاً`, `ثانياً`, `ثالثاً`, etc.) | +1.5 |
| Word density (per 50 words, max +3.0) | up to +3.0 |

The top 4 non-overlapping clips per lecture are selected.

---

## Scheduling Manifest

`outputs/metadata/master_manifest.json` contains a ready-to-use publishing plan for every lecture across every platform:

```json
{
  "1": {
    "lecture_title": "Sahih al-Bukhari - Lesson 4",
    "sheikh": "الشيخ حسن بن محمد منصور الدغريري",
    "platforms": {
      "youtube_full": {
        "file": "outputs/encoded/1_youtube_full.mp4",
        "schedule_utc": "2026-02-13T14:00:00+00:00",
        "title": "Sahih al-Bukhari - Lesson 4",
        "caption": "...",
        "hashtags": ["#إسلام", "#صحيح_البخاري", "#Bukhari", ...]
      },
      "youtube_shorts_clip1": { ... },
      "tiktok_clip1": { ... }
    }
  }
}
```

This JSON can be fed directly into scheduling tools such as Buffer, Later, or a custom cron job.

---

## Title Card Design

Each title card is generated entirely offline using Python (no internet required):

- **Background:** navy-to-teal vertical gradient
- **Accent:** gold horizontal separator line at 60% height
- **Decoration:** subtle geometric star pattern in corners
- **Text layout:** Series name (Arabic) → Lesson number → English title → Sheikh name → Date
- **Contrast safety:** every text element is checked against WCAG AA (4.5:1 ratio); a semi-transparent dark overlay is automatically painted behind any text that would otherwise be hard to read

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `[SKIP] Audio not found` | Filename mismatch | Check `TelegramFileName` in Excel exactly matches the file in `inputs/audio/` |
| `[SKIP] Transcript not found` | CSV not present or wrong name | Name the CSV after the `S.No` value, e.g. `5.csv` for row 5 |
| `FFmpeg failed` | FFmpeg not installed or not on PATH | Install FFmpeg and verify with `ffmpeg -version` in terminal |
| Arabic text displays as boxes | Font missing | Install `fonts-dejavu` or `fonts-noto-core` on your system |
| `ModuleNotFoundError` | Dependencies not installed | Run `pip install -r requirements.txt` |

---

## Project Structure

```
rasmiSocials/
├── pipeline/
│   ├── config.py                 # paths, platform specs, settings
│   ├── stage1_image_gen.py       # title card generator
│   ├── stage2_base_video.py      # audio + image → MP4
│   ├── stage3_clip_extractor.py  # viral clip scorer
│   ├── stage4_platform_encode.py # per-platform FFmpeg encoder
│   ├── stage5_metadata_schedule.py # captions, hashtags, schedule
│   └── run_pipeline.py           # CLI orchestrator
├── inputs/
│   ├── audio/                    # M4A files (you provide)
│   └── transcripts/              # CSV transcripts (you provide)
├── outputs/                      # all generated files (git-ignored)
├── testUpdatedData10June.xlsx    # master lecture metadata
└── requirements.txt
```
