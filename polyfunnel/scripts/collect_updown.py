#!/usr/bin/env python3
"""Phase 1 collector: live order books + outcomes for up/down recurrer series.

Run:  PYTHONPATH=src python3 scripts/collect_updown.py [--minutes 12]
      (stdlib-only; runs in the web container and locally alike)

Why this exists: Polymarket does NOT serve historical order books or reliable
sub-12h price history for resolved markets, so intraday backtests live or die
on data collected in real time (docs/GROUND_TRUTH.md § prices-history). This
collector records the raw material for Phase 3 backtests of the 5-minute
crypto up/down families — the same real-book data polybot's backtest README
lists as its main missing input.

What it writes (plain NDJSON, one dir per series per UTC day, under
data/collect/ — gitignored; back up before any cleanup):
  meta.ndjson      one row per market discovered (full Gamma market object)
  books-HH.ndjson  book snapshots, ~1 Hz per token, deduped on the server's
                   book `hash` (a heartbeat row is forced every 15s per token
                   so collection gaps are distinguishable from quiet books);
                   closed hours are gzipped to books-HH.ndjson.gz
  outcomes.ndjson  one row per market once resolution is observed

Honesty guarantees: fails loudly after persistent API failures (exit 2);
never fabricates rows; heartbeat rows make gaps provable; dedupe drops only
snapshots whose server-side hash is unchanged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polyfunnel.api.clob import ClobPublic  # noqa: E402
from polyfunnel.api.gamma import GammaClient  # noqa: E402

DISCOVER_EVERY_S = 30          # how often to look for newly created markets
TRACK_HORIZON_S = 12 * 60      # track markets ending within this window
HEARTBEAT_ROW_S = 15           # force a book row at least this often per token
RESOLVE_POLL_S = 20            # poll cadence for post-end resolution
RESOLVE_GIVEUP_S = 45 * 60     # stop chasing a resolution after this long
STATUS_EVERY_S = 60            # console heartbeat
MAX_CONSEC_FAILURES = 30       # ~30s of solid failures -> die loudly


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class Market:
    def __init__(self, gamma_market: dict, series: str):
        self.series = series
        self.id = str(gamma_market["id"])
        self.slug = gamma_market.get("slug") or self.id
        self.end = dt.datetime.fromisoformat(
            gamma_market["endDate"].replace("Z", "+00:00"))
        self.token_ids: list[str] = json.loads(gamma_market.get("clobTokenIds") or "[]")
        outcomes = json.loads(gamma_market.get("outcomes") or "[]")
        self.outcome_by_token = dict(zip(self.token_ids, outcomes))
        self.resolve_started: float | None = None
        self.last_prices: list[str] = []  # latest pre-settlement outcomePrices
        self.raw = gamma_market


class SeriesWriter:
    """Per-series day/hour-partitioned NDJSON writer with gzip-on-rotate."""

    def __init__(self, base: Path, series: str):
        self.base = base / series
        self.series = series
        self._books_path: Path | None = None
        self._books_fh = None

    def _day_dir(self, t: dt.datetime) -> Path:
        d = self.base / t.strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _append(self, path: Path, row: dict) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    def meta(self, row: dict) -> None:
        self._append(self._day_dir(utcnow()) / "meta.ndjson", row)

    def outcome(self, row: dict) -> None:
        self._append(self._day_dir(utcnow()) / "outcomes.ndjson", row)

    def book(self, row: dict) -> None:
        t = utcnow()
        path = self._day_dir(t) / f"books-{t:%H}.ndjson"
        if path != self._books_path:
            if self._books_fh:
                self._books_fh.close()
                self._gzip_closed(self._books_path)
            self._books_path = path
            self._books_fh = path.open("a", encoding="utf-8")
        self._books_fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    def _gzip_closed(self, path: Path | None) -> None:
        if not path or not path.exists():
            return
        gz = path.with_suffix(".ndjson.gz")
        with path.open("rb") as src, gzip.open(gz, "wb") as dst:
            dst.write(src.read())
        path.unlink()

    def flush(self) -> None:
        if self._books_fh:
            self._books_fh.flush()

    def close(self) -> None:
        if self._books_fh:
            self._books_fh.close()
            self._books_fh = None


class Collector:
    def __init__(self, series_slugs: list[str], data_dir: Path, poll_s: float):
        self.gamma = GammaClient()
        self.clob = ClobPublic()
        self.series_slugs = series_slugs
        self.poll_s = poll_s
        self.writers = {s: SeriesWriter(data_dir, s) for s in series_slugs}
        self.live: dict[str, Market] = {}       # market id -> Market (pre-end)
        self.resolving: dict[str, Market] = {}  # market id -> Market (post-end)
        self.seen_ids: set[str] = set()
        self.last_hash: dict[str, str] = {}     # token -> last written book hash
        self.last_row_ts: dict[str, float] = {} # token -> last written epoch
        self.stats = {"books_written": 0, "books_deduped": 0,
                      "markets_seen": 0, "outcomes": 0, "unresolved": 0}
        self.consec_failures = 0
        self.stop = False

    # -- discovery ---------------------------------------------------------
    def discover(self) -> None:
        now = utcnow()
        for series in self.series_slugs:
            events = self.gamma.get(
                "/events", limit=10, closed="false", series_slug=series,
                end_date_min=iso(now - dt.timedelta(minutes=2)),
                order="endDate", ascending="true")
            for ev in events:
                for gm in ev.get("markets") or []:
                    mid = str(gm.get("id"))
                    if mid in self.seen_ids or not gm.get("endDate"):
                        continue
                    m = Market(gm, series)
                    if not m.token_ids:
                        continue
                    if (m.end - now).total_seconds() > TRACK_HORIZON_S:
                        continue
                    self.seen_ids.add(mid)
                    self.live[mid] = m
                    self.stats["markets_seen"] += 1
                    self.writers[series].meta(
                        {"ts": time.time(), "market_id": mid, "raw": gm})

    # -- book polling ------------------------------------------------------
    def poll_books(self) -> None:
        tokens: list[tuple[str, Market]] = [
            (t, m) for m in self.live.values() for t in m.token_ids]
        if not tokens:
            return
        books = self.clob.books([t for t, _ in tokens])
        now = time.time()
        by_token = {b.get("asset_id"): b for b in books}
        for token, m in tokens:
            b = by_token.get(token)
            if b is None:
                continue
            h = b.get("hash")
            fresh = h != self.last_hash.get(token)
            due = now - self.last_row_ts.get(token, 0) >= HEARTBEAT_ROW_S
            if not fresh and not due:
                self.stats["books_deduped"] += 1
                continue
            self.last_hash[token] = h
            self.last_row_ts[token] = now
            self.writers[m.series].book({
                "ts": round(now, 3),
                "server_ts": b.get("timestamp"),
                "market_id": m.id,
                "slug": m.slug,
                "token": token,
                "outcome": m.outcome_by_token.get(token),
                "bids": b.get("bids"),
                "asks": b.get("asks"),
                "last_trade_price": b.get("last_trade_price"),
                "tick_size": b.get("tick_size"),
                "min_order_size": b.get("min_order_size"),
                "hash": h,
                "dedup": not fresh,  # True = unchanged heartbeat row
            })
            self.stats["books_written"] += 1

    # -- lifecycle / resolution -------------------------------------------
    def advance_lifecycle(self) -> None:
        now = utcnow()
        for mid in [k for k, m in self.live.items() if m.end <= now]:
            m = self.live.pop(mid)
            m.resolve_started = time.time()
            self.resolving[mid] = m

    def poll_resolutions(self) -> None:
        # Live quirks (2026-07-07): /markets?id=<id> returns [] for recent 5m
        # market ids, and settled markets vanish from the default (closed=false)
        # listing — so look up by slug WITH closed=true (hit = settled), fall
        # back to the open listing for interim prices. Settlement lags the
        # window end by ~6-30 min.
        for mid in list(self.resolving):
            m = self.resolving[mid]
            settled_q = self.gamma.get("/markets", slug=m.slug, closed="true")
            if settled_q:
                gm = settled_q[0]
                prices = json.loads(gm.get("outcomePrices") or "[]")
                outcomes = json.loads(gm.get("outcomes") or "[]")
                winner = None
                for o, p in zip(outcomes, prices):
                    if p == "1":
                        winner = o
                self.writers[m.series].outcome({
                    "ts": time.time(), "market_id": mid, "slug": m.slug,
                    "end_date": iso(m.end), "winner": winner, "settled": True,
                    "outcome_prices": prices,
                    "uma_statuses": gm.get("umaResolutionStatuses")})
                self.stats["outcomes"] += 1
                del self.resolving[mid]
                continue
            open_q = self.gamma.get("/markets", slug=m.slug)
            if open_q:
                m.last_prices = json.loads(open_q[0].get("outcomePrices") or "[]")
            if time.time() - m.resolve_started > RESOLVE_GIVEUP_S:
                self.writers[m.series].outcome(self._provisional_row(m))
                self.stats["unresolved"] += 1
                del self.resolving[mid]

    def _provisional_row(self, m: Market) -> dict:
        """Not settled (yet): record last observed prices, clearly labeled."""
        return {"ts": time.time(), "market_id": m.id, "slug": m.slug,
                "end_date": iso(m.end), "winner": None, "settled": False,
                "provisional_prices": m.last_prices}

    # -- main loop ---------------------------------------------------------
    def run(self, minutes: float) -> int:
        deadline = time.time() + minutes * 60 if minutes else None
        next_discover = next_resolve = next_status = 0.0
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop", True))
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))
        print(f"collecting {self.series_slugs} "
              f"({'for %.0f min' % minutes if minutes else 'until stopped'})")
        while not self.stop and (deadline is None or time.time() < deadline):
            tick = time.time()
            try:
                if tick >= next_discover:
                    self.discover()
                    next_discover = tick + DISCOVER_EVERY_S
                self.advance_lifecycle()
                self.poll_books()
                if self.resolving and tick >= next_resolve:
                    self.poll_resolutions()
                    next_resolve = tick + RESOLVE_POLL_S
                self.consec_failures = 0
            except Exception as e:  # noqa: BLE001 — count, then die loudly
                self.consec_failures += 1
                print(f"WARN tick failed ({self.consec_failures}/"
                      f"{MAX_CONSEC_FAILURES}): {e}", file=sys.stderr)
                if self.consec_failures >= MAX_CONSEC_FAILURES:
                    print("FATAL: persistent API failures — stopping so the "
                          "gap is visible rather than silently thin.",
                          file=sys.stderr)
                    self._shutdown()
                    return 2
            if time.time() >= next_status:
                for w in self.writers.values():
                    w.flush()
                print(f"[{iso(utcnow())}] live={len(self.live)} "
                      f"resolving={len(self.resolving)} {self.stats}")
                next_status = time.time() + STATUS_EVERY_S
            time.sleep(max(0.0, self.poll_s - (time.time() - tick)))
        self._shutdown()
        return 0

    def _shutdown(self) -> None:
        # last chance to catch resolutions for already-ended markets
        try:
            self.advance_lifecycle()
            if self.resolving:
                self.poll_resolutions()
        except Exception:  # noqa: BLE001
            pass
        # settlement lags ~6-30 min; short runs end before it lands — write
        # provisional rows so the de-facto winner isn't lost
        for m in self.resolving.values():
            self.writers[m.series].outcome(self._provisional_row(m))
            self.stats["unresolved"] += 1
        for w in self.writers.values():
            w.close()
        print("done:", self.stats)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--series", action="append",
                    help="series slug (repeatable); default btc-up-or-down-5m")
    ap.add_argument("--minutes", type=float, default=0,
                    help="stop after N minutes (0 = run until stopped)")
    ap.add_argument("--poll", type=float, default=1.0,
                    help="book poll interval seconds (default 1.0)")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data" / "collect")
    args = ap.parse_args()
    series = args.series or ["btc-up-or-down-5m"]
    return Collector(series, args.data_dir, args.poll).run(args.minutes)


if __name__ == "__main__":
    raise SystemExit(main())
