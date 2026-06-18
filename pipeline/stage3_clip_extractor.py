"""Stage 3: Rule-based viral clip extraction from timestamped transcripts."""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from pipeline.config import (
    EXCEL_FILE, TRANSCRIPTS_DIR, METADATA_DIR,
    CLIP_DURATION_MIN, CLIP_DURATION_MAX, CLIPS_PER_LECTURE,
)

# Engagement signal word sets
_HADITH_SIGNALS     = ["قال النبي", "رسول الله", "صلى الله عليه", "حدثنا", "روى", "أخرجه"]
_ADDRESS_SIGNALS    = ["أنتم", "اعلموا", "انتبه", "تعلمون", "اسمع", "اسمعوا", "أخي", "إخواني"]
_ENUM_SIGNALS       = ["أولاً", "ثانياً", "ثالثاً", "رابعاً", "أول", "ثاني", "ثالث"]


def _contains_any(text, signals):
    return any(s in text for s in signals)


def score_segment(rows_slice):
    """Score a list of transcript rows as a candidate clip. Returns 0–10 float."""
    text = " ".join(str(r) for r in rows_slice)
    score = 0.0

    if "؟" in text:
        score += 2.0
    if _contains_any(text, _ADDRESS_SIGNALS):
        score += 1.5
    if _contains_any(text, _HADITH_SIGNALS):
        score += 2.0
    if _contains_any(text, _ENUM_SIGNALS):
        score += 1.5

    word_count = len(text.split())
    score += min(word_count / 50.0, 3.0)

    # Penalise if first row looks like a mid-sentence start
    first = str(rows_slice[0]).strip() if rows_slice else ""
    if first and not first[0].isupper() and first[0] not in "،.؟!\"'(":
        score -= 1.0

    return max(0.0, min(10.0, score))


def _overlaps(a_start, a_end, b_start, b_end, threshold=0.5):
    """Return True if two intervals overlap by more than threshold of the shorter."""
    overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
    shorter = min(a_end - a_start, b_end - b_start)
    return shorter > 0 and (overlap / shorter) > threshold


def extract_clips(sno, transcript_df):
    """
    Slide windows of various durations over the transcript, score each,
    return top CLIPS_PER_LECTURE non-overlapping clips.
    """
    os.makedirs(METADATA_DIR, exist_ok=True)

    rows = transcript_df.reset_index(drop=True)
    candidates = []

    # Try window durations in steps
    for target_dur_sec in range(CLIP_DURATION_MIN, CLIP_DURATION_MAX + 1, 15):
        target_dur_ms = target_dur_sec * 1000
        step_ms = 10_000   # 10-second slide step

        # Build a list of (start_ms, end_ms, row_indices) windows
        n = len(rows)
        i = 0
        while i < n:
            w_start_ms = int(rows.at[i, "start"])
            # Find rows that fit within this window
            j = i
            while j < n and int(rows.at[j, "end"]) - w_start_ms <= target_dur_ms:
                j += 1
            if j == i:
                i += 1
                continue
            w_end_ms = int(rows.at[j - 1, "end"])
            dur = (w_end_ms - w_start_ms) / 1000.0
            if CLIP_DURATION_MIN <= dur <= CLIP_DURATION_MAX:
                texts = rows.loc[i:j-1, "text"].tolist()
                s = score_segment(texts)
                candidates.append({
                    "start_ms": w_start_ms,
                    "end_ms":   w_end_ms,
                    "duration_sec": round(dur, 1),
                    "score":    round(s, 2),
                    "text":     " ".join(str(t) for t in texts),
                })
            # Advance by step
            while i < n and int(rows.at[i, "start"]) < w_start_ms + step_ms:
                i += 1

    # Sort by score descending, then pick non-overlapping greedily
    candidates.sort(key=lambda c: c["score"], reverse=True)
    selected = []
    for cand in candidates:
        if len(selected) >= CLIPS_PER_LECTURE:
            break
        overlapped = any(
            _overlaps(cand["start_ms"], cand["end_ms"], s["start_ms"], s["end_ms"])
            for s in selected
        )
        if not overlapped:
            selected.append(cand)

    # Assign ranks
    for rank, clip in enumerate(selected, 1):
        clip["rank"] = rank

    out_path = os.path.join(METADATA_DIR, f"{sno}_clips.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    print(f"  ✓ {len(selected)} clips → {out_path}")
    return selected


def extract_all_clips(excel_df):
    results = {}
    total = len(excel_df)
    for i, (_, row) in enumerate(excel_df.iterrows(), 1):
        sno = int(row.get("S.No", i))
        csv_path = os.path.join(TRANSCRIPTS_DIR, f"{sno}.csv")
        if not os.path.exists(csv_path):
            print(f"  [SKIP] Transcript not found: {csv_path}")
            results[sno] = []
            continue
        print(f"[{i}/{total}] Extracting clips for S.No {sno} …")
        df_t = pd.read_csv(csv_path)
        clips = extract_clips(sno, df_t)
        results[sno] = clips
    return results


if __name__ == "__main__":
    df = pd.read_excel(EXCEL_FILE)
    extract_all_clips(df)
