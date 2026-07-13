"""Performance statistics — always the full picture, never just CAGR.

Every stat here has the formula in its docstring and a known-value test.
Daily frequency assumed (annualization by 252 / calendar years by date).
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Sequence

from pydantic import BaseModel

TRADING_DAYS = 252


def daily_returns(equity: Sequence[float]) -> list[float]:
    """Simple daily returns from an equity curve."""
    return [
        equity[i + 1] / equity[i] - 1.0
        for i in range(len(equity) - 1)
        if equity[i] > 0
    ]


def cagr(equity: Sequence[float], dates: Sequence[dt.date]) -> float:
    """(end/start)^(1/years) - 1, years measured by calendar dates."""
    if len(equity) < 2 or equity[0] <= 0:
        return 0.0
    years = (dates[-1] - dates[0]).days / 365.25
    if years <= 0:
        return 0.0
    return float((equity[-1] / equity[0]) ** (1.0 / years)) - 1.0


def annualized_vol(returns: Sequence[float]) -> float:
    """std(daily returns, ddof=1) x sqrt(252)."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def sharpe(returns: Sequence[float], rf_annual: float = 0.0) -> float:
    """(mean excess daily return / std) x sqrt(252). 0 when undefined."""
    n = len(returns)
    if n < 2:
        return 0.0
    rf_daily = rf_annual / TRADING_DAYS
    excess = [r - rf_daily for r in returns]
    mean = sum(excess) / n
    var = sum((r - mean) ** 2 for r in excess) / (n - 1)
    if var <= 0:
        return 0.0
    return mean / math.sqrt(var) * math.sqrt(TRADING_DAYS)


def sortino(returns: Sequence[float], rf_annual: float = 0.0) -> float:
    """Like Sharpe but denominator = downside deviation (returns < target).

    Infinite-downside-free periods return 0 rather than inf — a series
    with no losing days yet has no measurable downside risk, not zero.
    """
    n = len(returns)
    if n < 2:
        return 0.0
    rf_daily = rf_annual / TRADING_DAYS
    excess = [r - rf_daily for r in returns]
    mean = sum(excess) / n
    downside = [min(r, 0.0) ** 2 for r in excess]
    dd = math.sqrt(sum(downside) / n)
    if dd <= 0:
        return 0.0
    return mean / dd * math.sqrt(TRADING_DAYS)


def max_drawdown(
    equity: Sequence[float], dates: Sequence[dt.date]
) -> tuple[float, int]:
    """(worst peak-to-trough fraction, longest underwater stretch in days).

    Depth is positive (0.25 = -25%); duration is the longest run of days
    spent below a prior peak, whether or not it contains the deepest low.
    """
    if not equity:
        return 0.0, 0
    peak = equity[0]
    peak_date = dates[0]
    worst = 0.0
    longest_underwater = 0
    underwater = False
    for value, date in zip(equity, dates):
        if value >= peak:
            if underwater:
                # Recovery day closes the drawdown: duration is peak-to-recovery.
                longest_underwater = max(
                    longest_underwater, (date - peak_date).days
                )
                underwater = False
            peak = value
            peak_date = date
        else:
            underwater = True
            worst = max(worst, 1.0 - value / peak)
            # Still-open drawdown counts up to the latest bar.
            longest_underwater = max(longest_underwater, (date - peak_date).days)
    return worst, longest_underwater


def ulcer_index(equity: Sequence[float]) -> float:
    """sqrt(mean(drawdown_pct^2)) — penalizes depth AND duration of pain."""
    if not equity:
        return 0.0
    peak = equity[0]
    sq_sum = 0.0
    for value in equity:
        peak = max(peak, value)
        dd = (1.0 - value / peak) * 100.0
        sq_sum += dd * dd
    return math.sqrt(sq_sum / len(equity))


def cvar_95(returns: Sequence[float]) -> float:
    """Expected shortfall: mean of the worst 5% of daily returns.

    Reported as a negative number (it is a loss). Needs >= 20 returns
    for the tail to contain at least one observation.
    """
    if len(returns) < 20:
        return 0.0
    ordered = sorted(returns)
    k = max(int(len(ordered) * 0.05), 1)
    tail = ordered[:k]
    return sum(tail) / len(tail)


class TradeStats(BaseModel):
    n_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    premium_capture: float  # net option P&L / gross premium collected


def trade_stats(
    pnls: Sequence[float], gross_premium: float
) -> TradeStats:
    """Per-trade statistics. premium_capture is the seller's efficiency:
    of every dollar of premium sold, how much was kept net of buybacks,
    losses, and costs."""
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    return TradeStats(
        n_trades=n,
        win_rate=len(wins) / n if n else 0.0,
        avg_win=sum(wins) / len(wins) if wins else 0.0,
        avg_loss=sum(losses) / len(losses) if losses else 0.0,
        premium_capture=(sum(pnls) / gross_premium) if gross_premium > 0 else 0.0,
    )


class PerformanceSummary(BaseModel):
    label: str
    cagr: float
    annualized_vol: float
    sharpe: float
    sortino: float
    max_drawdown: float
    max_drawdown_days: int
    ulcer: float
    cvar_95: float


def summarize_equity(
    label: str,
    equity: Sequence[float],
    dates: Sequence[dt.date],
    rf_annual: float = 0.0,
) -> PerformanceSummary:
    rets = daily_returns(equity)
    dd, dd_days = max_drawdown(equity, dates)
    return PerformanceSummary(
        label=label,
        cagr=cagr(equity, dates),
        annualized_vol=annualized_vol(rets),
        sharpe=sharpe(rets, rf_annual),
        sortino=sortino(rets, rf_annual),
        max_drawdown=dd,
        max_drawdown_days=dd_days,
        ulcer=ulcer_index(equity),
        cvar_95=cvar_95(rets),
    )
