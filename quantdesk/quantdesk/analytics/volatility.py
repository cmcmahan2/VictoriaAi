"""Realized volatility estimators, IV rank/percentile, VRP, expected move.

All estimators annualize with sqrt(252) and return decimal vol
(0.20 = 20%). Inputs are plain sequences ordered oldest -> newest so the
functions stay pure and trivially testable; the provider layer adapts
``PriceHistory`` to arrays.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

TRADING_DAYS = 252


def _check_window(n_available: int, window: int, min_needed: int) -> None:
    if window < 2:
        raise ValueError(f"window must be >= 2 (got {window})")
    if n_available < min_needed:
        raise ValueError(
            f"need at least {min_needed} bars for window={window}, got {n_available}"
        )


def close_to_close_vol(closes: Sequence[float], window: int) -> float:
    """Classic close-to-close realized vol.

    sigma = std(log returns over last `window` returns, ddof=1) * sqrt(252)

    Needs ``window + 1`` closes (a window of N returns spans N+1 prices).
    """
    _check_window(len(closes), window, window + 1)
    arr = np.asarray(closes[-(window + 1) :], dtype=float)
    log_returns = np.diff(np.log(arr))
    return float(np.std(log_returns, ddof=1) * math.sqrt(TRADING_DAYS))


def parkinson_vol(
    highs: Sequence[float], lows: Sequence[float], window: int
) -> float:
    """Parkinson (1980) high-low range estimator.

    sigma^2 = (1 / (4 ln 2)) * mean( ln(H/L)^2 ) * 252

    ~5x more efficient than close-to-close on continuous data, but biased
    low when there are overnight gaps (it never sees the gap).
    """
    if len(highs) != len(lows):
        raise ValueError("highs and lows must have equal length")
    _check_window(len(highs), window, window)
    h = np.asarray(highs[-window:], dtype=float)
    low = np.asarray(lows[-window:], dtype=float)
    hl_sq = np.log(h / low) ** 2
    daily_var = float(np.mean(hl_sq)) / (4.0 * math.log(2.0))
    return math.sqrt(daily_var * TRADING_DAYS)


def yang_zhang_vol(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    window: int,
) -> float:
    """Yang-Zhang (2000) estimator: drift-independent, handles overnight gaps.

    With n = window days (needing n+1 bars for the overnight terms):
        o_i  = ln(O_i / C_{i-1})                      (overnight return)
        c_i  = ln(C_i / O_i)                          (open-to-close return)
        rs_i = ln(H_i/O_i) ln(H_i/C_i) + ln(L_i/O_i) ln(L_i/C_i)
        k    = 0.34 / (1.34 + (n + 1) / (n - 1))
        sigma^2 = var(o, ddof=1) + k var(c, ddof=1) + (1 - k) mean(rs)

    Annualized by 252. The estimator of choice for gappy equities.
    """
    n_bars = len(closes)
    if not (len(opens) == len(highs) == len(lows) == n_bars):
        raise ValueError("OHLC sequences must have equal length")
    _check_window(n_bars, window, window + 1)

    o = np.asarray(opens[-window:], dtype=float)
    h = np.asarray(highs[-window:], dtype=float)
    low = np.asarray(lows[-window:], dtype=float)
    c = np.asarray(closes[-window:], dtype=float)
    c_prev = np.asarray(closes[-(window + 1) : -1], dtype=float)

    overnight = np.log(o / c_prev)
    open_close = np.log(c / o)
    rs = np.log(h / o) * np.log(h / c) + np.log(low / o) * np.log(low / c)

    n = float(window)
    k = 0.34 / (1.34 + (n + 1.0) / (n - 1.0))
    var_o = float(np.var(overnight, ddof=1))
    var_c = float(np.var(open_close, ddof=1))
    var_rs = float(np.mean(rs))
    daily_var = var_o + k * var_c + (1.0 - k) * var_rs
    return math.sqrt(max(daily_var, 0.0) * TRADING_DAYS)


def realized_vol_suite(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> dict[str, float]:
    """Standard RV panel: close-to-close 20/30/60/90d + Parkinson/YZ 20d.

    Windows lacking data are omitted rather than guessed.
    """
    out: dict[str, float] = {}
    for w in (20, 30, 60, 90):
        if len(closes) >= w + 1:
            out[f"cc_{w}d"] = close_to_close_vol(closes, w)
    if len(highs) >= 20:
        out["parkinson_20d"] = parkinson_vol(highs, lows, 20)
    if len(closes) >= 21:
        out["yang_zhang_20d"] = yang_zhang_vol(opens, highs, lows, closes, 20)
    return out


def rolling_cc_vol_series(closes: Sequence[float], window: int) -> list[float]:
    """Rolling close-to-close vol: one annualized estimate per day.

    Element i covers the ``window`` returns ending at close i. Used to
    bootstrap IV rank against a realized-vol distribution while our own
    IV history is still immature. Returns empty list if data is short.
    """
    if len(closes) < window + 1:
        return []
    arr = np.asarray(closes, dtype=float)
    log_returns = np.diff(np.log(arr))
    out: list[float] = []
    for i in range(window, len(log_returns) + 1):
        chunk = log_returns[i - window : i]
        out.append(float(np.std(chunk, ddof=1) * math.sqrt(TRADING_DAYS)))
    return out


def iv_rank(current_iv: float, iv_history: Sequence[float]) -> float:
    """IV Rank: where current IV sits in its trailing range, 0-100.

    rank = (current - min) / (max - min) * 100

    Degenerate (flat) history returns 50.0 — no information either way.
    """
    if not iv_history:
        raise ValueError("iv_history is empty")
    lo, hi = min(iv_history), max(iv_history)
    if hi - lo < 1e-12:
        return 50.0
    return float(np.clip((current_iv - lo) / (hi - lo) * 100.0, 0.0, 100.0))


def iv_percentile(current_iv: float, iv_history: Sequence[float]) -> float:
    """IV Percentile: % of history observations strictly below current, 0-100."""
    if not iv_history:
        raise ValueError("iv_history is empty")
    below = sum(1 for v in iv_history if v < current_iv)
    return below / len(iv_history) * 100.0


def iv_history_maturity(n_observations: int, target: int = TRADING_DAYS) -> str:
    """Honest label for our home-grown IV history, e.g. 'IV history: 12/252 days'."""
    qualifier = " (mature)" if n_observations >= target else " (IMMATURE — rank unreliable)"
    return f"IV history: {min(n_observations, target)}/{target} days collected{qualifier}"


def vrp(iv_30d: float, rv_20d: float) -> float:
    """Volatility risk premium estimate: 30d ATM IV minus 20d realized vol.

    Both annualized decimals. Positive => options priced rich vs recent
    realized — the premium this whole system exists to harvest. Remember:
    VRP is compensation for tail risk, not free money.
    """
    return iv_30d - rv_20d


def expected_move(spot: float, iv: float, days: int) -> float:
    """One-sigma expected move in dollars to a horizon: S * IV * sqrt(days/365).

    An *estimate* under lognormal assumptions; reality has fatter tails.
    """
    if days < 0:
        raise ValueError("days must be >= 0")
    return spot * iv * math.sqrt(days / 365.0)


def straddle_implied_move(
    call_mid: float, put_mid: float, spot: float
) -> float:
    """Market-implied move as a fraction of spot: (ATM call + ATM put) / S.

    The market's own consensus for total movement by expiry; useful as a
    cross-check on the analytic expected move.
    """
    if spot <= 0:
        raise ValueError("spot must be positive")
    return (call_mid + put_mid) / spot
