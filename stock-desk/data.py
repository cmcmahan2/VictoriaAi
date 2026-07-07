"""
data.py — daily stock bars for stock-desk.

Real path: Alpaca market data (/v2/stocks/{symbol}/bars, free tier). Needs
ALPACA_API_KEY / ALPACA_SECRET_KEY. Sandbox blocks it, so use synthetic here.
synthetic_daily() makes seeded daily bars (GBM with a mild drift) for backtests.
"""
from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass

import config

DAY = 86400


@dataclass(frozen=True)
class Bar:
    ts: int      # unix seconds (bar date, 00:00 UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float


def synthetic_daily(days: int = 504, seed: int = config.SEED, end_ts: int | None = None,
                    drift: float = 0.0003, vol: float = 0.018):
    """Seeded daily bars (GBM). drift/vol are per-day. SYNTHETIC — not real data."""
    if end_ts is None:
        end_ts = (int(time.time()) // DAY) * DAY
    rng = random.Random(seed)
    price = 180.0
    start = end_ts - days * DAY
    out = []
    for i in range(days):
        ret = drift + vol * rng.gauss(0, 1)
        new = price * math.exp(ret)
        hi = max(price, new) * (1 + abs(rng.gauss(0, vol / 3)))
        lo = min(price, new) * (1 - abs(rng.gauss(0, vol / 3)))
        out.append(Bar(start + i * DAY, price, hi, lo, new, rng.uniform(1e6, 5e6)))
        price = new
    return out


def load_alpaca_daily(symbol: str = config.TICKER, days: int = config.LOOKBACK_DAYS):
    """Daily bars from Alpaca market data. Raises if blocked / no keys."""
    import requests
    key, sec = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
    if not key or not sec:
        raise RuntimeError("set ALPACA_API_KEY and ALPACA_SECRET_KEY")
    start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * DAY))
    r = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec},
        params={"timeframe": "1Day", "start": start, "limit": 10000, "adjustment": "all"},
        timeout=20)
    r.raise_for_status()
    bars = r.json().get("bars") or []
    out = []
    for b in bars:
        ts = int(time.mktime(time.strptime(b["t"][:10], "%Y-%m-%d")))
        out.append(Bar(ts, b["o"], b["h"], b["l"], b["c"], b["v"]))
    if not out:
        raise RuntimeError(f"no bars for {symbol}")
    return out


def get_daily(symbol: str = config.TICKER, days: int = config.LOOKBACK_DAYS,
              source: str = "alpaca"):
    return synthetic_daily(days=days) if source == "synthetic" else load_alpaca_daily(symbol, days)
