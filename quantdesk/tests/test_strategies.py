"""Tests for the strategy engine: CSP, covered call, credit spread, wheel."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fake_provider import FakeProvider, FakeSymbolSpec
from quantdesk.analytics.probability import prob_itm
from quantdesk.cli import app
from quantdesk.config import QuantDeskConfig
from quantdesk.strategies.covered_call import CoveredCall
from quantdesk.strategies.credit_spreads import PutCreditSpread
from quantdesk.strategies.csp import CashSecuredPut
from quantdesk.strategies.wheel import (
    WheelPosition,
    WheelState,
    WheelTransitionError,
)

CFG = QuantDeskConfig()
EXPIRY = dt.date.today() + dt.timedelta(days=30)


def chain_for(spec: FakeSymbolSpec, symbol: str = "X"):  # type: ignore[no-untyped-def]
    return FakeProvider({symbol: spec}).get_option_chain(symbol, EXPIRY)


class TestCashSecuredPut:
    def test_proposal_numbers(self) -> None:
        chain = chain_for(FakeSymbolSpec())
        proposals = CashSecuredPut().propose(chain, CFG)
        assert len(proposals) == 1  # only the 95 strike sits in the delta band
        p = proposals[0]
        assert p.legs[0].action == "sell"
        assert p.legs[0].contract.strike == 95.0
        credit = p.net_credit
        assert p.max_profit == pytest.approx(credit * 100)
        assert p.max_loss == pytest.approx((95.0 - credit) * 100)
        assert p.collateral == 9_500.0
        assert p.breakevens == [pytest.approx(95.0 - credit)]
        assert p.annualized_yield_on_collateral == pytest.approx(
            credit / 95.0 * 365 / 30
        )

    def test_pop_model_matches_breakeven_lognormal(self) -> None:
        chain = chain_for(FakeSymbolSpec())
        p = CashSecuredPut().propose(chain, CFG)[0]
        expected = 1.0 - prob_itm(
            "put", 100.0, p.breakevens[0], 30 / 365, CFG.data.risk_free_rate, 0.25
        )
        assert p.pop_model == pytest.approx(expected, abs=1e-6)
        # POP must exceed prob of expiring OTM at the strike itself.
        assert p.pop_model > 0.5

    def test_short_put_greeks_signs(self) -> None:
        p = CashSecuredPut().propose(chain_for(FakeSymbolSpec()), CFG)[0]
        assert p.greeks.delta_shares > 0     # short put = long exposure
        assert p.greeks.theta_usd_day > 0    # collects time decay
        assert p.greeks.vega_usd_pt < 0      # hurt by vol expansion
        assert p.greeks.gamma_shares < 0     # short gamma

    def test_exit_plan_from_config(self) -> None:
        p = CashSecuredPut().propose(chain_for(FakeSymbolSpec()), CFG)[0]
        assert p.exit_plan.take_profit_buyback == pytest.approx(p.net_credit * 0.5)
        assert p.exit_plan.stop_loss_buyback == pytest.approx(p.net_credit * 3.0)
        assert p.exit_plan.time_exit_dte == 21
        assert len(p.exit_plan.rules) == 3

    def test_thin_yield_warned(self) -> None:
        # Default spec yields ~11.5% annualized < 12% minimum.
        p = CashSecuredPut().propose(chain_for(FakeSymbolSpec()), CFG)[0]
        assert any("below" in w for w in p.warnings)

    def test_rich_vol_no_warning_and_not_margin(self) -> None:
        p = CashSecuredPut().propose(chain_for(FakeSymbolSpec(sigma=0.40)), CFG)[0]
        assert p.warnings == []
        assert p.requires_margin_account is False


class TestCoveredCall:
    def test_band_and_numbers(self) -> None:
        chain = chain_for(FakeSymbolSpec())
        proposals = CoveredCall(cost_basis=92.0).propose(chain, CFG)
        assert len(proposals) == 1  # the 105 call sits in the +band
        p = proposals[0]
        strike = p.legs[0].contract.strike
        assert strike == 105.0
        assert p.max_profit == pytest.approx((strike - 92.0 + p.net_credit) * 100)
        assert p.breakevens == [pytest.approx(92.0 - p.net_credit)]
        assert p.warnings == []

    def test_flags_strike_below_basis(self) -> None:
        chain = chain_for(FakeSymbolSpec())
        p = CoveredCall(cost_basis=110.0).propose(chain, CFG)[0]
        assert any("BELOW cost basis" in w for w in p.warnings)

    def test_missing_basis_warns_and_uses_spot(self) -> None:
        chain = chain_for(FakeSymbolSpec())
        p = CoveredCall().propose(chain, CFG)[0]
        assert any("cost basis not provided" in w for w in p.warnings)
        assert p.breakevens == [pytest.approx(100.0 - p.net_credit)]


class TestPutCreditSpread:
    def test_rejected_when_credit_below_minimum(self) -> None:
        # Default 25% vol: 95/90 spread pays ~0.72 < 5/3 — must not propose.
        chain = chain_for(FakeSymbolSpec())
        assert PutCreditSpread().propose(chain, CFG) == []

    def test_qualifying_spread_numbers(self) -> None:
        cfg = QuantDeskConfig()
        cfg.strategy.spreads.min_credit_fraction = 0.10
        chain = chain_for(FakeSymbolSpec())
        proposals = PutCreditSpread().propose(chain, cfg)
        assert len(proposals) == 1
        p = proposals[0]
        assert p.requires_margin_account is True
        assert [leg.action for leg in p.legs] == ["sell", "buy"]
        assert p.legs[0].contract.strike == 95.0
        assert p.legs[1].contract.strike == 90.0
        assert p.net_credit == pytest.approx(p.legs[0].price - p.legs[1].price)
        assert p.max_loss == pytest.approx((5.0 - p.net_credit) * 100)
        assert p.collateral == pytest.approx(p.max_loss)  # defined risk
        assert p.max_profit == pytest.approx(p.net_credit * 100)
        assert p.breakevens == [pytest.approx(95.0 - p.net_credit)]

    def test_skipped_when_long_strike_unlisted(self) -> None:
        cfg = QuantDeskConfig()
        cfg.strategy.spreads.min_credit_fraction = 0.01
        cfg.strategy.spreads.width = 7.5  # 95 - 7.5 = 87.5 not on the grid
        chain = chain_for(FakeSymbolSpec())
        assert PutCreditSpread().propose(chain, cfg) == []


class TestWheel:
    def d(self, offset: int = 0) -> dt.date:
        return dt.date(2026, 7, 13) + dt.timedelta(days=offset)

    def test_full_cycle_cost_basis_and_pnl(self) -> None:
        w = WheelPosition(symbol="X")
        w.sell_put(95.0, 0.90, self.d(0))
        assert w.state == WheelState.SHORT_PUT
        w.put_assigned(self.d(30))
        assert w.state == WheelState.ASSIGNED
        assert w.shares == 100
        assert w.effective_cost_basis == pytest.approx(94.10)  # 95 - 0.90
        w.sell_call(100.0, 1.20, self.d(32))
        assert w.effective_cost_basis == pytest.approx(92.90)
        w.call_expired(self.d(62))
        assert w.state == WheelState.ASSIGNED
        w.sell_call(100.0, 1.00, self.d(64))
        assert w.effective_cost_basis == pytest.approx(91.90)
        w.called_away(self.d(94))
        assert w.state == WheelState.CALLED_AWAY
        assert w.shares == 0
        # P&L: (100 - 95) strike gain + 3.10 premiums = 8.10/share
        assert w.realized_pnl_per_share == pytest.approx(8.10)
        w.restart(self.d(95))
        assert w.state == WheelState.CASH
        assert w.premiums_per_share == 0.0

    def test_put_expiring_worthless_realizes_premium(self) -> None:
        w = WheelPosition(symbol="X")
        w.sell_put(95.0, 0.90, self.d(0))
        w.put_expired(self.d(30))
        assert w.state == WheelState.CASH
        assert w.realized_pnl_per_share == pytest.approx(0.90)
        assert w.premiums_per_share == 0.0  # fresh cycle

    def test_invalid_transitions_raise(self) -> None:
        w = WheelPosition(symbol="X")
        with pytest.raises(WheelTransitionError, match="sell_call"):
            w.sell_call(100.0, 1.0, self.d())
        with pytest.raises(WheelTransitionError, match="called_away"):
            w.called_away(self.d())
        w.sell_put(95.0, 0.9, self.d())
        with pytest.raises(WheelTransitionError, match="sell_put"):
            w.sell_put(90.0, 0.8, self.d())

    def test_event_log_is_complete(self) -> None:
        w = WheelPosition(symbol="X")
        w.sell_put(95.0, 0.90, self.d(0))
        w.put_assigned(self.d(30))
        w.sell_call(100.0, 1.20, self.d(32))
        w.called_away(self.d(60))
        assert [e.action for e in w.events] == [
            "sell_put", "put_assigned", "sell_call", "called_away",
        ]
        assert sum(e.cash_flow_per_share for e in w.events) == pytest.approx(2.10)


class TestProposeCli:
    @pytest.fixture()
    def env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[CliRunner, Path]:
        monkeypatch.setattr(
            "quantdesk.cli._provider", lambda config: FakeProvider()
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.safe_dump({"db_path": str(tmp_path / "q.db")}))
        return CliRunner(), cfg

    def test_propose_csp_card(self, env: tuple[CliRunner, Path]) -> None:
        runner, cfg = env
        result = runner.invoke(app, ["propose", "csp", "FAKE", "--config", str(cfg)])
        assert result.exit_code == 0, result.output
        out = result.output
        assert "FAKE csp" in out
        assert "Exit plan" in out
        assert "POP" in out
        assert "collateral" in out
        assert "Take profit" in out and "Stop loss" in out and "Time exit" in out

    def test_spreads_blocked_on_tfsa(self, env: tuple[CliRunner, Path]) -> None:
        runner, cfg = env
        result = runner.invoke(
            app, ["propose", "put-credit-spread", "FAKE", "--config", str(cfg)]
        )
        assert result.exit_code == 1
        assert "BLOCKED" in result.output
        assert "tfsa" in result.output

    def test_spreads_allowed_on_margin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "quantdesk.cli._provider", lambda config: FakeProvider()
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.safe_dump(
                {
                    "db_path": str(tmp_path / "q.db"),
                    "account": {"account_type": "margin"},
                    "strategy": {"spreads": {"min_credit_fraction": 0.10}},
                }
            )
        )
        runner = CliRunner()
        result = runner.invoke(
            app, ["propose", "put-credit-spread", "FAKE", "--config", str(cfg)]
        )
        assert result.exit_code == 0, result.output
        assert "MARGIN ACCOUNT REQUIRED" in result.output

    def test_unknown_strategy_rejected(self, env: tuple[CliRunner, Path]) -> None:
        runner, cfg = env
        result = runner.invoke(
            app, ["propose", "condor", "FAKE", "--config", str(cfg)]
        )
        assert result.exit_code == 1
        assert "Unknown strategy" in result.output
