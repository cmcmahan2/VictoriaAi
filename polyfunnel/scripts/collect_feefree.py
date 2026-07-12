#!/usr/bin/env python3
"""Phase 1 collector #3: fee-free segment books + outcomes.

Run:  PYTHONPATH=src python3 scripts/collect_feefree.py [--top 60]

Records the live order books of the top fee-free markets (feesEnabled=false
— the segment with no taker-fee wall) plus their eventual resolutions, for
the F1/F3 strategy tests in vault/STRATEGY-feefree.md. These markets move
on news over hours, so cadence is gentle: books every 20s (hash-deduped,
5-min heartbeat rows keep gaps provable), discovery every 30 min, outcome
sweep every hour. Storage: same NDJSON layout as collect_updown, under
data/collect/feefree/. Runs happily alongside the other collectors.

Only the first (YES) token's book is recorded — the NO book is its economic
mirror on the CLOB; halving the poll keeps us polite.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from collect_updown import SeriesWriter, iso, utcnow  # noqa: E402
from polyfunnel.api.clob import ClobPublic  # noqa: E402
from polyfunnel.api.gamma import GammaClient  # noqa: E402

DISCOVER_EVERY_S = 30 * 60
POLL_EVERY_S = 20.0
HEARTBEAT_ROW_S = 300
OUTCOME_SWEEP_S = 60 * 60
MIN_VOL24 = 5_000
BATCH = 20
MAX_CONSEC_FAILURES = 30


class FeeFreeCollector:
    def __init__(self, top_n: int, data_dir: Path):
        self.gamma, self.clob = GammaClient(), ClobPublic()
        self.top_n = top_n
        self.writer = SeriesWriter(data_dir, "feefree")
        self.tracked: dict[str, dict] = {}   # slug -> {token, question, end}
        self.meta_seen: set[str] = set()
        self.last_hash: dict[str, str] = {}
        self.last_row: dict[str, float] = {}
        self.stats = {"books": 0, "deduped": 0, "markets": 0, "outcomes": 0}
        self.stop = False

    def discover(self) -> None:
        cands, off = [], 0
        while off < 400:
            page = self.gamma.get("/events", limit=100, offset=off,
                                  closed="false", order="volume24hr",
                                  ascending="false")
            if not page:
                break
            for ev in page:
                for m in ev.get("markets") or []:
                    if m.get("feesEnabled") or m.get("closed"):
                        continue
                    if not m.get("acceptingOrders"):
                        continue
                    try:
                        bid, ask = float(m.get("bestBid") or 0), float(m.get("bestAsk") or 0)
                        vol = float(m.get("volume24hr") or 0)
                    except ValueError:
                        continue
                    if not (0 < bid < ask < 1) or vol < MIN_VOL24:
                        continue
                    toks = json.loads(m.get("clobTokenIds") or "[]")
                    if toks:
                        cands.append((vol, m, toks[0]))
            off += 100
            time.sleep(0.4)
        cands.sort(key=lambda c: -c[0])
        fresh = {}
        for vol, m, tok in cands[:self.top_n]:
            slug = m["slug"]
            fresh[slug] = {"token": tok, "question": m.get("question"),
                           "end": m.get("endDate")}
            if slug not in self.meta_seen:
                self.meta_seen.add(slug)
                self.stats["markets"] += 1
                self.writer.meta({"ts": time.time(), "market_id": m.get("id"),
                                  "raw": m})
        dropped = set(self.tracked) - set(fresh)
        self.tracked = fresh
        print(f"[{iso(utcnow())}] tracking {len(fresh)} fee-free markets "
              f"(+{len(set(fresh)-set(self.tracked))} new, -{len(dropped)} dropped)")

    def poll_books(self) -> None:
        items = list(self.tracked.items())
        for i in range(0, len(items), BATCH):
            chunk = items[i:i + BATCH]
            books = self.clob.books([v["token"] for _, v in chunk])
            by_tok = {b.get("asset_id"): b for b in books}
            now = time.time()
            for slug, v in chunk:
                b = by_tok.get(v["token"])
                if not b:
                    continue
                h = b.get("hash")
                fresh = h != self.last_hash.get(slug)
                due = now - self.last_row.get(slug, 0) >= HEARTBEAT_ROW_S
                if not fresh and not due:
                    self.stats["deduped"] += 1
                    continue
                self.last_hash[slug] = h
                self.last_row[slug] = now
                self.writer.book({
                    "ts": round(now, 3), "slug": slug, "token": v["token"],
                    "bids": b.get("bids"), "asks": b.get("asks"),
                    "last_trade_price": b.get("last_trade_price"),
                    "tick_size": b.get("tick_size"), "hash": h,
                    "dedup": not fresh})
                self.stats["books"] += 1
            time.sleep(0.5)

    def sweep_outcomes(self) -> None:
        for slug in list(self.meta_seen):
            settled = self.gamma.get("/markets", slug=slug, closed="true")
            if not settled:
                continue
            gm = settled[0]
            prices = json.loads(gm.get("outcomePrices") or "[]")
            outcomes = json.loads(gm.get("outcomes") or "[]")
            winner = next((o for o, p in zip(outcomes, prices) if p == "1"), None)
            self.writer.outcome({
                "ts": time.time(), "slug": slug, "winner": winner,
                "outcome_prices": prices, "settled": True})
            self.stats["outcomes"] += 1
            self.meta_seen.discard(slug)
            self.tracked.pop(slug, None)
            time.sleep(0.3)

    def run(self, minutes: float) -> int:
        deadline = time.time() + minutes * 60 if minutes else None
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop", True))
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))
        next_disc = next_sweep = next_status = 0.0
        failures = 0
        print(f"collecting fee-free segment (top {self.top_n} by vol24, "
              f"{'for %.0f min' % minutes if minutes else 'until stopped'})")
        while not self.stop and (deadline is None or time.time() < deadline):
            tick = time.time()
            try:
                if tick >= next_disc:
                    self.discover()
                    next_disc = tick + DISCOVER_EVERY_S
                self.poll_books()
                if tick >= next_sweep:
                    self.sweep_outcomes()
                    next_sweep = tick + OUTCOME_SWEEP_S
                failures = 0
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"WARN tick failed ({failures}/{MAX_CONSEC_FAILURES}): "
                      f"{str(e)[:160]}", file=sys.stderr)
                if failures >= MAX_CONSEC_FAILURES:
                    print("FATAL: persistent API failures — stopping loudly.",
                          file=sys.stderr)
                    self.writer.close()
                    return 2
            if time.time() >= next_status:
                self.writer.flush()
                print(f"[{iso(utcnow())}] tracked={len(self.tracked)} {self.stats}")
                next_status = time.time() + 60
            time.sleep(max(0.0, POLL_EVERY_S - (time.time() - tick)))
        self.writer.close()
        print("done:", self.stats)
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--minutes", type=float, default=0)
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data" / "collect")
    a = ap.parse_args()
    return FeeFreeCollector(a.top, a.data_dir).run(a.minutes)


if __name__ == "__main__":
    raise SystemExit(main())
