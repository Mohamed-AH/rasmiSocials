"""Stage 2: Assemble full-length base MP4 from title image + M4A audio."""

import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from pipeline.config import EXCEL_FILE, AUDIO_DIR, IMAGES_DIR, BASE_VIDEOS_DIR


def _ffmpeg(cmd, label=""):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed [{label}]:\n{result.stderr[-2000:]}")
    return result


def assemble_base_video(row):
    os.makedirs(BASE_VIDEOS_DIR, exist_ok=True)

    sno       = int(row.get("S.No", 0))
    filename  = str(row.get("TelegramFileName", ""))
    title_en  = str(row.get("TitleEnglish", ""))
    sheikh    = str(row.get("Sheikh", ""))
    series    = str(row.get("SeriesName", ""))
    date_val  = str(row.get("DateInGreg", ""))

    audio_path = os.path.join(AUDIO_DIR, filename)
    image_path = os.path.join(IMAGES_DIR, f"{sno}_landscape.png")
    out_path   = os.path.join(BASE_VIDEOS_DIR, f"{sno}_base.mp4")

    if not os.path.exists(audio_path):
        print(f"  [SKIP] Audio not found: {audio_path}")
        return None
    if not os.path.exists(image_path):
        print(f"  [SKIP] Title image not found: {image_path} — run Stage 1 first")
        return None

    # Ken Burns slow zoom-in over full audio duration
    zoom_filter = (
        "zoompan=z='min(zoom+0.0003,1.05)':d=1"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":s=1920x1080:fps=25,format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-vf", zoom_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-map_metadata", "-1",
        "-metadata", f"title={title_en}",
        "-metadata", f"artist={sheikh}",
        "-metadata", f"album={series}",
        "-metadata", f"date={date_val}",
        out_path,
    ]

    print(f"  Assembling base video for S.No {sno} …")
    _ffmpeg(cmd, f"base_video_sno{sno}")
    print(f"  ✓ {out_path}")
    return out_path


def assemble_all(excel_df):
    results = []
    total = len(excel_df)
    for i, (_, row) in enumerate(excel_df.iterrows(), 1):
        sno = int(row.get("S.No", i))
        print(f"[{i}/{total}] S.No {sno}")
        path = assemble_base_video(row)
        results.append({"sno": sno, "base_video": path})
    return results


if __name__ == "__main__":
    df = pd.read_excel(EXCEL_FILE)
    assemble_all(df)
