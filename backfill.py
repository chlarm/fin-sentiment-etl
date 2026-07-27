#!/usr/bin/env python3
"""
Backfill script — runs the daily ETL for every date in [start_date, end_date].

Usage:
    python backfill.py --start 2026-01-01 --end 2026-03-16

Tip: run inside a tmux / screen session so it keeps going if the terminal closes.
"""
import argparse
import subprocess
import sys
from datetime import date, timedelta
import time

def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end",   default=str(date.today()))
    parser.add_argument("--sleep", type=int, default=5,
                        help="Seconds to wait between each day (default: 5)")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end   = date.fromisoformat(args.end)
    total = (end - start).days + 1

    print(f"=== Backfill: {start} → {end} ({total} days) ===\n")

    for i, d in enumerate(daterange(start, end), 1):
        ds = str(d)
        print(f"[{i}/{total}] Running ETL for {ds} ...", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "src.etl.run_daily", "--date", ds],
            capture_output=False,   # stream output live
        )
        if result.returncode != 0:
            print(f"  ⚠️  ETL for {ds} exited with code {result.returncode} — continuing anyway")
        else:
            print(f"  ✅ Done {ds}")
        if i < total:
            time.sleep(args.sleep)

    print("\n=== Backfill complete! ===")

if __name__ == "__main__":
    main()
