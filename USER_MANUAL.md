# rasmiSocials — User Manual
### Step-by-Step Guide for Non-Technical Users

---

## Before You Start — What You Need

You need three things on your computer:

1. **Python 3** — the programming language that runs this tool
2. **FFmpeg** — a free video tool used behind the scenes
3. **This project folder** — the `rasmiSocials` folder you already have

---

## PART A — One-Time Setup
*You only do this once, ever.*

---

### Step 1 — Install Python

1. Go to **https://www.python.org/downloads**
2. Click the big yellow **"Download Python"** button
3. Run the installer
4. ⚠️ **Important:** On the first screen of the installer, tick the box that says **"Add Python to PATH"** before clicking Install

To confirm it worked, open a terminal (see Step 3 below for how) and type:
```
python --version
```
You should see something like `Python 3.11.4`. If you do, Python is ready.

---

### Step 2 — Install FFmpeg

**On Windows:**
1. Go to **https://ffmpeg.org/download.html**
2. Click **"Windows builds from gyan.dev"**
3. Download the file named `ffmpeg-release-essentials.zip`
4. Unzip it — you'll get a folder like `ffmpeg-6.0-essentials_build`
5. Inside that folder, open the `bin` folder — you'll see `ffmpeg.exe`
6. Copy the full path to this `bin` folder (e.g. `C:\ffmpeg\bin`)
7. Search Windows for **"Edit the system environment variables"** → click **Environment Variables** → find **Path** → click Edit → click New → paste the path → click OK on everything

**On Mac:**
1. Open Terminal (search for "Terminal" in Spotlight)
2. Type this and press Enter:
   ```
   brew install ffmpeg
   ```
   (If brew is not found, first install it from **https://brew.sh**)

**On Linux (Ubuntu/Debian):**
```
sudo apt install ffmpeg
```

To confirm FFmpeg is ready, type in terminal:
```
ffmpeg -version
```
You should see version information, not an error.

---

### Step 3 — Open a Terminal in the Project Folder

**On Windows:**
1. Open the `rasmiSocials` folder in File Explorer
2. Click in the address bar at the top (where it shows the path)
3. Type `cmd` and press Enter — a black Command Prompt window opens

**On Mac:**
1. Open the `rasmiSocials` folder in Finder
2. Right-click on the folder → **"New Terminal at Folder"**

**On Linux:**
1. Right-click inside the folder → **"Open Terminal"**

---

### Step 4 — Install the Python Libraries

In the terminal you just opened, type this exactly and press Enter:

```
pip install -r requirements.txt
```

You'll see text scrolling — that's normal. Wait until it finishes and you see the prompt again. This only needs to be done once.

---

## PART B — Every Time You Run the Pipeline
*Do this whenever you have new lectures to process.*

---

### Step 5 — Add Your Audio Files

1. Open the `rasmiSocials` folder
2. Go into `inputs` → `audio`
3. Copy your M4A files into this folder

⚠️ **The filenames must match exactly what's in your Excel sheet** (the `TelegramFileName` column). Don't rename the files.

Example — your Excel shows:
```
AUDIO-2026-02-13-17-49-55.m4a
```
The file in `inputs/audio/` must be named exactly that.

---

### Step 6 — Add Your Transcript Files

1. Go into `inputs` → `transcripts`
2. Copy your transcript CSV files here
3. **Rename each file to match its row number** in the Excel sheet (the `S.No` column)

Example: the lecture in row 1 of the Excel sheet → rename its CSV to `1.csv`. Row 5 → `5.csv`. Row 78 → `78.csv`.

Your transcripts folder should look like:
```
inputs/transcripts/
    1.csv
    2.csv
    3.csv
    ...
```

---

### Step 7 — Run the Pipeline

Open a terminal in the `rasmiSocials` folder (same as Step 3).

#### To process ONE lecture (good for testing):
```
python pipeline/run_pipeline.py --sno 1
```
Replace `1` with the row number (`S.No`) of the lecture you want to process.

#### To process ALL lectures:
```
python pipeline/run_pipeline.py --all
```

You'll see progress messages like:
```
Processing S.No 1  [1/80]  Sahih al-Bukhari - Lesson 4
── Stage 1: Image Generation ──
── Stage 2: Base Video Assembly ──
...
```

Wait for it to finish. A long lecture at full quality may take a few minutes per video.

---

### Step 8 — Find Your Output Files

When the pipeline finishes, all your files are in the `outputs` folder:

```
outputs/
│
├── images/              ← title card images (PNG)
│   ├── 1_landscape.png
│   ├── 1_portrait.png
│   └── ...
│
├── encoded/             ← FINAL VIDEOS — ready to upload
│   ├── 1_youtube_full.mp4          ← upload to YouTube
│   ├── 1_youtube_shorts_clip1.mp4  ← upload to YouTube Shorts
│   ├── 1_tiktok_clip1.mp4          ← upload to TikTok
│   ├── 1_instagram_reels_clip1.mp4 ← upload to Instagram Reels
│   ├── 1_instagram_feed.mp4        ← upload to Instagram Feed
│   ├── 1_x_twitter.mp4             ← upload to X (Twitter)
│   ├── 1_facebook.mp4              ← upload to Facebook
│   ├── 1_snapchat_clip1.mp4        ← upload to Snapchat
│   └── ...
│
└── metadata/            ← captions, hashtags, schedule
    ├── 1_schedule.json
    ├── master_manifest.json   ← ALL lectures combined
    └── run_log.json           ← what succeeded / failed
```

---

### Step 9 — Get Captions and Hashtags

Open `outputs/metadata/master_manifest.json` in any text editor (Notepad on Windows, TextEdit on Mac).

For each lecture and platform you'll find:

- **`caption`** — ready-to-paste post text
- **`hashtags`** — list of hashtags to copy into your post
- **`title`** — the video title to use when uploading
- **`schedule_utc`** — the recommended publish time (UTC)

Example entry:
```json
"youtube_shorts_clip1": {
  "file": "outputs/encoded/1_youtube_shorts_clip1.mp4",
  "schedule_utc": "2026-02-14T16:00:00+00:00",
  "title": "Sahih al-Bukhari - Lesson 4 — Clip 1",
  "caption": "🎙️ مرحبا بكم في محاضرتي | Sahih al-Bukhari - Lesson 4",
  "hashtags": ["#إسلام", "#صحيح_البخاري", "#Bukhari", "#Hadith", ...]
}
```

---

## PART C — Tips & Common Issues

---

### "I see [SKIP] Audio not found"

The pipeline couldn't find the M4A file. Check:
- Is the file in `inputs/audio/`? (not a subfolder inside it)
- Does the filename **exactly** match the Excel `TelegramFileName` cell? (including capitalisation and hyphens)

---

### "I see [SKIP] Transcript not found"

The pipeline couldn't find the CSV for that lecture. Check:
- Is it in `inputs/transcripts/`?
- Is it named after the `S.No` number (e.g. `5.csv` for row 5)?

---

### "FFmpeg failed"

FFmpeg either isn't installed or wasn't added to PATH correctly. Redo Step 2, especially the PATH part. Then close and reopen your terminal.

---

### The title card text looks like boxes / squares

Your system is missing a font that supports Arabic. On Windows, Arabic fonts are built in. On Linux, run:
```
sudo apt install fonts-noto fonts-dejavu
```

---

### I want to rerun just the title card stage without re-encoding everything

```
python pipeline/run_pipeline.py --all --stages 1
```

---

### I want to test without waiting for FFmpeg video encoding

```
python pipeline/run_pipeline.py --sno 1 --skip-encode
```
This runs stages 1, 3, and 5 only (images, clip selection, and metadata). Fast, no video files created.

---

### Where do I check what succeeded and what failed?

Open `outputs/metadata/run_log.json`. Each lecture row will show `"status": "ok"` or `"status": "error"` with an error message.

---

## Quick Reference Card

| Task | Command |
|---|---|
| Process one lecture | `python pipeline/run_pipeline.py --sno 5` |
| Process all lectures | `python pipeline/run_pipeline.py --all` |
| Title cards only (fast) | `python pipeline/run_pipeline.py --all --stages 1` |
| Clips + metadata only | `python pipeline/run_pipeline.py --all --stages 3,5` |
| Skip video encoding | `python pipeline/run_pipeline.py --all --skip-encode` |
| Specific stages only | `python pipeline/run_pipeline.py --all --stages 1,2,3` |

---

## Input File Checklist

Before running, confirm:

- [ ] M4A files are in `inputs/audio/`
- [ ] Each M4A filename matches exactly the `TelegramFileName` column in Excel
- [ ] Transcript CSVs are in `inputs/transcripts/`
- [ ] Each transcript CSV is named `{S.No}.csv` (e.g. `1.csv`, `2.csv`)
- [ ] Each transcript CSV has columns: `start`, `end`, `text`
- [ ] Python is installed (`python --version` works in terminal)
- [ ] FFmpeg is installed (`ffmpeg -version` works in terminal)
- [ ] Libraries are installed (`pip install -r requirements.txt` was run)
