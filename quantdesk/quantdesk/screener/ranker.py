"""Composite opportunity score: weighted z-scores across the passing set.

Score components (weights in config.screener.weights):
  * vrp            — how overpriced options are vs realized vol
  * iv_rank        — how rich IV is vs its own recent range
  * liquidity      — (z(log10(1+OI)) - z(spread%)) / 2: deep + tight books
  * premium_yield  — annualized credit / collateral at the best strike

Z-scoring is done across the symbols that PASSED the filters in this
scan, so a score is always relative to today's opportunity set. With
one passing symbol every z is 0 by construction — the score only means
something when there is a cross-section to compare against.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from quantdesk.config import QuantDeskConfig
from quantdesk.screener.models import ScoreBreakdown, ScreenResult


def zscores(values: Sequence[float]) -> list[float]:
    """Population z-scores; all zeros when the cross-section is degenerate."""
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    if std < 1e-12:
        return [0.0] * n
    return [(v - mean) / std for v in values]


def score_results(
    results: list[ScreenResult], config: QuantDeskConfig
) -> list[ScreenResult]:
    """Attach a ScoreBreakdown to every passing result; return them ranked.

    Non-passing results are left unscored (they are excluded, not bad).
    """
    passing = [r for r in results if r.passed and r.metrics is not None]
    if not passing:
        return []

    vrp_vals = [r.metrics.vrp for r in passing if r.metrics]
    ivr_vals = [r.metrics.iv_rank for r in passing if r.metrics]
    oi_vals: list[float] = []
    spread_vals: list[float] = []
    yield_vals: list[float] = []
    for r in passing:
        assert r.metrics is not None and r.metrics.best_strike is not None
        best = r.metrics.best_strike
        oi_vals.append(math.log10(1 + (best.open_interest or 0)))
        spread_vals.append(best.spread_pct if best.spread_pct is not None else 1.0)
        yield_vals.append(best.annualized_yield)

    z_vrp = zscores(vrp_vals)
    z_ivr = zscores(ivr_vals)
    z_oi = zscores(oi_vals)
    z_spread = zscores(spread_vals)
    z_yield = zscores(yield_vals)

    w = config.screener.weights
    for i, r in enumerate(passing):
        liquidity_z = (z_oi[i] - z_spread[i]) / 2.0
        total = (
            w.vrp * z_vrp[i]
            + w.iv_rank * z_ivr[i]
            + w.liquidity * liquidity_z
            + w.premium_yield * z_yield[i]
        )
        r.score = ScoreBreakdown(
            vrp_z=z_vrp[i],
            iv_rank_z=z_ivr[i],
            liquidity_z=liquidity_z,
            premium_yield_z=z_yield[i],
            total=total,
        )

    passing.sort(key=lambda r: r.score.total if r.score else 0.0, reverse=True)
    return passing
