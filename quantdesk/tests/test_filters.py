"""Unit tests for the composable screening filters."""

from __future__ import annotations

import datetime as dt

from quantdesk.config import QuantDeskConfig
from quantdesk.data.models import OptionContract
from quantdesk.screener.filters import (
    affordability_filter,
    csp_pipeline,
    earnings_blackout_filter,
    freefall_filter,
    liquidity_filter,
    run_filters,
    vol_richness_filter,
)
from quantdesk.screener.models import StrikeCandidate, SymbolMetrics


def make_strike(
    oi: int = 5000,
    volume: int = 1000,
    spread_pct: float | None = 0.02,
    strike: float = 95.0,
) -> StrikeCandidate:
    return StrikeCandidate(
        contract=OptionContract(
            contract_symbol="X-put-95",
            underlying="X",
            option_type="put",
            strike=strike,
            expiry=dt.date.today() + dt.timedelta(days=35),
            bid=0.9,
            ask=0.95,
        ),
        iv=0.25,
        delta=-0.21,
        mid=0.92,
        spread_pct=spread_pct,
        open_interest=oi,
        volume=volume,
        collateral=strike * 100,
        annualized_yield=0.12,
    )


def make_metrics(**overrides: object) -> SymbolMetrics:
    base: dict[str, object] = dict(
        symbol="X",
        spot=100.0,
        expiry=dt.date.today() + dt.timedelta(days=35),
        dte=35,
        atm_iv=0.25,
        rv_20d=0.20,
        vrp=0.05,
        iv_rank=60.0,
        iv_rank_source="own-iv-history",
        iv_history_days=100,
        dma_50=101.0,
        next_earnings=dt.date.today() + dt.timedelta(days=60),
        best_strike=make_strike(),
    )
    base.update(overrides)
    return SymbolMetrics.model_validate(base)


CFG = QuantDeskConfig()


class TestLiquidity:
    def test_passes_liquid_strike(self) -> None:
        assert liquidity_filter(CFG)(make_metrics()).passed

    def test_fails_low_open_interest(self) -> None:
        r = liquidity_filter(CFG)(make_metrics(best_strike=make_strike(oi=100)))
        assert not r.passed and "open interest" in r.detail

    def test_fails_zero_volume(self) -> None:
        r = liquidity_filter(CFG)(make_metrics(best_strike=make_strike(volume=0)))
        assert not r.passed and "volume" in r.detail

    def test_fails_wide_spread(self) -> None:
        r = liquidity_filter(CFG)(
            make_metrics(best_strike=make_strike(spread_pct=0.09))
        )
        assert not r.passed and "spread" in r.detail

    def test_fails_one_sided_quote(self) -> None:
        r = liquidity_filter(CFG)(
            make_metrics(best_strike=make_strike(spread_pct=None))
        )
        assert not r.passed

    def test_fails_no_strike_in_band(self) -> None:
        r = liquidity_filter(CFG)(make_metrics(best_strike=None))
        assert not r.passed and "delta band" in r.detail


class TestVolRichness:
    def test_passes_rich_vol(self) -> None:
        assert vol_richness_filter(CFG)(make_metrics()).passed

    def test_fails_low_iv_rank(self) -> None:
        r = vol_richness_filter(CFG)(make_metrics(iv_rank=30.0))
        assert not r.passed and "IV rank" in r.detail

    def test_fails_negative_vrp(self) -> None:
        r = vol_richness_filter(CFG)(make_metrics(vrp=-0.02))
        assert not r.passed and "not rich" in r.detail

    def test_detail_reveals_rank_source(self) -> None:
        r = vol_richness_filter(CFG)(
            make_metrics(iv_rank=20.0, iv_rank_source="rv-bootstrap")
        )
        assert "rv-bootstrap" in r.detail


class TestEarningsBlackout:
    def test_fails_earnings_before_expiry(self) -> None:
        r = earnings_blackout_filter(CFG)(
            make_metrics(next_earnings=dt.date.today() + dt.timedelta(days=10))
        )
        assert not r.passed and "earnings" in r.detail

    def test_passes_earnings_after_expiry(self) -> None:
        assert earnings_blackout_filter(CFG)(make_metrics()).passed

    def test_unknown_earnings_passes_with_warning(self) -> None:
        r = earnings_blackout_filter(CFG)(make_metrics(next_earnings=None))
        assert r.passed and "UNKNOWN" in r.detail

    def test_toggle_off_always_passes(self) -> None:
        cfg = QuantDeskConfig()
        cfg.strategy.earnings_blackout = False
        r = earnings_blackout_filter(cfg)(
            make_metrics(next_earnings=dt.date.today() + dt.timedelta(days=10))
        )
        assert r.passed and "disabled" in r.detail


class TestAffordability:
    def test_passes_within_cap(self) -> None:
        assert affordability_filter(10_000.0)(make_metrics()).passed

    def test_fails_over_cap(self) -> None:
        r = affordability_filter(500.0)(make_metrics())  # collateral 9,500
        assert not r.passed and "cap" in r.detail


class TestFreefall:
    def test_passes_normal_trend(self) -> None:
        assert freefall_filter(CFG)(make_metrics()).passed

    def test_fails_freefall(self) -> None:
        r = freefall_filter(CFG)(make_metrics(spot=80.0, dma_50=100.0))
        assert not r.passed and "freefall" in r.detail

    def test_boundary_at_ratio_passes(self) -> None:
        # spot exactly 85% of dma50: not strictly below -> pass.
        r = freefall_filter(CFG)(make_metrics(spot=85.0, dma_50=100.0))
        assert r.passed


class TestPipeline:
    def test_all_filters_run_no_short_circuit(self) -> None:
        m = make_metrics(iv_rank=10.0, spot=50.0, dma_50=100.0)  # 2 failures
        results = run_filters(m, csp_pipeline(CFG, 10_000.0))
        assert len(results) == 5
        failed = {r.name for r in results if not r.passed}
        assert failed == {"vol-richness", "trend-sanity"}
