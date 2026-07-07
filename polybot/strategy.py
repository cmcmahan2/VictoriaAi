"""
strategy.py — the composite directional-momentum signal.

`Strategy.evaluate(feed, orderbook, now_ts)` reads the PriceFeed (1m candles up to
the decision moment) plus a top-of-book OrderBook snapshot, computes 7 indicator
sub-signals each squashed to [-1, +1], and returns their weighted composite as a
`Signal` in [-1, +1]. Positive => UP favored, negative => DOWN favored.

This is the *exact* decision logic the live bot and the backtester both call —
there is no second implementation. The only difference between live and backtest
is who constructs the `feed` and `orderbook` handed in here. In the backtest the
orderbook is SYNTHETIC (see backtest/pricing.py); treat any orderbook-driven edge
in a backtest with deep suspicion.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import config
from price_feed import OrderBook, PriceFeed


@dataclass
class Signal:
    score: float                       # composite, [-1, +1]
    side: str                          # "UP" | "DOWN" | "NONE"
    confidence: float                  # |score|, [0, 1]
    should_trade: bool                 # passed threshold + hour filter + warmup
    components: dict[str, float] = field(default_factory=dict)  # per-indicator [-1,1]
    reason: str = ""                   # why we did/didn't trade (for logging)


def _tanh(x: float) -> float:
    # math.tanh, guarded against overflow on absurd inputs
    if x > 20:
        return 1.0
    if x < -20:
        return -1.0
    return math.tanh(x)


class Strategy:
    """7-indicator composite. Stateless apart from its weights/config."""

    def __init__(self, cfg=config, weights: dict[str, float] | None = None):
        self.cfg = cfg
        self.weights = dict(weights if weights is not None else cfg.WEIGHTS)
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            # normalize defensively so the composite stays in [-1, 1]
            self.weights = {k: v / total for k, v in self.weights.items()}

    # -- individual sub-signals, each returning a value in [-1, +1] --------- #
    def _ema_cross(self, feed: PriceFeed) -> float | None:
        ef, es = feed.ema(self.cfg.EMA_FAST), feed.ema(self.cfg.EMA_SLOW)
        if ef is None or es is None or es == 0:
            return None
        return _tanh(self.cfg.K_EMA * (ef - es) / es)

    def _macd(self, feed: PriceFeed) -> float | None:
        h = feed.macd_hist(self.cfg.MACD_FAST, self.cfg.MACD_SLOW, self.cfg.MACD_SIGNAL)
        px = feed.price
        if h is None or not px:
            return None
        return _tanh(self.cfg.K_MACD * h / px)

    def _rsi(self, feed: PriceFeed) -> float | None:
        r = feed.rsi(self.cfg.RSI_PERIOD)
        if r is None:
            return None
        return max(-1.0, min(1.0, (r - 50.0) / 50.0))

    def _momentum(self, feed: PriceFeed) -> float | None:
        m = feed.momentum(self.cfg.MOMENTUM_LOOKBACK)
        if m is None:
            return None
        return _tanh(self.cfg.K_MOMENTUM * m)

    def _volume_delta(self, feed: PriceFeed) -> float | None:
        return feed.volume_delta(self.cfg.VOL_DELTA_LOOKBACK)

    def _trend_strength(self, feed: PriceFeed) -> float | None:
        return feed.trend_strength(self.cfg.TREND_LOOKBACK)

    def _orderbook_imbal(self, ob: OrderBook | None) -> float | None:
        if ob is None:
            return None
        return ob.imbalance()

    # -- main entry point --------------------------------------------------- #
    def evaluate(
        self,
        feed: PriceFeed,
        orderbook: OrderBook | None,
        now_ts: int | None = None,
    ) -> Signal:
        """Compute the composite signal. `now_ts` (UTC seconds) drives the hour filter."""
        if not feed.ready(self.cfg.WARMUP_CANDLES):
            return Signal(0.0, "NONE", 0.0, False, {}, "warmup")

        raw = {
            "orderbook_imbal": self._orderbook_imbal(orderbook),
            "ema_cross":       self._ema_cross(feed),
            "macd":            self._macd(feed),
            "rsi":             self._rsi(feed),
            "momentum":        self._momentum(feed),
            "volume_delta":    self._volume_delta(feed),
            "trend_strength":  self._trend_strength(feed),
        }

        # Weighted sum over available sub-signals. If one is missing (e.g. no
        # orderbook), drop it and renormalize the remaining weights so the
        # composite stays calibrated to [-1, 1] rather than silently shrinking.
        num, wsum = 0.0, 0.0
        components: dict[str, float] = {}
        for name, val in raw.items():
            if val is None:
                continue
            v = max(-1.0, min(1.0, val))
            components[name] = v
            num += self.weights[name] * v
            wsum += self.weights[name]
        score = num / wsum if wsum > 0 else 0.0
        score = max(-1.0, min(1.0, score))

        side = "UP" if score > 0 else ("DOWN" if score < 0 else "NONE")
        confidence = abs(score)

        # Hour filter (UTC). now_ts is the decision time.
        hour_ok = True
        if now_ts is not None:
            import time
            hour = time.gmtime(now_ts).tm_hour
            hour_ok = hour in self.cfg.ALLOWED_HOURS

        passed = confidence >= self.cfg.SIGNAL_THRESHOLD
        should_trade = bool(passed and hour_ok and side != "NONE")
        if not passed:
            reason = f"below_threshold({confidence:.3f}<{self.cfg.SIGNAL_THRESHOLD})"
        elif not hour_ok:
            reason = "hour_filtered"
        else:
            reason = "trade"

        return Signal(score, side, confidence, should_trade, components, reason)
