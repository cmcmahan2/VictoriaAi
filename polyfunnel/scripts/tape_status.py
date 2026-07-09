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


def last_row_ts(path: Path) -> float | None:
    """Timestamp of the last VALID row — scans lines from the end so a torn
    final line (killed mid-write) or trailing blank doesn't hide a live feed."""
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            lines = f.read().splitlines()
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            row = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        ts = row.get("ts") or row.get("recv_ts")
        if ts:
            return ts
    return None


def newest_row_age(day_dirs: list[Path], prefix: str) -> float | None:
    # Only plain .ndjson holds the current (open) hour; .gz are closed hours.
    files = sorted(f for d in day_dirs for f in d.glob(f"{prefix}*.ndjson"))
    if not files:
        return None
    ts = last_row_ts(files[-1])
    return time.time() - ts if ts else None


def fmt_size(nbytes: int) -> str:
    if nbytes >= 1e6:
        return f"{nbytes / 1e6:,.0f} MB"
    if nbytes >= 1e3:
        return f"{nbytes / 1e3:,.0f} KB"
    return f"{nbytes} B"


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
        total_bytes = 0
        for day in day_dirs:
            files = sorted(day.glob("*.ndjson*"))
            nbytes = sum(f.stat().st_size for f in files)
            total_bytes += nbytes
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
            print(f"  {day.name}: {len(files)} files, {fmt_size(nbytes)}"
                  + (f"  ({', '.join(extras)})" if extras else ""))
        # freshness: books-* for the updown collector, prices-* for rtds.
        # NB: `any(d.glob(...))` is always True (generators are truthy) — must
        # test that a file actually matches, or rtds gets the wrong prefix.
        has_books = any(True for d in day_dirs for _ in d.glob("books-*"))
        prefix = "books-" if has_books else "prices-"
        print(f"  total: {fmt_size(total_bytes)} | newest row: "
              f"{fmt_age(newest_row_age(day_dirs, prefix))}")
    print("\n(LIVE = a row landed in the last 2 minutes. If a stream says "
          "STALLED/NOT RECORDING,\n restart that collector window: "
          "python scripts\\collect_updown.py or collect_rtds.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
