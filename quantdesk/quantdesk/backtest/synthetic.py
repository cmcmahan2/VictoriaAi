"""Synthetic option pricing for backtests — READ THE LIMITATION.

Historical option prices are not free, so backtests price every option
with Black-Scholes using an IV *proxy*: trailing 20d realized vol times
a configurable richness multiplier (calibrated to the measured VRP,
default 1.15). This reproduces the *average* relationship between
implied and realized vol but erases everything idiosyncratic: skew,
term structure, earnings ramps, panic spikes.

Consequently backtest results have DIRECTIONAL / REGIME VALIDITY ONLY.
Absolute return numbers are approximate and systematically too smooth.
Every report prints ``SYNTHETIC_WARNING`` — do not remove it.
"""

from __future__ import annotations

from collections.abc import Sequence

from quantdesk.analytics import black_scholes as bs
from quantdesk.analytics.volatility import close_to_close_vol
from quantdesk.data.models import OptionType

SYNTHETIC_WARNING = (
    "SYNTHETIC PRICING — options are Black-Scholes priced from an RV20 x "
    "richness IV proxy, not real quotes. Directional/regime validity only; "
    "absolute returns are approximate and smoother than reality."
)

MIN_BARS_FOR_IV = 21  # RV20 needs 21 closes


def synthetic_iv(closes_so_far: Sequence[float], richness: float) -> float:
    """IV proxy at a point in time: RV20 of the trailing closes x richness.

    Uses only data available *up to* that bar — no lookahead. Floored at
    5% annualized so deep-calm stretches still price options sanely.
    """
    if len(closes_so_far) < MIN_BARS_FOR_IV:
        raise ValueError(
            f"need >= {MIN_BARS_FOR_IV} closes for the IV proxy, "
            f"got {len(closes_so_far)}"
        )
    rv = close_to_close_vol(closes_so_far, 20)
    return max(rv * richness, 0.05)


def synthetic_price(
    option_type: OptionType,
    spot: float,
    strike: float,
    dte_days: int,
    rate: float,
    iv: float,
) -> float:
    """BS price under the proxy IV; intrinsic at/past expiry."""
    t_years = max(dte_days, 0) / 365.0
    return bs.bs_price(option_type, spot, strike, t_years, rate, iv)


def strike_for_delta(
    option_type: OptionType,
    spot: float,
    target_delta: float,
    dte_days: int,
    rate: float,
    iv: float,
    increment_pct: float = 0.01,
) -> float:
    """Strike whose BS delta is closest to target, on a 1%-of-spot grid.

    Mimics picking from a listed strike ladder. Puts scan 70-100% of
    spot, calls 100-130%.
    """
    t_years = max(dte_days, 1) / 365.0
    if option_type == "put":
        grid = [spot * (0.70 + increment_pct * i) for i in range(int(0.30 / increment_pct) + 1)]
    else:
        grid = [spot * (1.00 + increment_pct * i) for i in range(int(0.30 / increment_pct) + 1)]
    best_strike = grid[0]
    best_err = float("inf")
    for k in grid:
        delta = bs.bs_greeks(option_type, spot, k, t_years, rate, iv).delta
        err = abs(delta - target_delta)
        if err < best_err:
            best_err = err
            best_strike = k
    return round(best_strike, 2)
