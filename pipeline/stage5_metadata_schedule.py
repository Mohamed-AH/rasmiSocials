"""Stage 5: Generate metadata (captions, hashtags) and JSON scheduling manifest."""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

import pandas as pd
from pipeline.config import (
    EXCEL_FILE, ENCODED_DIR, METADATA_DIR, PLATFORM_SPECS, SHORT_FORM_PLATFORMS,
)

# Hashtag counts per platform
_HASHTAG_LIMITS = {
    "youtube_full":     20,
    "youtube_shorts":   15,
    "tiktok":           10,
    "instagram_reels":  30,
    "instagram_feed":   30,
    "x_twitter":         5,
    "facebook":         10,
    "snapchat":          5,
}

# Days offset from base date for each platform
_PLATFORM_SCHEDULE_OFFSET = {
    "youtube_full":    (0,  14),   # (day_offset, hour_utc)
    "youtube_shorts":  (1,  16),
    "tiktok":          (2,  12),
    "instagram_reels": (3,  15),
    "instagram_feed":  (3,  17),
    "x_twitter":       (4,  13),
    "facebook":        (5,  18),
    "snapchat":        (6,  11),
}


def _parse_date(date_str):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def generate_hashtags(row, platform):
    series  = str(row.get("SeriesName", ""))
    sheikh  = str(row.get("Sheikh", ""))
    limit   = _HASHTAG_LIMITS.get(platform, 10)

    base = [
        "#إسلام", "#علم", "#محاضرة",
        "#Islam", "#Islamic", "#Knowledge", "#Quran",
    ]

    series_tags = []
    if "البخاري" in series:
        series_tags = ["#صحيح_البخاري", "#Bukhari", "#Hadith", "#السنة"]
    elif "مسلم" in series:
        series_tags = ["#صحيح_مسلم", "#Muslim", "#Hadith"]
    elif "رياض" in series:
        series_tags = ["#رياض_الصالحين", "#RiyadhAlSaliheen"]
    else:
        series_tags = [f"#{series.replace(' ', '_')[:20]}"] if series and series != "nan" else []

    sheikh_tag = []
    if sheikh and sheikh != "nan":
        last = sheikh.strip().split()[-1]
        sheikh_tag = [f"#{last}"]

    platform_extra = {
        "tiktok":          ["#fyp", "#learnislam", "#islamictiktok"],
        "instagram_reels": ["#islamicreels", "#muslimcontent"],
        "youtube_shorts":  ["#shorts", "#islamicshorts"],
        "snapchat":        ["#islamicsnap"],
    }.get(platform, [])

    all_tags = base + series_tags + sheikh_tag + platform_extra
    # Deduplicate preserving order
    seen, unique = set(), []
    for t in all_tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique[:limit]


def generate_caption(row, platform, clip_text=None):
    title_en = str(row.get("TitleEnglish", "Lecture"))
    series   = str(row.get("SeriesName", ""))
    sheikh   = str(row.get("Sheikh", ""))
    seq      = str(row.get("SequenceInSeries", ""))
    date_val = str(row.get("DateInGreg", ""))

    if platform == "youtube_full":
        lines = [
            f"{title_en}",
            "",
            f"Series: {series}" if series and series != "nan" else "",
            f"Lesson: {seq}" if seq and seq != "nan" else "",
            f"Sheikh: {sheikh}" if sheikh and sheikh != "nan" else "",
            f"Date: {date_val}" if date_val and date_val != "nan" else "",
            "",
            "An in-depth Islamic lecture covering key principles drawn from classical scholarship. "
            "This lesson is part of an ongoing series — follow for more.",
            "",
            "⏱ Timestamps and chapters available in the comments.",
        ]
        return "\n".join(l for l in lines if l is not None).strip()

    elif platform in ("youtube_shorts", "tiktok", "instagram_reels", "snapchat"):
        hook = clip_text[:120].strip() if clip_text else title_en
        # Strip TurboScribe watermark if present
        if "TurboScribe" in hook:
            hook = title_en
        return f"🎙️ {hook} | {title_en}"[:220]

    elif platform == "x_twitter":
        return f"{title_en} — {sheikh}"[:220]

    elif platform == "facebook":
        return (
            f"📖 New lecture: {title_en}\n\n"
            f"Sheikh {sheikh} continues the {series} series. "
            f"A valuable lesson for every Muslim — share with family and friends."
        )

    elif platform == "instagram_feed":
        return (
            f"📚 {title_en}\n\n"
            f"Part of the {series} series by Sheikh {sheikh}.\n\n"
            f"💾 Save this post to revisit later."
        )

    return title_en


def _schedule_time(base_date, platform):
    day_offset, hour = _PLATFORM_SCHEDULE_OFFSET.get(platform, (0, 12))
    dt = base_date + timedelta(days=day_offset)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def build_schedule_manifest(excel_df):
    os.makedirs(METADATA_DIR, exist_ok=True)
    all_entries = {}

    for i, (_, row) in enumerate(excel_df.iterrows()):
        sno      = int(row.get("S.No", i + 1))
        date_val = row.get("DateInGreg", None)
        base_dt  = _parse_date(date_val) if date_val else datetime.now(timezone.utc) + timedelta(days=i)

        clips_json_path = os.path.join(METADATA_DIR, f"{sno}_clips.json")
        clips = []
        if os.path.exists(clips_json_path):
            with open(clips_json_path, encoding="utf-8") as f:
                clips = json.load(f)

        entry = {
            "sno":            sno,
            "lecture_title":  str(row.get("TitleEnglish", "")),
            "sheikh":         str(row.get("Sheikh", "")),
            "series":         str(row.get("SeriesName", "")),
            "platforms":      {},
        }

        for platform in PLATFORM_SPECS:
            is_short = platform in SHORT_FORM_PLATFORMS
            tags = generate_hashtags(row, platform)

            if is_short and clips:
                # One entry per clip for short-form platforms
                for clip in clips:
                    rank = clip["rank"]
                    key  = f"{platform}_clip{rank}"
                    file_path = os.path.join(ENCODED_DIR, f"{sno}_{platform}_clip{rank}.mp4")
                    entry["platforms"][key] = {
                        "file":         file_path,
                        "schedule_utc": _schedule_time(
                            base_dt + timedelta(hours=(rank - 1) * 3), platform
                        ),
                        "title":        f"{row.get('TitleEnglish', '')} — Clip {rank}",
                        "caption":      generate_caption(row, platform, clip.get("text")),
                        "hashtags":     tags,
                        "clip_rank":    rank,
                        "clip_duration_sec": clip.get("duration_sec"),
                        "clip_score":   clip.get("score"),
                    }
            else:
                file_path = os.path.join(ENCODED_DIR, f"{sno}_{platform}.mp4")
                entry["platforms"][platform] = {
                    "file":         file_path,
                    "schedule_utc": _schedule_time(base_dt, platform),
                    "title":        str(row.get("TitleEnglish", "")),
                    "caption":      generate_caption(row, platform),
                    "hashtags":     tags,
                }

        per_lecture_path = os.path.join(METADATA_DIR, f"{sno}_schedule.json")
        with open(per_lecture_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

        all_entries[str(sno)] = entry
        print(f"  ✓ Schedule written: {per_lecture_path}")

    master_path = os.path.join(METADATA_DIR, "master_manifest.json")
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Master manifest: {master_path}")
    return all_entries


if __name__ == "__main__":
    df = pd.read_excel(EXCEL_FILE)
    build_schedule_manifest(df)
