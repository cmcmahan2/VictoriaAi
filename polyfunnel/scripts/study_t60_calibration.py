#!/usr/bin/env python3
"""Study: are up/down markets calibrated at T-60s, and does any naive
price-only strategy clear fees? Rerunnable as data grows.

Run:  PYTHONPATH=src python3 scripts/study_t60_calibration.py [--events 200]
Writes findings to stdout; keep conclusions in vault/studies/.

Method: newest settled events for the series, minute-fidelity Up-token
prices-history for each market's final 6 minutes, last price at/before
T-60s and T-240s, official winner from outcomePrices. Honest accounting
notes: entry at history price is OPTIMISTIC (real takers cross the spread);
fee model 0.07*p*(1-p) per share from config/costs.yaml assumptions.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polyfunnel.api.clob import ClobPublic  # noqa: E402
from polyfunnel.api.gamma import GammaClient  # noqa: E402

CRYPTO_TAKER_RATE = 0.07  # live-verified 2026-07-06 (docs/GROUND_TRUTH.md)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - hw, c + hw)


def fetch(series: str, n_events: int) -> list[dict]:
    g, c = GammaClient(), ClobPublic()
    events: list[dict] = []
    off = 0
    while len(events) < n_events:
        page = g.get("/events", limit=100, offset=off, closed="true",
                     series_slug=series, order="endDate", ascending="false")
        if not page:
            break
        events += page
        off += 100
        time.sleep(0.4)
    rows, empty = [], 0
    for ev in events[:n_events]:
        for m in ev.get("markets") or []:
            prices = json.loads(m.get("outcomePrices") or "[]")
            toks = json.loads(m.get("clobTokenIds") or "[]")
            outs = json.loads(m.get("outcomes") or "[]")
            if len(prices) != 2 or len(toks) != 2 or set(prices) != {"1", "0"}:
                continue
            end_ts = int(dt.datetime.fromisoformat(
                m["endDate"].replace("Z", "+00:00")).timestamp())
            try:
                h = c.prices_history(toks[outs.index("Up")],
                                     start_ts=end_ts - 360, end_ts=end_ts,
                                     fidelity=1).get("history", [])
            except Exception:  # noqa: BLE001
                h = []
            if not h:
                empty += 1
                continue

            def px_at(cutoff: int) -> float | None:
                pts = [p for p in h if p["t"] <= end_ts - cutoff]
                return pts[-1]["p"] if pts else None

            rows.append({"slug": m["slug"], "end": end_ts,
                         "up_won": prices[outs.index("Up")] == "1",
                         "p60": px_at(60), "p240": px_at(240)})
            time.sleep(0.35)
    print(f"markets with usable history: {len(rows)} | empty history: {empty}")
    return [r for r in rows if r["p60"] is not None]


def report(rows: list[dict]) -> None:
    print(f"N = {len(rows)}")
    print("\n== Calibration: Up price at T-60s vs realized Up win rate ==")
    edges = [i / 10 for i in range(11)]
    for lo, hi in zip(edges, edges[1:]):
        bs = [r for r in rows if lo <= r["p60"] < (hi if hi < 1 else 1.01)]
        if not bs:
            continue
        k = sum(r["up_won"] for r in bs)
        w = wilson(k, len(bs))
        print(f"  {lo:.1f}-{hi:.1f}: n={len(bs):4d} | won {k/len(bs):.3f} "
              f"| CI [{w[0]:.2f},{w[1]:.2f}]")

    print("\n== Buy favorite at T-60 (taker; entry optimistic, spread NOT charged) ==")
    n = k = 0
    pnl = 0.0
    for r in rows:
        p = r["p60"]
        if abs(p - 0.5) < 0.02:
            continue
        q = p if p > 0.5 else 1 - p
        win = r["up_won"] == (p > 0.5)
        pnl += (1 - q if win else -q) - CRYPTO_TAKER_RATE * q * (1 - q)
        n += 1
        k += win
    if n:
        w = wilson(k, n)
        print(f"  trades={n} | fav won {k/n:.3f} (CI [{w[0]:.2f},{w[1]:.2f}]) "
              f"| avg PnL/share {pnl/n:+.4f}  (subtract ~0.01 spread!)")

    print("\n== Longshot (side priced <=0.15 at T-60) ==")
    ls = [r for r in rows if min(r["p60"], 1 - r["p60"]) <= 0.15]
    if ls:
        k = sum((r["up_won"] if r["p60"] < 0.5 else not r["up_won"]) for r in ls)
        avg = sum(min(r["p60"], 1 - r["p60"]) for r in ls) / len(ls)
        w = wilson(k, len(ls))
        print(f"  n={len(ls)} | implied {avg:.3f} | won {k/len(ls):.3f} "
              f"| CI [{w[0]:.2f},{w[1]:.2f}]")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="btc-up-or-down-5m")
    ap.add_argument("--events", type=int, default=200)
    a = ap.parse_args()
    report(fetch(a.series, a.events))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
