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
# Real data (KuCoin public candles — clean REST API, crypto, supports leverage)
# --------------------------------------------------------------------------- #
KUCOIN_HOST = "https://api.kucoin.com"
_KC_TYPE = {"1h": "1hour", "1hour": "1hour", "4h": "4hour", "1d": "1day", "15m": "15min"}


def load_kucoin(symbol: str = "BTC-USDT", days: int = config.LOOKBACK_DAYS,
                interval: str = config.INTERVAL) -> list[Bar]:
    """Fetch hourly bars from KuCoin's public /market/candles (no key needed).

    KuCoin caps ~1500 candles/request and returns newest-first as
    [time, open, close, high, low, volume, turnover] (note: open, CLOSE, high, low).
    Symbols use a dash, e.g. BTC-USDT. Raises if the network is blocked (sandbox)."""
    import requests
    ktype = _KC_TYPE.get(interval, "1hour")
    end = int(time.time())
    start = end - days * 86400
    out, cur_end = [], end
    while cur_end > start:
        r = requests.get(f"{KUCOIN_HOST}/api/v1/market/candles",
                         params={"type": ktype, "symbol": symbol,
                                 "startAt": max(start, cur_end - 1500 * 3600),
                                 "endAt": cur_end}, timeout=15)
        r.raise_for_status()
        data = (r.json() or {}).get("data") or []
        if not data:
            break
        for t, o, c, h, l, v, _turn in data:           # KuCoin column order!
            out.append(Bar(int(t), float(o), float(h), float(l), float(c), float(v)))
        cur_end = int(data[-1][0]) - 3600               # page older (data is newest-first)
    out.sort(key=lambda b: b.ts)
    seen, uniq = set(), []
    for b in out:
        if b.ts not in seen:
            seen.add(b.ts); uniq.append(b)
    return uniq


# --------------------------------------------------------------------------- #
# Synthetic (sandbox demo + HMM validation): bars WITH planted regime labels
# --------------------------------------------------------------------------- #
# Each planted regime has a distinct (drift, vol) signature the HMM should recover.
# Signatures are well-separated so a CORRECT HMM should recover them at high
# accuracy — this validates the machinery, not the (harder) real-data task.
PLANTED_REGIMES = [
    ("bull",   0.0050, 0.004),  # clear up-trend, low vol
    ("chop",   0.0000, 0.002),  # flat, very calm
    ("bear",  -0.0030, 0.006),  # clear down-trend, elevated vol
    ("crash", -0.0080, 0.015),  # violent down, high vol + high volume
]
# Selection weights (indices into PLANTED_REGIMES): bull/chop common, crash rare,
# tuned so the long-run drift is ~neutral (a realistic wandering market, not a
# structural crater). Validation (drift_scale=1.0) still sees all 4 clearly.
REGIME_WEIGHTS = [0, 0, 0, 1, 1, 1, 2, 2, 3]


def synthetic_ohlcv(days: int = 120, interval_hours: int = 1,
                    seed: int = config.SEED, end_ts: int | None = None,
                    drift_scale: float = 1.0):
    """Seeded hourly OHLCV with planted regimes. Returns (bars, true_labels).

    drift_scale scales the planted drifts: 1.0 = strong/separable (for HMM
    VALIDATION); ~0.2 = realistic, bounded price paths (for BACKTEST demos, so
    the strategy can't trivially print money on cratering synthetic prices)."""
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
            cur = rng.choice(REGIME_WEIGHTS)
        regime_left -= 1
        name, drift, vol = PLANTED_REGIMES[cur]
        ret = drift * drift_scale + vol * rng.gauss(0, 1)
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
def cache_path(ticker: str, interval: str, source: str = "yfinance") -> str:
    return os.path.join(CACHE_DIR, f"{source}-{ticker.replace('/', '-')}-{interval}.csv")


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
             interval: str = config.INTERVAL, source: str = "yfinance",
             use_cache: bool = True) -> list[Bar]:
    """Cached real-data load. source = 'yfinance' or 'kucoin'. Raises RuntimeError
    if the network/package is unavailable (e.g. blocked in this sandbox)."""
    path = cache_path(ticker, interval, source)
    if use_cache and os.path.exists(path):
        return load_csv(path)
    bars = load_kucoin(ticker, days, interval) if source == "kucoin" \
        else load_yfinance(ticker, days, interval)
    if not bars:
        raise RuntimeError(f"no bars from {source} for {ticker}")
    save_csv(bars, path)
    return bars
