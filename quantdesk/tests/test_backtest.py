"""Tests for synthetic pricing, costs, metrics, and the backtest engine."""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pytest

from quantdesk.backtest.costs import SPREAD_FLOOR, CostModel
from quantdesk.backtest.engine import ExitReason, run_backtest, walk_forward
from quantdesk.backtest.metrics import (
    cagr,
    cvar_95,
    daily_returns,
    max_drawdown,
    sharpe,
    sortino,
    summarize_equity,
    trade_stats,
    ulcer_index,
)
from quantdesk.backtest.synthetic import (
    SYNTHETIC_WARNING,
    strike_for_delta,
    synthetic_iv,
    synthetic_price,
)
from quantdesk.config import QuantDeskConfig
from quantdesk.data.models import Bar, PriceHistory

CFG = QuantDeskConfig()


def make_history(
    closes: list[float], start: dt.date = dt.date(2024, 1, 1)
) -> PriceHistory:
    bars = [
        Bar(
            date=start + dt.timedelta(days=i),
            open=c, high=c * 1.004, low=c * 0.996, close=c, volume=1e6,
        )
        for i, c in enumerate(closes)
    ]
    return PriceHistory(symbol="TEST", bars=bars)


def alternating(n: int, vol: float = 0.20, start: float = 100.0) -> list[float]:
    a = vol / math.sqrt(252)
    out = [start]
    for i in range(n - 1):
        out.append(out[-1] * math.exp(a if i % 2 else -a))
    return out


def trending(n: int, daily: float, vol: float = 0.15, start: float = 100.0) -> list[float]:
    a = vol / math.sqrt(252)
    out = [start]
    for i in range(n - 1):
        out.append(out[-1] * math.exp(daily + (a if i % 2 else -a)))
    return out


class TestSynthetic:
    def test_iv_proxy_is_rv_times_richness(self) -> None:
        closes = alternating(30)
        from quantdesk.analytics.volatility import close_to_close_vol

        assert synthetic_iv(closes, 1.15) == pytest.approx(
            close_to_close_vol(closes, 20) * 1.15
        )

    def test_iv_floor(self) -> None:
        assert synthetic_iv([100.0] * 30, 1.15) == 0.05

    def test_too_little_data_raises(self) -> None:
        with pytest.raises(ValueError):
            synthetic_iv([100.0] * 10, 1.15)

    def test_price_is_bs(self) -> None:
        from quantdesk.analytics.black_scholes import bs_price

        assert synthetic_price("put", 100, 95, 37, 0.04, 0.25) == pytest.approx(
            bs_price("put", 100, 95, 37 / 365, 0.04, 0.25)
        )

    def test_strike_for_delta_hits_band(self) -> None:
        from quantdesk.analytics.black_scholes import bs_greeks

        k = strike_for_delta("put", 100.0, -0.225, 37, 0.04, 0.25)
        d = bs_greeks("put", 100.0, k, 37 / 365, 0.04, 0.25).delta
        assert d == pytest.approx(-0.225, abs=0.03)  # 1%-grid resolution


class TestCosts:
    CM = CostModel(per_contract_fee=0.75)

    def test_spread_floor(self) -> None:
        assert self.CM.modeled_spread(0.01, 100, 95, 37) == SPREAD_FLOOR

    def test_spread_widens_otm_and_short_dte(self) -> None:
        atm = self.CM.modeled_spread(2.0, 100, 100, 30)
        otm = self.CM.modeled_spread(2.0, 100, 80, 30)
        short = self.CM.modeled_spread(2.0, 100, 100, 7)
        assert otm > atm
        assert short > atm

    def test_sell_and_buy_are_asymmetric(self) -> None:
        # Selling nets less than mid x 100; buying costs more.
        proceeds = self.CM.sell_proceeds(1.0, 100, 95, 37)
        cost = self.CM.buy_cost(1.0, 100, 95, 37)
        assert proceeds < 100.0 - 0.74
        assert cost > 100.0 + 0.74
        assert cost - proceeds == pytest.approx(
            self.CM.modeled_spread(1.0, 100, 95, 37) * 100 + 2 * 0.75
        )


class TestMetrics:
    DATES = [dt.date(2024, 1, 1) + dt.timedelta(days=i) for i in range(4)]

    def test_cagr_known(self) -> None:
        # +21% over exactly 2 years -> 10% CAGR.
        eq = [100.0, 121.0]
        dates = [dt.date(2022, 1, 1), dt.date(2024, 1, 1)]
        assert cagr(eq, dates) == pytest.approx(0.10, abs=1e-3)

    def test_sharpe_known(self) -> None:
        rets = [0.01, -0.01, 0.01, -0.01, 0.01, -0.01]
        # mean 0 -> Sharpe 0.
        assert sharpe(rets) == pytest.approx(0.0, abs=1e-12)
        up = [0.01] * 10 + [0.02] * 10
        assert sharpe(up) > 0

    def test_sortino_no_downside_returns_zero(self) -> None:
        assert sortino([0.01, 0.02, 0.01]) == 0.0

    def test_max_drawdown_known(self) -> None:
        eq = [100.0, 120.0, 90.0, 130.0]
        dd, days = max_drawdown(eq, self.DATES)
        assert dd == pytest.approx(0.25)  # 120 -> 90
        assert days == 2  # underwater from day1 peak to day3 recovery

    def test_ulcer_flat_is_zero(self) -> None:
        assert ulcer_index([100.0] * 10) == 0.0

    def test_cvar_95_known(self) -> None:
        rets = [0.01] * 95 + [-0.05] * 5  # worst 5% = the five -5% days
        assert cvar_95(rets) == pytest.approx(-0.05)

    def test_trade_stats(self) -> None:
        stats = trade_stats([50.0, -25.0, 75.0, -25.0], gross_premium=250.0)
        assert stats.n_trades == 4
        assert stats.win_rate == 0.5
        assert stats.avg_win == 62.5
        assert stats.avg_loss == -25.0
        assert stats.premium_capture == pytest.approx(75.0 / 250.0)

    def test_summarize_bundles_everything(self) -> None:
        eq = [100.0, 101.0, 99.0, 102.0]
        s = summarize_equity("x", eq, self.DATES)
        assert s.label == "x"
        assert s.max_drawdown > 0
        assert s.cagr != 0


class TestEngine:
    def test_flat_market_wheel_collects_premium(self) -> None:
        # Sideways market: puts should expire/profit; equity ends above start.
        history = make_history(alternating(400, vol=0.18))
        result = run_backtest(history, "wheel", CFG)
        assert SYNTHETIC_WARNING in result.warnings
        assert len(result.equity) == len(result.dates)
        assert result.trades, "no trades in a 400-bar flat market"
        assert result.gross_premium > 0
        assert result.total_costs > 0
        assert result.equity[-1] > result.initial_capital

    def test_crash_assigns_the_put(self) -> None:
        # Relentless -0.4%/day decline: puts finish ITM -> assignment path.
        history = make_history(trending(200, daily=-0.004))
        result = run_backtest(history, "wheel", CFG)
        reasons = {t.exit_reason for t in result.trades}
        assert ExitReason.ASSIGNED in reasons or ExitReason.STOP_LOSS in reasons
        assert result.equity[-1] < result.initial_capital  # crash costs money — honesty check

    def test_rally_takes_profit_on_puts(self) -> None:
        history = make_history(trending(300, daily=+0.003))
        result = run_backtest(history, "csp", CFG)
        reasons = {t.exit_reason for t in result.trades}
        assert ExitReason.TAKE_PROFIT in reasons
        assert result.equity[-1] > result.initial_capital

    def test_csp_mode_never_holds_shares_across_bars(self) -> None:
        history = make_history(trending(250, daily=-0.004))
        result = run_backtest(history, "csp", CFG)
        # After assignment CSP liquidates same-bar; equity stays defined.
        assert all(np.isfinite(result.equity))

    def test_covered_call_mode_runs(self) -> None:
        history = make_history(alternating(300))
        result = run_backtest(history, "covered-call", CFG)
        kinds = {t.kind for t in result.trades}
        assert kinds == {"call"}
        assert all(np.isfinite(result.equity))

    def test_no_lookahead_first_decision_bar(self) -> None:
        # Equity series starts at bar MIN_BARS_FOR_IV, not bar 0.
        from quantdesk.backtest.synthetic import MIN_BARS_FOR_IV

        closes = alternating(100)
        history = make_history(closes)
        result = run_backtest(history, "csp", CFG)
        assert result.dates[0] == history.bars[MIN_BARS_FOR_IV].date

    def test_too_short_history_raises(self) -> None:
        with pytest.raises(ValueError, match="bars"):
            run_backtest(make_history(alternating(10)), "csp", CFG)


class TestWalkForward:
    def test_walk_forward_reports_both_sides(self) -> None:
        closes = alternating(700, vol=0.22)
        history = make_history(closes)
        split = history.bars[350].date
        wf = walk_forward(history, "csp", CFG, split)
        assert wf.best_delta in (-0.20, -0.25, -0.30)
        assert "IS Sharpe" in wf.detail
        assert isinstance(wf.overfit_flag, bool)

    def test_split_without_data_raises(self) -> None:
        history = make_history(alternating(100))
        with pytest.raises(ValueError, match="split"):
            walk_forward(history, "csp", CFG, history.bars[2].date)
