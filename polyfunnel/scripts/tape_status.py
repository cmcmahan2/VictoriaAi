#!/usr/bin/env python3
"""How much tape do we have? One-command health check for the collectors.

Run:  python3 scripts/tape_status.py
Reads data/collect/ and reports, per stream and per day: file count, size,
row counts for the small files, and how fresh the newest row is — so you can
tell at a glance whether recording is LIVE or has stalled. Stdlib-only.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "collect"
LIVE_THRESHOLD_S = 120  # newest row older than this => something is stalled


def last_line(path: Path) -> str | None:
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 16384))
            lines = f.read().splitlines()
            return lines[-1].decode("utf-8", "replace") if lines else None
    except OSError:
        return None


def newest_row_age(day_dirs: list[Path], prefix: str) -> float | None:
    files = sorted(f for d in day_dirs for f in d.glob(f"{prefix}*.ndjson"))
    if not files:
        return None
    line = last_line(files[-1])
    if not line:
        return None
    try:
        row = json.loads(line)
    except ValueError:
        return None
    ts = row.get("ts") or row.get("recv_ts")
    return time.time() - ts if ts else None


def fmt_age(age: float | None) -> str:
    if age is None:
        return "no rows found"
    if age < LIVE_THRESHOLD_S:
        return f"{age:.0f}s ago  -> RECORDING LIVE"
    if age < 3600:
        return f"{age/60:.0f} min ago  -> STALLED? check the window"
    return f"{age/3600:.1f} h ago  -> NOT RECORDING"


def main() -> int:
    print(f"TAPE STATUS  {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%S} UTC")
    if not BASE.exists():
        print(f"  {BASE} does not exist — no data collected on this machine yet.")
        return 1
    streams = sorted(p for p in BASE.iterdir() if p.is_dir())
    if not streams:
        print("  no streams found.")
        return 1
    for stream in streams:
        day_dirs = sorted(p for p in stream.iterdir() if p.is_dir())
        print(f"\n{stream.name}:")
        total_mb = 0.0
        for day in day_dirs:
            files = sorted(day.glob("*.ndjson*"))
            mb = sum(f.stat().st_size for f in files) / 1e6
            total_mb += mb
            extras = []
            outcomes = day / "outcomes.ndjson"
            if outcomes.exists():
                rows = [json.loads(l) for l in outcomes.open()]
                settled = sum(1 for r in rows if r.get("settled"))
                extras.append(f"outcomes: {settled} settled"
                              + (f" / {len(rows)-settled} provisional"
                                 if len(rows) > settled else ""))
            meta = day / "meta.ndjson"
            if meta.exists():
                extras.append(f"markets: {sum(1 for _ in meta.open())}")
            print(f"  {day.name}: {len(files)} files, {mb:,.0f} MB"
                  + (f"  ({', '.join(extras)})" if extras else ""))
        # freshness: books-* for the updown collector, prices-* for rtds
        prefix = "books-" if any(
            d.glob("books-*") for d in day_dirs) else "prices-"
        print(f"  total: {total_mb:,.0f} MB | newest row: "
              f"{fmt_age(newest_row_age(day_dirs, prefix))}")
    print("\n(LIVE = a row landed in the last 2 minutes. If a stream says "
          "STALLED/NOT RECORDING,\n restart that collector window: "
          "python scripts\\collect_updown.py or collect_rtds.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
