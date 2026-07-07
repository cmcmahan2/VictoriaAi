"""
backtest/data.py — PHASE 1: historical data acquisition + ground-truth outcomes.

================================================================================
WHAT HISTORICAL DATA IS ACTUALLY OBTAINABLE (investigated)
================================================================================
* BTC/USDT 1-minute klines  — Binance REST `/api/v3/klines`.
  1000 candles/request cap, so we paginate with startTime/endTime. Cached to CSV
  under backtest/cache/ so we never re-download. THESE CANDLES ARE THE SPINE of
  the whole backtest: both the ground-truth outcomes and the reconstructed
  PriceFeed are derived from them. (Mirrors api.binance.us / data-api.binance.vision
  are tried as fallbacks for geo/IP blocks.)

* Polymarket historical data — what each source can and cannot give us:
    - Gamma API (gamma-api.polymarket.com): market metadata + resolution. Good for
      *which* markets existed and how they resolved; NOT tick token prices, NOT books.
    - Polymarket subgraph (TheGraph): on-chain executed trades/positions. You can
      reconstruct *filled* prices for a market, but BTC-5m markets are ultra-short
      and historically thin/sparse; coverage is spotty and there is NO depth.
    - CLOB `/prices-history`: a midpoint/last-trade time series for a *given token id*
      at coarse fidelity. Usable only if you already hold the token ids of past 5m
      markets, and history for long-expired 5m tokens is frequently unavailable.
    - Historical ORDER BOOKS: **not retrievable.** The CLOB serves only the *current*
      book; there is no historical depth-snapshot endpoint, and the subgraph carries
      no book. CONFIRMED: real historical orderbook imbalance cannot be replayed.
      This is the single biggest backtest-validity limitation — `orderbook_imbal`
      (25% of the signal) must be MODELED (see backtest/pricing.py), never observed.

  => We use BTC candles as ground truth for OUTCOMES, and a MODEL for token prices,
     because reliable historical Polymarket token prices/books for these markets do
     not exist.

================================================================================
GROUND-TRUTH OUTCOMES
================================================================================
For each 5m window aligned to floor(ts/300)*300, UP wins iff
    close(window_end) > close(window_start)
where close(T) is the close of the 1m candle that closes exactly at T. Derived
purely from candles — never from Polymarket. (Polymarket's live BTC-5m markets
resolve on Binance prints; if your target market uses open-of-first-minute vs
close-of-last-minute instead, switch OUTCOME_MODE below — documented, not guessed.)

================================================================================
SANDBOX NOTE
================================================================================
In the Claude-on-the-web sandbox every exchange host is blocked by the network
allowlist, so real download fails here — run it on your machine. `--synthetic`
generates seeded regime-drift candles so the pipeline is demonstrable in-sandbox;
they are CLEARLY synthetic and any 'edge' measured on them is meaningless.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import time
from dataclasses import dataclass

import requests

import config
from price_feed import Candle

# Binance mirrors, tried in order (geo/IP blocks differ per host).
BINANCE_HOSTS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
    "https://api.binance.us",
]
KLINES_PATH = "/api/v3/klines"
_UA = {"User-Agent": "Mozilla/5.0 (polybot-backtest)"}

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
DAY_MS = 86_400_000
OUTCOME_MODE = "close_vs_close"  # or "close_vs_open" — see docstring


@dataclass(frozen=True)
class Outcome:
    window_start: int   # unix seconds, aligned to 300
    window_end: int     # window_start + 300
    price_open: float   # close(window_start)
    price_close: float  # close(window_end)
    outcome: str        # "UP" | "DOWN"


# --------------------------------------------------------------------------- #
# Download (real)
# --------------------------------------------------------------------------- #
def _get_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list[list]:
    """One page (<=1000) of raw kline rows. Tries each Binance mirror."""
    params = {"symbol": symbol, "interval": interval,
              "startTime": start_ms, "endTime": end_ms, "limit": 1000}
    last_err = "unknown"
    for host in BINANCE_HOSTS:
        try:
            r = requests.get(host + KLINES_PATH, params=params, timeout=15, headers=_UA)
            if r.status_code == 200:
                return r.json()
            last_err = f"{host} -> HTTP {r.status_code}: {r.text[:80]}"
        except Exception as e:  # network / TLS / timeout
            last_err = f"{host} -> {type(e).__name__}: {str(e)[:80]}"
    raise RuntimeError(f"all Binance mirrors failed ({last_err})")


def _row_to_candle(row: list) -> Candle:
    # [openTime, open, high, low, close, volume, closeTime, quoteVol, trades,
    #  takerBuyBase, takerBuyQuote, ignore]
    return Candle(
        ts=int(row[0]) // 1000,
        open=float(row[1]), high=float(row[2]), low=float(row[3]),
        close=float(row[4]), volume=float(row[5]), taker_buy=float(row[9]),
    )


def download_day(symbol: str, interval: str, day_start_ms: int) -> list[Candle]:
    """Download one UTC day of klines (paginating the 1000/req cap)."""
    out: list[Candle] = []
    cur, end = day_start_ms, day_start_ms + DAY_MS
    while cur < end:
        page = _get_klines(symbol, interval, cur, end - 1)
        if not page:
            break
        out.extend(_row_to_candle(r) for r in page)
        cur = int(page[-1][0]) + 60_000  # next minute after last openTime
        if len(page) < 1000:
            break
    return out


# --------------------------------------------------------------------------- #
# Cache (CSV, one file per UTC day)
# --------------------------------------------------------------------------- #
def _cache_file(symbol: str, interval: str, day_ms: int) -> str:
    day = time.strftime("%Y-%m-%d", time.gmtime(day_ms / 1000))
    return os.path.join(CACHE_DIR, f"{symbol}-{interval}-{day}.csv")


def _write_csv(path: str, candles: list[Candle]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume", "taker_buy"])
        for c in candles:
            w.writerow([c.ts, c.open, c.high, c.low, c.close, c.volume, c.taker_buy])


def _read_csv(path: str) -> list[Candle]:
    out: list[Candle] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.append(Candle(
                ts=int(row["ts"]), open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row["volume"]), taker_buy=float(row["taker_buy"]),
            ))
    return out


def get_candles(symbol: str = "BTCUSDT", interval: str = "1m",
                days: int = 180, end_ms: int | None = None) -> list[Candle]:
    """
    Return `days` of 1m candles ending at `end_ms` (default: now), using the
    per-day CSV cache and downloading only missing days. Raises if the network is
    blocked (sandbox) — callers wanting a demo should use synthetic_candles().
    """
    if end_ms is None:
        end_ms = int(time.time() * 1000)
    end_day = (end_ms // DAY_MS) * DAY_MS
    start_day = end_day - (days - 1) * DAY_MS

    candles: list[Candle] = []
    day = start_day
    while day <= end_day:
        path = _cache_file(symbol, interval, day)
        if os.path.exists(path):
            candles.extend(_read_csv(path))
        else:
            fetched = download_day(symbol, interval, day)
            if fetched:
                _write_csv(path, fetched)
                candles.extend(fetched)
        day += DAY_MS

    candles.sort(key=lambda c: c.ts)
    # de-dup any boundary overlap
    seen, uniq = set(), []
    for c in candles:
        if c.ts not in seen:
            seen.add(c.ts)
            uniq.append(c)
    return uniq


# --------------------------------------------------------------------------- #
# Synthetic fallback (sandbox demo only — CLEARLY not real data)
# --------------------------------------------------------------------------- #
def synthetic_candles(days: int = 7, end_ms: int | None = None,
                      seed: int = config.RANDOM_SEED,
                      drift_strength: float = 0.25) -> list[Candle]:
    """Seeded 1m candles, near-efficient. SYNTHETIC — not market data.

    Deliberately ALMOST a random walk: only a faint regime drift (default
    drift_strength≈0.35·σ), because real 5-minute BTC direction is close to
    unpredictable. Strong synthetic momentum would let a momentum strategy
    'predict' the data trivially and massively OVERSELL the bot — the worst way to
    be wrong. Crank drift_strength only to stress-test a known-predictable market.
    """
    if end_ms is None:
        end_ms = int(time.time() * 1000)
    n = days * 1440
    # Anchor to the 5m grid so candle close_times land on window boundaries
    # (real Binance candles are minute-aligned; synthetic must match or outcome
    # lookups at multiples of 300 all miss).
    anchor = ((end_ms // 1000) // config.WINDOW_SECONDS) * config.WINDOW_SECONDS
    start_ts = anchor - n * 60
    rng = random.Random(seed)
    price, sigma, drift, regime_left = 60000.0, 0.0008, 0.0, 0
    out: list[Candle] = []
    for i in range(n):
        if regime_left <= 0:
            regime_left = rng.randint(15, 40)
            drift = rng.choice([-1, 0, 0, 1]) * sigma * drift_strength * rng.uniform(0.5, 1.5)
        regime_left -= 1
        z = rng.gauss(0, 1)
        ret = drift + sigma * z
        new = price * math.exp(ret)
        hi = max(price, new) * (1 + abs(rng.gauss(0, 0.0002)))
        lo = min(price, new) * (1 - abs(rng.gauss(0, 0.0002)))
        vol = rng.uniform(5, 50)
        buy_share = min(0.95, max(0.05, 0.5 + 0.4 * math.tanh(ret / sigma)))
        out.append(Candle(start_ts + i * 60, price, hi, lo, new, vol, vol * buy_share))
        price = new
    return out


# --------------------------------------------------------------------------- #
# Ground-truth 5m outcomes
# --------------------------------------------------------------------------- #
def compute_outcomes(candles: list[Candle],
                     window: int = config.WINDOW_SECONDS) -> list[Outcome]:
    """UP iff close(window_end) > close(window_start), per 5m window."""
    close_at = {c.close_time: c.close for c in candles}  # T -> close of candle ending at T
    open_at = {c.ts: c.open for c in candles}
    if not candles:
        return []
    first_end = ((candles[0].ts + window) // window) * window
    last_end = (candles[-1].close_time // window) * window
    outcomes: list[Outcome] = []
    w = first_end
    while w + window <= last_end:
        ws, we = w, w + window
        if OUTCOME_MODE == "close_vs_open":
            p_open = open_at.get(ws)            # open of first minute in window
        else:
            p_open = close_at.get(ws)           # close at window start boundary
        p_close = close_at.get(we)
        if p_open is not None and p_close is not None:
            outcomes.append(Outcome(ws, we, p_open, p_close,
                                    "UP" if p_close > p_open else "DOWN"))
        w += window
    return outcomes


def outcome_base_rate(outcomes: list[Outcome]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o.outcome == "UP") / len(outcomes)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 1 — fetch klines + compute outcomes")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--synthetic", action="store_true",
                    help="use seeded synthetic candles (sandbox demo, not real)")
    args = ap.parse_args()

    if args.synthetic:
        print(f"[synthetic] generating {args.days}d of seeded candles (NOT real data)…")
        candles = synthetic_candles(days=args.days)
        src = "SYNTHETIC"
    else:
        print(f"[binance] fetching {args.days}d of {args.symbol} 1m klines "
              f"(cache: {CACHE_DIR})…")
        try:
            candles = get_candles(symbol=args.symbol, days=args.days)
            src = "BINANCE"
        except RuntimeError as e:
            print(f"\n  ✗ download failed: {e}")
            print("  This sandbox blocks exchange hosts (network allowlist). Run "
                  "locally for real data,\n  or re-run with --synthetic for a demo.\n")
            return

    outcomes = compute_outcomes(candles)
    if not candles:
        print("  no candles."); return
    span_d = (candles[-1].ts - candles[0].ts) / 86400.0
    up = outcome_base_rate(outcomes)
    print(f"\n  source        {src}")
    print(f"  candles       {len(candles):,}  spanning {span_d:.1f} days")
    print(f"  first / last  {time.strftime('%Y-%m-%d %H:%M', time.gmtime(candles[0].ts))}"
          f"  ->  {time.strftime('%Y-%m-%d %H:%M', time.gmtime(candles[-1].ts))} UTC")
    print(f"  5m windows    {len(outcomes):,}")
    if outcomes:
        print(f"  UP base rate  {up*100:.2f}%   (DOWN {100-up*100:.2f}%)")
        print(f"  sample        {outcomes[0]}")
        print(f"\n  Phase 1 OK — outcomes derived purely from candles.\n")
    else:
        print("  no 5m windows produced — check candle alignment.\n")


if __name__ == "__main__":
    main()
