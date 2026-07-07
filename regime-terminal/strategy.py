"""
strategy.py — the layer that decides what to DO inside a regime.

Indicators (all causal — each value uses only bars up to t) feed 8 confirmations.
A long is entered only when: regime stance is 'long' AND filtered regime confidence
>= MIN_REGIME_CONFIDENCE AND >= CONFIRMATIONS_REQUIRED of 8 pass AND we're past the
post-exit cooldown. Exit is immediate on an 'avoid' (bear/crash) regime; a drift to
'neutral' only exits after MIN_HOLD_HOURS (hysteresis — don't churn on wobble).

These thresholds are the part you ADAPT over time; the regime layer stays put.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

import config


# --------------------------------------------------------------------------- #
# Causal indicators precomputed over the full bar series
# --------------------------------------------------------------------------- #
def _wilder(series, period):
    """Wilder smoothing (used by RSI/ADX)."""
    out = [None] * len(series)
    if len(series) < period:
        return out
    avg = sum(series[:period]) / period
    out[period - 1] = avg
    for t in range(period, len(series)):
        avg = (avg * (period - 1) + series[t]) / period
        out[t] = avg
    return out


def _sma(vals, period):
    out = [None] * len(vals)
    s = 0.0
    for t in range(len(vals)):
        s += vals[t]
        if t >= period:
            s -= vals[t - period]
        if t >= period - 1:
            out[t] = s / period
    return out


def _ema(vals, period):
    out = [None] * len(vals)
    if not vals:
        return out
    k = 2.0 / (period + 1)
    e = vals[0]
    out[0] = e
    for t in range(1, len(vals)):
        e = vals[t] * k + e * (1 - k)
        out[t] = e
    return out


class Indicators:
    """All series indexed by bar; value is None until enough history (causal)."""

    def __init__(self, bars, cfg=config):
        self.bars = bars
        self.cfg = cfg
        closes = [b.close for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        vols = [b.volume for b in bars]
        n = len(bars)

        self.rsi = self._rsi(closes, cfg.RSI_PERIOD)
        self.macd_hist = self._macd_hist(closes, cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
        self.adx = self._adx(highs, lows, closes, cfg.ADX_PERIOD)
        self.sma_fast = _sma(closes, cfg.MA_FAST)
        self.sma_slow = _sma(closes, cfg.MA_SLOW)
        self.sma_trend = _sma(closes, getattr(cfg, "TREND_MA", 200))   # long-term trend filter
        self.vol_ma = _sma(vols, cfg.VOLUME_MA)
        self.momentum = [None] * n
        for t in range(n):
            if t >= cfg.MOMENTUM_LOOKBACK and closes[t - cfg.MOMENTUM_LOOKBACK] > 0:
                self.momentum[t] = closes[t] / closes[t - cfg.MOMENTUM_LOOKBACK] - 1
        # range and its rolling median (for blow-off detection)
        self.range = [(highs[t] - lows[t]) / closes[t] if closes[t] else 0.0 for t in range(n)]
        self.range_med = _sma(self.range, cfg.VOL_LOOKBACK)
        self.closes = closes

    @staticmethod
    def _rsi(closes, period):
        n = len(closes)
        out = [None] * n
        if n < period + 1:
            return out
        gains = [max(closes[t] - closes[t - 1], 0.0) for t in range(1, n)]
        losses = [max(closes[t - 1] - closes[t], 0.0) for t in range(1, n)]
        ag = _wilder(gains, period)
        al = _wilder(losses, period)
        for t in range(1, n):
            g, l = ag[t - 1], al[t - 1]
            if g is None or l is None:
                continue
            out[t] = 100.0 if l == 0 else 100.0 - 100.0 / (1.0 + g / l)
        return out

    @staticmethod
    def _macd_hist(closes, fast, slow, signal):
        ef, es = _ema(closes, fast), _ema(closes, slow)
        macd = [(ef[t] - es[t]) if ef[t] is not None and es[t] is not None else None
                for t in range(len(closes))]
        vals = [m if m is not None else 0.0 for m in macd]
        sig = _ema(vals, signal)
        return [(macd[t] - sig[t]) if macd[t] is not None else None
                for t in range(len(closes))]

    @staticmethod
    def _adx(highs, lows, closes, period):
        n = len(highs)
        out = [None] * n
        if n < 2 * period + 1:
            return out
        tr, pdm, ndm = [0.0], [0.0], [0.0]
        for t in range(1, n):
            up = highs[t] - highs[t - 1]
            dn = lows[t - 1] - lows[t]
            pdm.append(up if (up > dn and up > 0) else 0.0)
            ndm.append(dn if (dn > up and dn > 0) else 0.0)
            tr.append(max(highs[t] - lows[t], abs(highs[t] - closes[t - 1]),
                          abs(lows[t] - closes[t - 1])))
        str_ = _wilder(tr[1:], period)
        spdm = _wilder(pdm[1:], period)
        sndm = _wilder(ndm[1:], period)
        dx = [None] * n
        for i in range(len(str_)):
            t = i + 1
            if str_[i] in (None, 0) or spdm[i] is None or sndm[i] is None:
                continue
            pdi = 100 * spdm[i] / str_[i]
            ndi = 100 * sndm[i] / str_[i]
            denom = pdi + ndi
            dx[t] = 100 * abs(pdi - ndi) / denom if denom else 0.0
        dxv = [d for d in dx if d is not None]
        adx_s = _wilder(dxv, period)
        # map smoothed adx back to bar indices
        first = next((t for t in range(n) if dx[t] is not None), n)
        for i, v in enumerate(adx_s):
            if v is not None and first + i < n:
                out[first + i] = v
        return out


# --------------------------------------------------------------------------- #
# Confirmations (8) — each returns True when bullish-aligned
# --------------------------------------------------------------------------- #
def confirmations(ind: Indicators, t: int) -> list[tuple[str, bool]]:
    c = ind.cfg
    rsi = ind.rsi[t]; mh = ind.macd_hist[t]; adx = ind.adx[t]
    mom = ind.momentum[t]; sf = ind.sma_fast[t]; ss = ind.sma_slow[t]
    vma = ind.vol_ma[t]; rng = ind.range[t]; rmed = ind.range_med[t]
    px = ind.closes[t]; vol = ind.bars[t].volume
    checks = [
        ("rsi_ok",      rsi is not None and 50.0 < rsi < c.RSI_MAX),
        ("macd_up",     mh is not None and mh > 0),
        ("adx_trend",   adx is not None and adx > c.ADX_MIN),
        ("momentum_up", mom is not None and mom > 0),
        ("above_fast",  sf is not None and px > sf),
        ("fast_gt_slow", sf is not None and ss is not None and sf > ss),
        ("volume_ok",   vma is not None and vol > vma),
        ("not_blowoff", rmed is not None and rng < 2.5 * rmed),
    ]
    return checks


def count_passed(ind: Indicators, t: int) -> tuple[int, list]:
    cks = confirmations(ind, t)
    return sum(1 for _, ok in cks if ok), cks


# --------------------------------------------------------------------------- #
# Decision (given regime + position state)
# --------------------------------------------------------------------------- #
@dataclass
class Decision:
    action: str            # 'enter' | 'exit' | 'hold' | 'flat'
    reason: str
    n_confirm: int = 0


def decide(stance: str, confidence: float, n_confirm: int,
           in_position: bool, bars_since_exit: int, bars_held: int,
           cfg=config) -> Decision:
    if in_position:
        if stance == "avoid":
            return Decision("exit", "regime->avoid (bear/crash)", n_confirm)
        if stance != "long" and bars_held >= cfg.MIN_HOLD_HOURS:
            return Decision("exit", f"regime->{stance} held>={cfg.MIN_HOLD_HOURS}h", n_confirm)
        return Decision("hold", "in long, regime intact", n_confirm)
    # flat
    if stance != "long":
        return Decision("flat", f"regime={stance}", n_confirm)
    if confidence < cfg.MIN_REGIME_CONFIDENCE:
        return Decision("flat", f"low confidence {confidence:.2f}", n_confirm)
    if bars_since_exit < cfg.COOLDOWN_HOURS:
        return Decision("flat", f"cooldown {bars_since_exit}/{cfg.COOLDOWN_HOURS}h", n_confirm)
    if n_confirm < cfg.CONFIRMATIONS_REQUIRED:
        return Decision("flat", f"confirms {n_confirm}/{cfg.CONFIRMATIONS_REQUIRED}", n_confirm)
    return Decision("enter", f"bull regime + {n_confirm}/{cfg.CONFIRMATIONS_TOTAL} confirms", n_confirm)


def target_dir(stance, confidence, n_confirm, cur_dir, bars_held, bars_since_exit,
               allow_short, cfg=config, trend_down=True):
    """Desired position direction (-1 short / 0 flat / +1 long) + reason.

    With allow_short=False this reduces to the original long-or-flat logic, so
    existing results are unchanged. With allow_short=True it also shorts bear/crash
    regimes and can flip directly long<->short on a regime reversal.

    trend_down (price < long-term TREND_MA) GATES every short: on real data, shorting
    bull-market pullbacks — where stance flips to 'avoid' but price is still above the
    trend — was the single behavior that blew up the strategy. Shorts now require the
    bigger-picture trend to actually be down."""
    can_short = allow_short and trend_down
    if cur_dir > 0:                                   # currently long
        if stance == "avoid":
            return (-1, "regime->avoid: flip short") if can_short else (0, "regime->avoid: exit")
        if stance != "long" and bars_held >= cfg.MIN_HOLD_HOURS:
            return 0, f"left bull, held {bars_held}h"
        return 1, "hold long"
    if cur_dir < 0:                                   # currently short
        if stance == "long" or not trend_down:        # bull regime OR price reclaimed trend
            return (1, "regime->bull: flip long") if stance == "long" else (0, "trend reclaimed: cover")
        if stance != "avoid" and bars_held >= cfg.MIN_HOLD_HOURS:
            return 0, f"left bear, held {bars_held}h"
        return -1, "hold short"
    # flat
    if bars_since_exit < cfg.COOLDOWN_HOURS:
        return 0, f"cooldown {bars_since_exit}/{cfg.COOLDOWN_HOURS}h"
    if stance == "long" and confidence >= cfg.MIN_REGIME_CONFIDENCE and n_confirm >= cfg.CONFIRMATIONS_REQUIRED:
        return 1, f"bull + {n_confirm}/{cfg.CONFIRMATIONS_TOTAL}"
    if can_short and stance == "avoid" and confidence >= cfg.MIN_REGIME_CONFIDENCE:
        return -1, "bear/crash + downtrend"
    return 0, f"flat ({stance})"
