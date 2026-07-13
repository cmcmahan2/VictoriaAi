"""Composable screening filters. Each filter is a pure function.

A filter takes ``SymbolMetrics`` and returns a ``FilterResult`` with a
human-readable detail string either way, so ``scan --explain SYMBOL``
can show exactly why a name was excluded. Filters never raise on bad
metrics — missing data is a documented failure, not a crash.
"""

from __future__ import annotations

from collections.abc import Callable

from quantdesk.config import QuantDeskConfig
from quantdesk.screener.models import FilterResult, SymbolMetrics

Filter = Callable[[SymbolMetrics], FilterResult]


def liquidity_filter(config: QuantDeskConfig) -> Filter:
    """Open interest, volume, and bid-ask spread at the target strike.

    Wide spreads are the #1 retail killer: crossing a 10% spread twice
    costs more than most edges pay. Strict by design.
    """
    min_oi = config.screener.min_open_interest
    max_spread = config.screener.max_spread_pct
    min_vol = config.screener.min_option_volume

    def check(m: SymbolMetrics) -> FilterResult:
        name = "liquidity"
        best = m.best_strike
        if best is None:
            return FilterResult(
                name=name, passed=False,
                detail="no quotable strike in the target delta band",
            )
        oi = best.open_interest or 0
        vol = best.volume or 0
        if oi < min_oi:
            return FilterResult(
                name=name, passed=False,
                detail=f"open interest {oi} < {min_oi} at {best.contract.strike:g}",
            )
        if vol < min_vol:
            return FilterResult(
                name=name, passed=False,
                detail=f"option volume {vol} < {min_vol} at {best.contract.strike:g}",
            )
        if best.spread_pct is None:
            return FilterResult(
                name=name, passed=False, detail="no two-sided quote (missing bid/ask)"
            )
        if best.spread_pct > max_spread:
            return FilterResult(
                name=name, passed=False,
                detail=f"bid-ask spread {best.spread_pct:.1%} of mid > {max_spread:.0%}",
            )
        return FilterResult(
            name=name, passed=True,
            detail=f"OI {oi}, vol {vol}, spread {best.spread_pct:.1%}",
        )

    return check


def vol_richness_filter(config: QuantDeskConfig) -> Filter:
    """IV rank above threshold and positive VRP — the reason to sell at all."""
    iv_rank_min = config.screener.iv_rank_min

    def check(m: SymbolMetrics) -> FilterResult:
        name = "vol-richness"
        if m.iv_rank < iv_rank_min:
            return FilterResult(
                name=name, passed=False,
                detail=f"IV rank {m.iv_rank:.0f} < {iv_rank_min:.0f} "
                f"(source: {m.iv_rank_source}, {m.iv_history_days}d)",
            )
        if m.vrp <= 0:
            return FilterResult(
                name=name, passed=False,
                detail=f"VRP {m.vrp:+.1%} — options not rich vs realized",
            )
        return FilterResult(
            name=name, passed=True,
            detail=f"IV rank {m.iv_rank:.0f} ({m.iv_rank_source}), VRP {m.vrp:+.1%}",
        )

    return check


def earnings_blackout_filter(config: QuantDeskConfig) -> Filter:
    """Exclude when earnings land before expiry (default ON).

    Earnings gaps are exactly the fat-tail event a premium seller must
    not hold through. Unknown earnings dates pass with a warning —
    yfinance's calendar is too flaky to exclude on absence of data —
    but the detail string says so.
    """
    enabled = config.strategy.earnings_blackout

    def check(m: SymbolMetrics) -> FilterResult:
        name = "earnings-blackout"
        if not enabled:
            return FilterResult(name=name, passed=True, detail="blackout disabled")
        if m.next_earnings is None:
            return FilterResult(
                name=name, passed=True,
                detail="earnings date UNKNOWN (yfinance) — verify manually",
            )
        if m.next_earnings <= m.expiry:
            return FilterResult(
                name=name, passed=False,
                detail=f"earnings {m.next_earnings} before expiry {m.expiry}",
            )
        return FilterResult(
            name=name, passed=True, detail=f"next earnings {m.next_earnings} after expiry"
        )

    return check


def affordability_filter(max_position_usd: float) -> Filter:
    """CSP collateral (strike x 100) must fit the per-position cap.

    The cap arrives in USD (converted from account currency upstream).
    """

    def check(m: SymbolMetrics) -> FilterResult:
        name = "affordability"
        best = m.best_strike
        if best is None:
            return FilterResult(
                name=name, passed=False, detail="no strike in the target delta band"
            )
        if best.collateral > max_position_usd:
            return FilterResult(
                name=name, passed=False,
                detail=f"collateral ${best.collateral:,.0f} > per-position cap "
                f"${max_position_usd:,.0f}",
            )
        return FilterResult(
            name=name, passed=True,
            detail=f"collateral ${best.collateral:,.0f} within cap "
            f"${max_position_usd:,.0f}",
        )

    return check


def freefall_filter(config: QuantDeskConfig) -> Filter:
    """Exclude names in freefall: spot < ratio x 50-day moving average.

    Selling puts into a knife is picking up the tail risk everyone else
    is paying to shed.
    """
    ratio = config.screener.freefall_dma_ratio

    def check(m: SymbolMetrics) -> FilterResult:
        name = "trend-sanity"
        floor = ratio * m.dma_50
        if m.spot < floor:
            return FilterResult(
                name=name, passed=False,
                detail=f"spot {m.spot:,.2f} < {ratio:.0%} of 50dma "
                f"({m.dma_50:,.2f}) — freefall",
            )
        return FilterResult(
            name=name, passed=True,
            detail=f"spot {m.spot:,.2f} vs 50dma {m.dma_50:,.2f}",
        )

    return check


def csp_pipeline(config: QuantDeskConfig, max_position_usd: float) -> list[Filter]:
    """The full CSP filter pipeline, in evaluation order."""
    return [
        liquidity_filter(config),
        vol_richness_filter(config),
        earnings_blackout_filter(config),
        affordability_filter(max_position_usd),
        freefall_filter(config),
    ]


def run_filters(m: SymbolMetrics, filters: list[Filter]) -> list[FilterResult]:
    """Run every filter (no short-circuit) so --explain shows the full picture."""
    return [f(m) for f in filters]
