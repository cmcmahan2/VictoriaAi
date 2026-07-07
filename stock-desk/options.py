"""
options.py — Black-Scholes option pricing (pure Python).

Historical option chains are expensive/hard to get, so to BACKTEST the wheel we
MODEL premiums with Black-Scholes from the stock price, strike, days-to-expiry,
and recent realized volatility. This is an explicit modeling assumption (like the
regime terminal's token pricing): real fills will differ (IV ≠ realized vol,
bid/ask spread, skew). Stated loudly wherever it's used.
"""
from __future__ import annotations

import math

SQRT2 = math.sqrt(2.0)
SQRT2PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT2))


def _d1(S, K, T, r, sigma):
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))


def bs_price(S, K, T, r, sigma, kind):
    """European option price. S spot, K strike, T years, r rate, sigma annual vol.
    kind 'call' or 'put'. At/après expiry returns intrinsic value."""
    if T <= 0 or sigma <= 0:
        return max(0.0, (S - K) if kind == "call" else (K - S))
    d1 = _d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_delta(S, K, T, r, sigma, kind):
    """Option delta (probability-ish that it finishes in the money for the writer)."""
    if T <= 0 or sigma <= 0:
        itm = (S > K) if kind == "call" else (S < K)
        return (1.0 if kind == "call" else -1.0) if itm else 0.0
    d1 = _d1(S, K, T, r, sigma)
    return _norm_cdf(d1) if kind == "call" else _norm_cdf(d1) - 1.0


def annualized_vol(closes, lookback=20, periods_per_year=252):
    """Annualized realized vol from the last `lookback` daily closes."""
    seg = closes[-lookback - 1:]
    if len(seg) < 3:
        return 0.3
    rets = [math.log(seg[i] / seg[i - 1]) for i in range(1, len(seg)) if seg[i - 1] > 0]
    if len(rets) < 2:
        return 0.3
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(periods_per_year)
