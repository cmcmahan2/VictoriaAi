"""
macro/history.py — cross-run memory for the /macro-scan tool.

Each macro-scan run saves a compact SNAPSHOT (one JSON per run date) under
macro/history/. Subsequent runs load prior snapshots and compute DELTAS — so the
daily radar stops being amnesiac and can say "10y +5bp w/w, gold made a new high,
VIX +2" and track whether earlier trade ideas are still in force.

This is the persistence + delta engine only. The caller (the /macro-scan command,
or the scheduled remote agent) builds the snapshot dict from the data it pulled and
hands it here. No data is fabricated here; we only store and difference what we're
given.

Snapshot shape (all fields optional except `date`):
{
  "date": "YYYY-MM-DD",
  "levels": {"S&P 500": {"close": 7580.1, "chg_pct": 0.01}, ...},
  "vix": 17.59,
  "curve": {"m3":3.69,"y2":3.98,"y5":4.13,"y10":4.45,"y30":4.99,"s2s10":0.47},
  "sectors_pe":   {"Healthcare": 25.8, ...},
  "sectors_perf": {"Technology": 0.74, ...},
  "regime": "one-line regime call",
  "ideas": [{"name":"Long gold / short USD","conviction":"Med-High","side":"long gold"}]
}

CLI:
  python macro/history.py record --file snap.json   # save a snapshot (or '-' for stdin)
  python macro/history.py report                    # latest + d/d and ~w/w deltas (text)
  python macro/history.py selftest                  # prove the delta math, writes nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

HISTORY_DIR = os.path.join(os.path.dirname(__file__), "history")


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #
def _path_for(date: str) -> str:
    return os.path.join(HISTORY_DIR, f"{date}.json")


def save_snapshot(snap: dict) -> str:
    """Persist one snapshot as macro/history/<date>.json. Returns the path."""
    date = snap.get("date")
    if not date:
        raise ValueError("snapshot needs a 'date' (YYYY-MM-DD)")
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = _path_for(date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)
    return path


def load_all() -> list[dict]:
    """All snapshots, oldest→newest by date."""
    out = []
    for p in glob.glob(os.path.join(HISTORY_DIR, "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            continue
    return sorted(out, key=lambda s: s.get("date", ""))


def _parse(date: str) -> dt.date:
    return dt.date.fromisoformat(date)


def prior_snapshot(today: str) -> dict | None:
    """The most recent snapshot strictly before `today` (day-over-day / last run)."""
    earlier = [s for s in load_all() if s.get("date", "") < today]
    return earlier[-1] if earlier else None


def around_days_ago(today: str, days: int, tol: int = 3) -> dict | None:
    """Snapshot closest to (today - days), within ±tol days (for w/w, m/m)."""
    target = _parse(today) - dt.timedelta(days=days)
    best, best_gap = None, tol + 1
    for s in load_all():
        d = s.get("date")
        if not d or d >= today:
            continue
        gap = abs((_parse(d) - target).days)
        if gap <= tol and gap < best_gap:
            best, best_gap = s, gap
    return best


# --------------------------------------------------------------------------- #
# Deltas
# --------------------------------------------------------------------------- #
def _close(snap: dict, name: str) -> float | None:
    lv = (snap.get("levels") or {}).get(name)
    return lv.get("close") if isinstance(lv, dict) else None


def _pct(now: float | None, was: float | None) -> str | None:
    if now is None or was is None or was == 0:
        return None
    return f"{(now - was) / was * 100:+.1f}%"


def _bp(now: float | None, was: float | None) -> str | None:
    if now is None or was is None:
        return None
    return f"{(now - was) * 100:+.0f}bp"  # yields are in %, ×100 → basis points


def _pts(now: float | None, was: float | None, dp: int = 1) -> str | None:
    if now is None or was is None:
        return None
    return f"{now - was:+.{dp}f}"


def compute_deltas(today: dict, prior: dict) -> list[str]:
    """Human-readable change lines for the headline macro series, prior→today."""
    lines: list[str] = []

    def add(label: str, s: str | None, suffix: str = ""):
        if s is not None:
            lines.append(f"{label} {s}{suffix}")

    # equities / risk assets — percent
    add("S&P", _pct(_close(today, "S&P 500"), _close(prior, "S&P 500")))
    add("Nasdaq", _pct(_close(today, "Nasdaq 100"), _close(prior, "Nasdaq 100")))
    add("Gold", _pct(_close(today, "Gold"), _close(prior, "Gold")))
    add("WTI", _pct(_close(today, "WTI Crude"), _close(prior, "WTI Crude")))
    add("BTC", _pct(_close(today, "Bitcoin"), _close(prior, "Bitcoin")))
    # vix — points
    add("VIX", _pts(today.get("vix"), prior.get("vix")))
    # dollar — points (DXY)
    add("DXY", _pts(_close(today, "US Dollar Index"), _close(prior, "US Dollar Index"), 2))
    # rates — basis points
    tc, pc = today.get("curve") or {}, prior.get("curve") or {}
    add("10y", _bp(tc.get("y10"), pc.get("y10")))
    add("2s10s", _bp(tc.get("s2s10"), pc.get("s2s10")))
    return lines


def track_ideas(prior: dict | None) -> list[str]:
    """Echo the prior run's trade ideas so the new run can mark them held/changed."""
    if not prior:
        return []
    out = []
    for it in prior.get("ideas") or []:
        nm = it.get("name", "?")
        cv = it.get("conviction", "")
        out.append(f"{nm}" + (f" ({cv})" if cv else ""))
    return out


# --------------------------------------------------------------------------- #
# Report (text the model can fold into the brief)
# --------------------------------------------------------------------------- #
def report(today_date: str | None = None) -> str:
    snaps = load_all()
    if not snaps:
        return "MEMORY: no prior snapshots — this is the first recorded run."
    today_date = today_date or snaps[-1]["date"]
    today = next((s for s in snaps if s["date"] == today_date), snaps[-1])

    prior = prior_snapshot(today_date)
    wow = around_days_ago(today_date, 7)

    lines = [f"MEMORY: {len(snaps)} snapshot(s) on file (through {snaps[-1]['date']})."]
    if not prior:
        lines.append("No earlier snapshot yet — deltas begin next run.")
        return "\n".join(lines)

    dd = compute_deltas(today, prior)
    lines.append(f"Delta vs last run ({prior['date']}): " + (", ".join(dd) if dd else "n/a"))
    if wow and wow["date"] != prior["date"]:
        ww = compute_deltas(today, wow)
        if ww:
            lines.append(f"Delta vs ~1wk ({wow['date']}): " + ", ".join(ww))
    held = track_ideas(prior)
    if held:
        lines.append("Prior ideas to re-assess (still on? thesis intact?): "
                     + "; ".join(held))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _selftest() -> None:
    prior = {
        "date": "2026-05-25",
        "levels": {"S&P 500": {"close": 7500.0}, "Gold": {"close": 4400.0},
                   "Bitcoin": {"close": 70000.0}, "US Dollar Index": {"close": 99.5}},
        "vix": 15.0,
        "curve": {"y10": 4.40, "s2s10": 0.40},
        "ideas": [{"name": "Curve steepener", "conviction": "High"}],
    }
    today = {
        "date": "2026-06-01",
        "levels": {"S&P 500": {"close": 7580.1}, "Gold": {"close": 4535.0},
                   "Bitcoin": {"close": 72922.0}, "US Dollar Index": {"close": 98.92}},
        "vix": 17.59,
        "curve": {"y10": 4.45, "s2s10": 0.47},
    }
    print("deltas prior->today:")
    for l in compute_deltas(today, prior):
        print("  -", l)
    print("prior ideas:", track_ideas(prior))
    # expected: S&P +1.1%, Gold +3.1%, BTC +4.2%, VIX +2.6, DXY -0.58, 10y +5bp, 2s10s +7bp


def main() -> None:
    ap = argparse.ArgumentParser(description="macro-scan cross-run memory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="save a snapshot JSON")
    r.add_argument("--file", default="-", help="path to snapshot JSON, or '-' for stdin")
    sub.add_parser("report", help="print latest + deltas")
    sub.add_parser("selftest", help="prove the delta math (writes nothing)")
    args = ap.parse_args()

    if args.cmd == "record":
        raw = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        path = save_snapshot(json.loads(raw))
        print(f"saved {path}")
    elif args.cmd == "report":
        print(report())
    elif args.cmd == "selftest":
        _selftest()


if __name__ == "__main__":
    main()
