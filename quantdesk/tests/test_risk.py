"""Phase 4 acceptance tests: sizing caps bind; sector and correlation
rules fire on a deliberately concentrated all-tech book."""

from __future__ import annotations

import math

import numpy as np
import pytest

from quantdesk.config import QuantDeskConfig
from quantdesk.risk.portfolio import (
    Position,
    aggregate,
    avg_abs_correlation_to_book,
    beta,
    correlation,
    correlation_matrix,
)
from quantdesk.risk.rules import Severity, check_proposal
from quantdesk.risk.sizing import kelly_binary, recommend_size

CFG = QuantDeskConfig()


class TestKelly:
    def test_known_value(self) -> None:
        # p=0.6, even payoff: f* = (0.6*1 - 0.4)/1 = 0.20
        assert kelly_binary(0.6, 100.0, 100.0) == pytest.approx(0.20)

    def test_uneven_payoff(self) -> None:
        # p=0.74, win 1, loss 2: b=0.5 -> (0.74*0.5 - 0.26)/0.5 = 0.22
        assert kelly_binary(0.74, 1.0, 2.0) == pytest.approx(0.22)

    def test_negative_edge_floors_at_zero(self) -> None:
        assert kelly_binary(0.30, 100.0, 100.0) == 0.0

    def test_invalid_inputs_raise(self) -> None:
        with pytest.raises(ValueError):
            kelly_binary(1.5, 1.0, 1.0)
        with pytest.raises(ValueError):
            kelly_binary(0.5, -1.0, 1.0)


class TestRecommendSize:
    def test_fixed_cap_binds_over_kelly(self) -> None:
        # Huge edge: Kelly would bet far more than the 5% cap allows.
        rec = recommend_size(
            account_usd=100_000.0,
            collateral_per_contract=1_000.0,
            pop=0.95,
            win_per_contract=500.0,
            loss_per_contract=200.0,
            vix=18.0,
            config=CFG,
        )
        assert rec.final_fraction == pytest.approx(CFG.risk.max_position_pct)
        assert rec.contracts == 5  # 5% of 100k / 1k
        assert any("capped" in n for n in rec.notes)

    def test_kelly_can_size_below_cap(self) -> None:
        # Thin edge: quarter-Kelly lands under the 5% cap.
        rec = recommend_size(
            account_usd=100_000.0,
            collateral_per_contract=1_000.0,
            pop=0.70,
            win_per_contract=100.0,
            loss_per_contract=200.0,
            vix=18.0,
            config=CFG,
        )
        # f* = (0.7*0.5 - 0.3)/0.5 = 0.10; quarter -> 2.5% < 5% cap.
        assert rec.kelly_raw == pytest.approx(0.10)
        assert rec.final_fraction == pytest.approx(0.025)
        assert rec.contracts == 2

    def test_vix_regime_halves_and_freezes(self) -> None:
        kwargs = dict(
            account_usd=100_000.0,
            collateral_per_contract=1_000.0,
            pop=0.95,
            win_per_contract=500.0,
            loss_per_contract=200.0,
            config=CFG,
        )
        normal = recommend_size(vix=18.0, **kwargs)  # type: ignore[arg-type]
        high = recommend_size(vix=34.0, **kwargs)  # type: ignore[arg-type]
        frozen = recommend_size(vix=45.0, **kwargs)  # type: ignore[arg-type]
        assert high.final_fraction == pytest.approx(normal.final_fraction / 2)
        assert frozen.contracts == 0
        assert frozen.final_fraction == 0.0

    def test_tiny_account_honest_zero(self) -> None:
        # The user's actual starting point: ~$73 USD cannot secure a put.
        rec = recommend_size(
            account_usd=73.0,
            collateral_per_contract=9_500.0,
            pop=0.80,
            win_per_contract=90.0,
            loss_per_contract=180.0,
            vix=18.0,
            config=CFG,
        )
        assert rec.contracts == 0
        assert any("too small" in n for n in rec.notes)

    def test_no_edge_notes_zero_kelly(self) -> None:
        rec = recommend_size(
            account_usd=100_000.0,
            collateral_per_contract=1_000.0,
            pop=0.40,
            win_per_contract=100.0,
            loss_per_contract=200.0,
            vix=18.0,
            config=CFG,
        )
        assert rec.kelly_raw == 0.0
        assert any("NO EDGE" in n for n in rec.notes)


def tech_position(symbol: str, collateral: float = 900.0) -> Position:
    return Position(
        symbol=symbol,
        strategy="csp",
        spot=100.0,
        delta_shares=20.0,
        theta_usd_day=5.0,
        vega_usd_pt=-8.0,
        collateral=collateral,
        sector="Technology",
        beta=1.3,
    )


def correlated_closes(seed_series: list[float], noise_scale: float, seed: int) -> list[float]:
    """A series driven by a common factor + small idiosyncratic noise."""
    rng = np.random.default_rng(seed)
    factor_returns = np.diff(np.log(np.asarray(seed_series)))
    noise = rng.normal(0.0, noise_scale, len(factor_returns))
    prices = [100.0]
    for r, n in zip(factor_returns, noise):
        prices.append(prices[-1] * math.exp(r + n))
    return prices


class TestPortfolio:
    def test_aggregate_dollar_greeks(self) -> None:
        book = [tech_position("AAPL"), tech_position("MSFT")]
        view = aggregate(book, spy_spot=500.0)
        assert view.n_positions == 2
        assert view.delta_dollars == pytest.approx(2 * 20 * 100.0)
        assert view.theta_usd_day == pytest.approx(10.0)
        assert view.vega_usd_pt == pytest.approx(-16.0)
        assert view.collateral_total == pytest.approx(1_800.0)
        # beta-weighted: 2 * 20 * 100 * 1.3 / 500 = 10.4 SPY-share equivalents
        assert view.beta_weighted_delta_spy == pytest.approx(10.4)
        assert view.sector_counts == {"Technology": 2}

    def test_correlation_perfect_and_zero(self) -> None:
        rng = np.random.default_rng(11)
        base = list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 120))))
        assert correlation(base, base) == pytest.approx(1.0)
        independent = list(100 * np.exp(np.cumsum(
            np.random.default_rng(99).normal(0, 0.01, 120)
        )))
        assert abs(correlation(base, independent)) < 0.35  # near zero

    def test_beta_of_benchmark_is_one(self) -> None:
        rng = np.random.default_rng(5)
        spy = list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 120))))
        assert beta(spy, spy) == pytest.approx(1.0)
        # 2x-levered series has beta ~2.
        levered = [100.0]
        r = np.diff(np.log(np.asarray(spy)))
        for x in r:
            levered.append(levered[-1] * math.exp(2 * x))
        assert beta(levered, spy) == pytest.approx(2.0, rel=1e-6)

    def test_correlation_matrix_keys(self) -> None:
        rng = np.random.default_rng(1)
        make = lambda s: list(100 * np.exp(np.cumsum(  # noqa: E731
            np.random.default_rng(s).normal(0, 0.01, 100)
        )))
        m = correlation_matrix({"A": make(1), "B": make(2), "C": make(3)})
        assert set(m) == {("A", "B"), ("A", "C"), ("B", "C")}


class TestRuleEngineAcceptance:
    """Spec acceptance: a 6-position all-tech book must trip the rules."""

    def setup_method(self) -> None:
        self.cfg = QuantDeskConfig()
        self.cfg.account.currency = "USD"
        self.account = 100_000.0
        self.book = [
            tech_position(s)
            for s in ("AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "META")
        ]
        rng = np.random.default_rng(42)
        factor = list(100 * np.exp(np.cumsum(rng.normal(0, 0.012, 120))))
        self.close_map: dict[str, list[float]] = {
            s: correlated_closes(factor, 0.002, i)
            for i, s in enumerate(
                ("AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "META", "ORCL")
            )
        }

    def test_sector_rule_fires(self) -> None:
        verdict = check_proposal(
            symbol="ORCL",
            sector="Technology",
            collateral_usd=900.0,
            account_usd=self.account,
            book=self.book,
            vix=18.0,
            config=self.cfg,
            close_map=self.close_map,
        )
        failed = {c.rule for c in verdict.failures}
        assert "sector-concentration" in failed
        assert verdict.blocked

    def test_correlation_rule_fires(self) -> None:
        verdict = check_proposal(
            symbol="ORCL",
            sector="Energy",  # dodge the sector rule to isolate correlation
            collateral_usd=900.0,
            account_usd=self.account,
            book=self.book,
            vix=18.0,
            config=self.cfg,
            close_map=self.close_map,
        )
        corr = next(c for c in verdict.checks if c.rule == "correlation")
        assert not corr.passed
        assert corr.severity == Severity.WARN
        assert not verdict.blocked  # warning, not a hard block

    def test_sizing_caps_bind(self) -> None:
        verdict = check_proposal(
            symbol="XOM",
            sector="Energy",
            collateral_usd=6_000.0,  # > 5% of 100k
            account_usd=self.account,
            book=[],
            vix=18.0,
            config=self.cfg,
        )
        pos_cap = next(c for c in verdict.checks if c.rule == "position-size-cap")
        assert not pos_cap.passed and verdict.blocked

    def test_deployment_cap_fires(self) -> None:
        # Book already deploys 5,400 of the 20,000 cap; a 15,000 add busts it.
        verdict = check_proposal(
            symbol="XOM",
            sector="Energy",
            collateral_usd=4_900.0,
            account_usd=25_000.0,  # cap = 5,000; book 5,400 already over
            book=self.book,
            vix=18.0,
            config=self.cfg,
        )
        dep = next(c for c in verdict.checks if c.rule == "deployment-cap")
        assert not dep.passed and verdict.blocked

    def test_vix_freeze_blocks(self) -> None:
        verdict = check_proposal(
            symbol="XOM",
            sector="Energy",
            collateral_usd=900.0,
            account_usd=self.account,
            book=[],
            vix=45.0,
            config=self.cfg,
        )
        vixr = next(c for c in verdict.checks if c.rule == "vix-regime")
        assert not vixr.passed and vixr.severity == Severity.BLOCK
        assert verdict.blocked

    def test_clean_proposal_passes_everything(self) -> None:
        verdict = check_proposal(
            symbol="XOM",
            sector="Energy",
            collateral_usd=900.0,
            account_usd=self.account,
            book=self.book[:1],
            vix=18.0,
            config=self.cfg,
            close_map={
                "XOM": list(
                    100 * np.exp(np.cumsum(
                        np.random.default_rng(77).normal(0, 0.01, 120)
                    ))
                ),
                "AAPL": self.close_map["AAPL"],
            },
        )
        assert not verdict.blocked
        assert verdict.failures == []

    def test_no_close_map_reports_unevaluated(self) -> None:
        verdict = check_proposal(
            symbol="XOM",
            sector="Energy",
            collateral_usd=900.0,
            account_usd=self.account,
            book=self.book,
            vix=18.0,
            config=self.cfg,
        )
        corr = next(c for c in verdict.checks if c.rule == "correlation")
        assert corr.passed and "not evaluated" in corr.detail
