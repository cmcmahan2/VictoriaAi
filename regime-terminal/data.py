"""
data.py — hourly OHLCV acquisition.

Real path: Yahoo Finance via the `yfinance` package (what the video uses).
    yfinance caps intraday history (~730 days at 1h), so LOOKBACK_DAYS defaults
    there. Cached to CSV under cache/ so we don't refetch.

Sandbox note: this environment's network allowlist blocks Yahoo Finance (same as
it blocked the exchanges), so the real fetch won't run here — run it locally.
`synthetic_ohlcv()` generates seeded hourly bars with PLANTED regimes so the
pipeline is demonstrable AND the HMM can be validated against known ground truth.
"""
from __future__ import annotations

import csv
import math
import os
import random
import time
from dataclasses import dataclass

import config

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
HOUR = 3600


@dataclass(frozen=True)
class Bar:
    ts: int      # unix seconds (bar open)
    open: float
    high: float
    low: float
    close: float
    volume: float


# --------------------------------------------------------------------------- #
# Real data (Yahoo Finance)
# --------------------------------------------------------------------------- #
def load_yfinance(ticker: str = config.TICKER, days: int = config.LOOKBACK_DAYS,
                  interval: str = config.INTERVAL) -> list[Bar]:
    """Fetch hourly bars via yfinance. Raises if unavailable (no pkg / blocked)."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError("yfinance not installed (`pip install yfinance`)") from e
    period = f"{min(days, 730)}d"
    df = yf.download(ticker, period=period, interval=interval,
                     auto_adjust=False, progress=False)
    if df is None or len(df) == 0:
        raise RuntimeError(f"no data returned for {ticker} (network blocked?)")
    bars = []
    for idx, row in df.iterrows():
        ts = int(idx.timestamp())
        def g(col):  # tolerate multi-index columns
            v = row[col]
            return float(v.iloc[0]) if hasattr(v, "iloc") else float(v)
        bars.append(Bar(ts, g("Open"), g("High"), g("Low"), g("Close"), g("Volume")))
    return bars


# --------------------------------------------------------------------------- #
# Synthetic (sandbox demo + HMM validation): bars WITH planted regime labels
# --------------------------------------------------------------------------- #
# Each planted regime has a distinct (drift, vol) signature the HMM should recover.
# Signatures are well-separated so a CORRECT HMM should recover them at high
# accuracy — this validates the machinery, not the (harder) real-data task.
PLANTED_REGIMES = [
    ("bull",   0.0030, 0.004),  # clear up-trend, low vol
    ("chop",   0.0000, 0.002),  # flat, very calm
    ("bear",  -0.0030, 0.006),  # clear down-trend, elevated vol
    ("crash", -0.0080, 0.015),  # violent down, high vol + high volume
]


def synthetic_ohlcv(days: int = 120, interval_hours: int = 1,
                    seed: int = config.SEED, end_ts: int | None = None):
    """Seeded hourly OHLCV with planted regimes. Returns (bars, true_labels)."""
    if end_ts is None:
        end_ts = int(time.time())
    n = days * 24 // interval_hours
    start_ts = end_ts - n * interval_hours * HOUR
    rng = random.Random(seed)
    price = 30000.0
    bars: list[Bar] = []
    labels: list[str] = []
    regime_left = 0
    cur = 0
    for i in range(n):
        if regime_left <= 0:
            regime_left = rng.randint(120, 300)   # sticky regimes
            cur = rng.randrange(len(PLANTED_REGIMES))
        regime_left -= 1
        name, drift, vol = PLANTED_REGIMES[cur]
        ret = drift + vol * rng.gauss(0, 1)
        new = price * math.exp(ret)
        hi = max(price, new) * (1 + abs(rng.gauss(0, vol / 2)))
        lo = min(price, new) * (1 - abs(rng.gauss(0, vol / 2)))
        # volume scales with the regime's volatility and spikes with bar action,
        # so volume_change carries regime information (crash >> chop)
        base_vol = 800.0 * (vol / 0.004) * (1 + 2 * abs(ret) / max(vol, 1e-9))
        volume = base_vol * rng.uniform(0.7, 1.3)
        bars.append(Bar(start_ts + i * interval_hours * HOUR,
                        price, hi, lo, new, volume))
        labels.append(name)
        price = new
    return bars, labels


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def cache_path(ticker: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{ticker.replace('/', '-')}-{interval}.csv")


def save_csv(bars: list[Bar], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow([b.ts, b.open, b.high, b.low, b.close, b.volume])


def load_csv(path: str) -> list[Bar]:
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out.append(Bar(int(r["ts"]), float(r["open"]), float(r["high"]),
                           float(r["low"]), float(r["close"]), float(r["volume"])))
    return out


def get_bars(ticker: str = config.TICKER, days: int = config.LOOKBACK_DAYS,
             interval: str = config.INTERVAL, use_cache: bool = True) -> list[Bar]:
    """Cached yfinance load. Raises RuntimeError if the network/pkg is unavailable."""
    path = cache_path(ticker, interval)
    if use_cache and os.path.exists(path):
        return load_csv(path)
    bars = load_yfinance(ticker, days, interval)
    save_csv(bars, path)
    return bars
