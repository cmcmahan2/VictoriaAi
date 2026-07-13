"""Portfolio aggregation: dollar Greeks, beta-weighted delta, concentration.

Positions are lightweight snapshots (the Phase 5 journal constructs them
from live trades). All math here is pure so tests can build any book
they want.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, Field


class Position(BaseModel):
    """An open position's risk snapshot, per total position (all contracts)."""

    symbol: str
    strategy: str
    contracts: int = 1
    spot: float
    delta_shares: float        # share-equivalent exposure
    theta_usd_day: float
    vega_usd_pt: float
    collateral: float
    sector: str = "Unknown"
    beta: float = 1.0          # vs SPY; provider/journal fills this in


class PortfolioView(BaseModel):
    n_positions: int
    delta_dollars: float               # sum(delta_shares x spot)
    beta_weighted_delta_spy: float | None  # SPY-share equivalents
    theta_usd_day: float
    vega_usd_pt: float
    collateral_total: float
    sector_counts: dict[str, int] = Field(default_factory=dict)


def aggregate(
    positions: Sequence[Position], spy_spot: float | None = None
) -> PortfolioView:
    """Aggregate book risk. Beta-weighting needs spy_spot; else None."""
    delta_dollars = sum(p.delta_shares * p.spot for p in positions)
    bw: float | None = None
    if spy_spot is not None and spy_spot > 0:
        bw = sum(p.delta_shares * p.spot * p.beta for p in positions) / spy_spot
    sectors: dict[str, int] = {}
    for p in positions:
        sectors[p.sector] = sectors.get(p.sector, 0) + 1
    return PortfolioView(
        n_positions=len(positions),
        delta_dollars=delta_dollars,
        beta_weighted_delta_spy=bw,
        theta_usd_day=sum(p.theta_usd_day for p in positions),
        vega_usd_pt=sum(p.vega_usd_pt for p in positions),
        collateral_total=sum(p.collateral for p in positions),
        sector_counts=sectors,
    )


def _log_returns(closes: Sequence[float], window: int) -> list[float]:
    tail = list(closes[-(window + 1) :])
    return [math.log(tail[i + 1] / tail[i]) for i in range(len(tail) - 1)]


def correlation(
    closes_a: Sequence[float], closes_b: Sequence[float], window: int = 90
) -> float:
    """Pearson correlation of trailing daily log returns.

    Requires window+1 closes on both series; raises otherwise. Returns
    0.0 when either series is flat (undefined correlation, no signal).
    """
    if len(closes_a) < window + 1 or len(closes_b) < window + 1:
        raise ValueError(f"need at least {window + 1} closes on both series")
    ra = _log_returns(closes_a, window)
    rb = _log_returns(closes_b, window)
    ma = sum(ra) / len(ra)
    mb = sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    var_a = sum((x - ma) ** 2 for x in ra)
    var_b = sum((y - mb) ** 2 for y in rb)
    if var_a < 1e-18 or var_b < 1e-18:
        return 0.0
    return cov / math.sqrt(var_a * var_b)


def beta(
    closes_asset: Sequence[float],
    closes_benchmark: Sequence[float],
    window: int = 90,
) -> float:
    """CAPM beta = cov(asset, benchmark) / var(benchmark) on log returns."""
    if len(closes_asset) < window + 1 or len(closes_benchmark) < window + 1:
        raise ValueError(f"need at least {window + 1} closes on both series")
    ra = _log_returns(closes_asset, window)
    rb = _log_returns(closes_benchmark, window)
    ma = sum(ra) / len(ra)
    mb = sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    var_b = sum((y - mb) ** 2 for y in rb)
    if var_b < 1e-18:
        return 0.0
    return cov / var_b


def correlation_matrix(
    close_map: dict[str, Sequence[float]], window: int = 90
) -> dict[tuple[str, str], float]:
    """Pairwise trailing correlations, keyed by sorted symbol pair."""
    symbols = sorted(close_map)
    out: dict[tuple[str, str], float] = {}
    for i, a in enumerate(symbols):
        for b_sym in symbols[i + 1 :]:
            out[(a, b_sym)] = correlation(close_map[a], close_map[b_sym], window)
    return out


def avg_abs_correlation_to_book(
    new_symbol: str,
    book_symbols: Sequence[str],
    close_map: dict[str, Sequence[float]],
    window: int = 90,
) -> float | None:
    """Mean |correlation| of a candidate against the existing book.

    None when the book is empty or no overlapping data exists.
    """
    others = [s for s in book_symbols if s != new_symbol and s in close_map]
    if not others or new_symbol not in close_map:
        return None
    cors = [
        abs(correlation(close_map[new_symbol], close_map[s], window)) for s in others
    ]
    return sum(cors) / len(cors)
