"""Stage 4: Encode base videos and clips to per-platform specifications."""

import json
import os
import subprocess
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from pipeline.config import (
    EXCEL_FILE, IMAGES_DIR, BASE_VIDEOS_DIR, CLIPS_DIR,
    ENCODED_DIR, METADATA_DIR, PLATFORM_SPECS, SHORT_FORM_PLATFORMS,
)


def _ffmpeg(cmd, label=""):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed [{label}]:\n{result.stderr[-2000:]}")
    return result


def _build_vf(platform, spec, portrait_bg=None):
    """Return the -vf filter string for the given platform spec."""
    W, H   = spec["width"], spec["height"]
    ratio  = spec["aspect_ratio"]

    if ratio == "9:16":
        if portrait_bg:
            # Use the portrait title card as a blurred background
            # This is handled separately via -i input; return marker
            return "__use_portrait_bg__"
        else:
            return (
                f"split[a][b];"
                f"[a]scale={W}:{H},boxblur=20[bg];"
                f"[b]scale={W}:ih*{W}/iw[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
                f"format=yuv420p"
            )
    elif ratio == "1:1":
        return (
            f"crop=min(iw\\,ih):min(iw\\,ih),"
            f"scale={W}:{H},"
            f"format=yuv420p"
        )
    else:  # 16:9
        return (
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
            f"format=yuv420p"
        )


def encode_video(input_video, platform_name, sno, clip_rank=None):
    os.makedirs(ENCODED_DIR, exist_ok=True)
    spec = PLATFORM_SPECS[platform_name]
    W, H = spec["width"], spec["height"]
    fps  = spec["fps"]
    max_dur = spec.get("max_duration_sec")

    suffix = f"_clip{clip_rank}" if clip_rank is not None else ""
    out_path = os.path.join(ENCODED_DIR, f"{sno}_{platform_name}{suffix}.mp4")

    portrait_bg = os.path.join(IMAGES_DIR, f"{sno}_portrait.png")
    has_portrait = os.path.exists(portrait_bg) and spec["aspect_ratio"] == "9:16"

    if has_portrait:
        # Two-input approach: blurred portrait bg + foreground video
        fg_scale = f"scale={W}:ih*{W}/iw"
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", portrait_bg,
            "-i", input_video,
            "-filter_complex",
            (
                f"[0:v]scale={W}:{H},boxblur=20[bg];"
                f"[1:v]{fg_scale}[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[vout]"
            ),
            "-map", "[vout]",
            "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-r", str(fps),
        ]
    else:
        vf = _build_vf(platform_name, spec)
        cmd = [
            "ffmpeg", "-y",
            "-i", input_video,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-r", str(fps),
        ]

    if max_dur:
        cmd += ["-t", str(max_dur)]

    cmd.append(out_path)
    _ffmpeg(cmd, f"{platform_name}_sno{sno}{suffix}")
    return out_path


def encode_base_video_all_platforms(sno):
    """Encode the base video for all 8 platforms."""
    base = os.path.join(BASE_VIDEOS_DIR, f"{sno}_base.mp4")
    if not os.path.exists(base):
        print(f"  [SKIP] Base video not found: {base}")
        return {}

    results = {}
    for platform in PLATFORM_SPECS:
        print(f"  Encoding {platform} …")
        try:
            path = encode_video(base, platform, sno)
            results[platform] = path
            print(f"  ✓ {path}")
        except RuntimeError as e:
            print(f"  [ERROR] {platform}: {e}")
            results[platform] = None
    return results


def encode_clips_all_platforms(sno):
    """Encode each extracted clip for short-form platforms."""
    clips_json = os.path.join(METADATA_DIR, f"{sno}_clips.json")
    if not os.path.exists(clips_json):
        print(f"  [SKIP] Clips metadata not found: {clips_json}")
        return {}

    with open(clips_json, encoding="utf-8") as f:
        clips = json.load(f)

    base = os.path.join(BASE_VIDEOS_DIR, f"{sno}_base.mp4")
    if not os.path.exists(base):
        print(f"  [SKIP] Base video not found for clip encoding: {base}")
        return {}

    results = {}
    for clip in clips:
        rank      = clip["rank"]
        start_sec = clip["start_ms"] / 1000.0
        dur_sec   = clip["duration_sec"]

        # First cut the raw clip from base video
        os.makedirs(CLIPS_DIR, exist_ok=True)
        raw_clip = os.path.join(CLIPS_DIR, f"{sno}_clip{rank}_raw.mp4")
        _ffmpeg([
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-i", base,
            "-t", str(dur_sec),
            "-c", "copy",
            raw_clip,
        ], f"cut_clip{rank}_sno{sno}")

        results[rank] = {}
        for platform in SHORT_FORM_PLATFORMS:
            print(f"  Encoding clip {rank} → {platform} …")
            try:
                path = encode_video(raw_clip, platform, sno, clip_rank=rank)
                results[rank][platform] = path
                print(f"  ✓ {path}")
            except RuntimeError as e:
                print(f"  [ERROR] clip{rank} {platform}: {e}")
                results[rank][platform] = None

    return results


if __name__ == "__main__":
    df = pd.read_excel(EXCEL_FILE)
    for _, row in df.iterrows():
        sno = int(row["S.No"])
        encode_base_video_all_platforms(sno)
        encode_clips_all_platforms(sno)
