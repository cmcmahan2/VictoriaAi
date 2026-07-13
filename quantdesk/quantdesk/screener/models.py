"""Screener domain models: per-symbol metrics, filter results, scores."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from quantdesk.data.models import OptionContract


class StrikeCandidate(BaseModel):
    """One short-put strike inside the target delta band."""

    contract: OptionContract
    iv: float
    delta: float
    mid: float
    spread_pct: float | None
    open_interest: int | None
    volume: int | None
    collateral: float          # strike x 100 (cash-secured)
    annualized_yield: float    # (mid / strike) x (365 / dte)


class SymbolMetrics(BaseModel):
    """Everything the filter pipeline and ranker need for one symbol."""

    symbol: str
    spot: float
    expiry: dt.date
    dte: int
    atm_iv: float
    rv_20d: float
    vrp: float
    iv_rank: float
    iv_rank_source: str        # "own-iv-history" | "rv-bootstrap"
    iv_history_days: int
    dma_50: float
    next_earnings: dt.date | None
    best_strike: StrikeCandidate | None  # highest-yield strike in delta band


class FilterResult(BaseModel):
    """Outcome of one filter for one symbol; details make exclusions queryable."""

    name: str
    passed: bool
    detail: str


class ScoreBreakdown(BaseModel):
    """Composite score: weighted z-scores across the passing set."""

    vrp_z: float
    iv_rank_z: float
    liquidity_z: float
    premium_yield_z: float
    total: float


class ScreenResult(BaseModel):
    """Full screening outcome for one symbol."""

    symbol: str
    metrics: SymbolMetrics | None = None
    filters: list[FilterResult] = []
    score: ScoreBreakdown | None = None
    error: str | None = None   # data failure — excluded, reason preserved

    @property
    def passed(self) -> bool:
        return (
            self.error is None
            and self.metrics is not None
            and bool(self.filters)
            and all(f.passed for f in self.filters)
        )

    @property
    def exclusion_reasons(self) -> list[str]:
        if self.error is not None:
            return [f"data-error: {self.error}"]
        return [f"{f.name}: {f.detail}" for f in self.filters if not f.passed]
