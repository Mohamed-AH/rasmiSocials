"""
Orchestrator — run the full rasmiSocials pipeline.

Usage:
  python pipeline/run_pipeline.py --all
  python pipeline/run_pipeline.py --sno 1
  python pipeline/run_pipeline.py --sno 1 --stages 1,2,3
  python pipeline/run_pipeline.py --sno 1 --skip-encode
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from pipeline.config import EXCEL_FILE, METADATA_DIR


def _stage_label(n):
    return {
        1: "Image Generation",
        2: "Base Video Assembly",
        3: "Clip Extraction",
        4: "Platform Encoding",
        5: "Metadata & Scheduling",
    }.get(n, f"Stage {n}")


def process_lecture(row, stages, skip_encode):
    sno = int(row.get("S.No", 0))
    results = {"sno": sno, "stages": {}}

    if 1 in stages:
        t0 = time.time()
        print(f"\n── Stage 1: {_stage_label(1)} ──")
        from pipeline.stage1_image_gen import generate_title_card
        land = generate_title_card(row, "landscape")
        port = generate_title_card(row, "portrait")
        results["stages"]["1"] = {"landscape": land, "portrait": port,
                                  "elapsed_sec": round(time.time() - t0, 1)}

    if 2 in stages and not skip_encode:
        t0 = time.time()
        print(f"\n── Stage 2: {_stage_label(2)} ──")
        from pipeline.stage2_base_video import assemble_base_video
        path = assemble_base_video(row)
        results["stages"]["2"] = {"base_video": path,
                                  "elapsed_sec": round(time.time() - t0, 1)}

    if 3 in stages:
        t0 = time.time()
        print(f"\n── Stage 3: {_stage_label(3)} ──")
        import os as _os
        from pipeline.config import TRANSCRIPTS_DIR
        csv_path = _os.path.join(TRANSCRIPTS_DIR, f"{sno}.csv")
        if _os.path.exists(csv_path):
            from pipeline.stage3_clip_extractor import extract_clips
            df_t = pd.read_csv(csv_path)
            clips = extract_clips(sno, df_t)
            results["stages"]["3"] = {"clips_found": len(clips),
                                      "elapsed_sec": round(time.time() - t0, 1)}
        else:
            print(f"  [SKIP] No transcript at {csv_path}")
            results["stages"]["3"] = {"skipped": True}

    if 4 in stages and not skip_encode:
        t0 = time.time()
        print(f"\n── Stage 4: {_stage_label(4)} ──")
        from pipeline.stage4_platform_encode import (
            encode_base_video_all_platforms, encode_clips_all_platforms
        )
        encode_base_video_all_platforms(sno)
        encode_clips_all_platforms(sno)
        results["stages"]["4"] = {"elapsed_sec": round(time.time() - t0, 1)}

    if 5 in stages:
        t0 = time.time()
        print(f"\n── Stage 5: {_stage_label(5)} ──")
        from pipeline.stage5_metadata_schedule import build_schedule_manifest
        build_schedule_manifest(pd.DataFrame([row]))
        results["stages"]["5"] = {"elapsed_sec": round(time.time() - t0, 1)}

    return results


def main():
    parser = argparse.ArgumentParser(description="rasmiSocials pipeline orchestrator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all",  action="store_true", help="Process all lectures")
    group.add_argument("--sno",  type=int,            help="Process a single lecture by S.No")

    parser.add_argument("--stages",      default="1,2,3,4,5",
                        help="Comma-separated stage numbers to run (default: all)")
    parser.add_argument("--skip-encode", action="store_true",
                        help="Skip FFmpeg-heavy stages 2 and 4")
    args = parser.parse_args()

    stages = set(int(s.strip()) for s in args.stages.split(","))

    df = pd.read_excel(EXCEL_FILE)

    if args.sno:
        rows = df[df["S.No"] == args.sno]
        if rows.empty:
            print(f"[ERROR] S.No {args.sno} not found in Excel.")
            sys.exit(1)
        target_rows = [rows.iloc[0]]
    else:
        target_rows = [row for _, row in df.iterrows()]

    total      = len(target_rows)
    run_log    = {}
    clips_total = 0
    encoded_total = 0
    t_overall  = time.time()

    for idx, row in enumerate(target_rows, 1):
        sno = int(row.get("S.No", idx))
        print(f"\n{'='*60}")
        print(f"Processing S.No {sno}  [{idx}/{total}]  {row.get('TitleEnglish','')}")
        print(f"{'='*60}")
        t_lecture = time.time()
        try:
            result = process_lecture(row, stages, args.skip_encode)
            result["status"] = "ok"
            result["elapsed_sec"] = round(time.time() - t_lecture, 1)
            clips_total   += result.get("stages", {}).get("3", {}).get("clips_found", 0)
            encoded_total += 1 if "4" in result.get("stages", {}) else 0
        except Exception as exc:
            print(f"  [ERROR] S.No {sno}: {exc}")
            result = {"sno": sno, "status": "error", "error": str(exc)}
        run_log[str(sno)] = result

    os.makedirs(METADATA_DIR, exist_ok=True)
    log_path = os.path.join(METADATA_DIR, "run_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(run_log, f, ensure_ascii=False, indent=2)

    elapsed = round(time.time() - t_overall, 1)
    ok_count  = sum(1 for v in run_log.values() if v.get("status") == "ok")
    err_count = total - ok_count

    print(f"\n{'='*60}")
    print(f"Pipeline complete in {elapsed}s")
    print(f"  Lectures processed : {ok_count}/{total}")
    print(f"  Errors             : {err_count}")
    print(f"  Clips extracted    : {clips_total}")
    print(f"  Platform encodes   : {encoded_total}")
    print(f"  Run log            : {log_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
