"""
price_feed.py — market data structures and indicator math.

`Candle`     : one 1-minute OHLCV bar (+ taker-buy volume for order-flow delta).
`OrderBook`  : a top-of-book snapshot with a single imbalance() readout in [-1, 1].
`PriceFeed`  : a rolling buffer of candles that computes EMA / RSI / MACD / momentum
               / volume-delta / realized-vol / trend-strength from *only* the candles
               it has been given.

The feed holds no notion of "now" beyond the last candle appended. The engine
guarantees no-look-ahead by only appending candles whose close time is < decision
time; the indicators here therefore cannot see the future by construction.

Pure stdlib — no numpy. All series math is plain Python over a deque.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    """One 1-minute bar. `ts` is the OPEN time in unix seconds (UTC)."""
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    taker_buy: float = 0.0  # taker buy base volume; sell vol = volume - taker_buy

    @property
    def close_time(self) -> int:
        """Unix seconds at which this 1m bar closes."""
        return self.ts + 60


@dataclass(frozen=True)
class OrderBook:
    """Top-of-book snapshot for one token. Sizes are in shares/contracts."""
    bids: tuple[tuple[float, float], ...]  # (price, size), best first
    asks: tuple[tuple[float, float], ...]  # (price, size), best first

    def imbalance(self, depth: int = 5) -> float:
        """(bid_size - ask_size) / (bid_size + ask_size) over top `depth`, in [-1, 1]."""
        bid = sum(s for _, s in self.bids[:depth])
        ask = sum(s for _, s in self.asks[:depth])
        tot = bid + ask
        if tot <= 0:
            return 0.0
        return (bid - ask) / tot

    def mid(self) -> float | None:
        if not self.bids or not self.asks:
            return None
        return (self.bids[0][0] + self.asks[0][0]) / 2.0


def _ema(values: list[float], period: int) -> float | None:
    """Classic EMA seeded with the first value. Needs >= period points."""
    if len(values) < period:
        return None
    k = 2.0 / (period + 1.0)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1.0 - k)
    return ema


def _ema_series(values: list[float], period: int) -> list[float]:
    """Full EMA series (same length as input, seeded with values[0])."""
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1.0 - k))
    return out


class PriceFeed:
    """Rolling 1m candle buffer with on-demand indicators."""

    def __init__(self, maxlen: int = 600):
        self.candles: deque[Candle] = deque(maxlen=maxlen)

    # -- ingestion ---------------------------------------------------------- #
    def add(self, c: Candle) -> None:
        """Append a candle. Enforces monotonic, gap-aware ordering."""
        if self.candles and c.ts <= self.candles[-1].ts:
            raise ValueError(
                f"non-monotonic candle: {c.ts} <= {self.candles[-1].ts} "
                "(would corrupt no-look-ahead ordering)"
            )
        self.candles.append(c)

    def __len__(self) -> int:
        return len(self.candles)

    def ready(self, warmup: int) -> bool:
        return len(self.candles) >= warmup

    # -- raw series --------------------------------------------------------- #
    def closes(self) -> list[float]:
        return [c.close for c in self.candles]

    @property
    def last(self) -> Candle | None:
        return self.candles[-1] if self.candles else None

    @property
    def price(self) -> float | None:
        return self.candles[-1].close if self.candles else None

    # -- indicators --------------------------------------------------------- #
    def ema(self, period: int) -> float | None:
        return _ema(self.closes(), period)

    def rsi(self, period: int) -> float | None:
        """Wilder's RSI in [0, 100]. None until enough data."""
        cl = self.closes()
        if len(cl) < period + 1:
            return None
        gains, losses = 0.0, 0.0
        for i in range(1, period + 1):
            d = cl[i] - cl[i - 1]
            gains += max(d, 0.0)
            losses += max(-d, 0.0)
        avg_gain, avg_loss = gains / period, losses / period
        for i in range(period + 1, len(cl)):
            d = cl[i] - cl[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(d, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-d, 0.0)) / period
        if avg_loss == 0.0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    def macd_hist(self, fast: int, slow: int, signal: int) -> float | None:
        """MACD histogram = MACD line - signal line. None until enough data."""
        cl = self.closes()
        if len(cl) < slow + signal:
            return None
        ef = _ema_series(cl, fast)
        es = _ema_series(cl, slow)
        macd_line = [a - b for a, b in zip(ef, es)]
        sig = _ema_series(macd_line, signal)
        return macd_line[-1] - sig[-1]

    def momentum(self, lookback: int) -> float | None:
        """Fractional price change over `lookback` candles."""
        cl = self.closes()
        if len(cl) <= lookback:
            return None
        past = cl[-lookback - 1]
        if past == 0:
            return None
        return (cl[-1] - past) / past

    def volume_delta(self, lookback: int) -> float | None:
        """Taker buy/sell imbalance over `lookback` candles, in [-1, 1]."""
        cs = list(self.candles)[-lookback:]
        if len(cs) < lookback:
            return None
        net = sum(2.0 * c.taker_buy - c.volume for c in cs)  # buy - sell
        tot = sum(c.volume for c in cs)
        if tot <= 0:
            return 0.0
        return max(-1.0, min(1.0, net / tot))

    def realized_vol(self, window: int) -> float | None:
        """Stdev of 1m log returns over `window` candles (per-minute sigma)."""
        cl = self.closes()
        if len(cl) < window + 1:
            return None
        rets = []
        for i in range(len(cl) - window, len(cl)):
            if cl[i - 1] > 0 and cl[i] > 0:
                rets.append(math.log(cl[i] / cl[i - 1]))
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(var)

    def trend_strength(self, lookback: int) -> float | None:
        """Signed Kaufman efficiency ratio in [-1, 1]: net move / total path length."""
        cl = self.closes()
        if len(cl) <= lookback:
            return None
        seg = cl[-lookback - 1:]
        net = seg[-1] - seg[0]
        path = sum(abs(seg[i] - seg[i - 1]) for i in range(1, len(seg)))
        if path == 0:
            return 0.0
        er = abs(net) / path           # efficiency ratio in [0, 1]
        return math.copysign(er, net)  # sign by direction
