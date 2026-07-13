"""Tests for the ranker, universe helpers, and the end-to-end scan CLI."""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fake_provider import FakeProvider, FakeSymbolSpec
from quantdesk.cli import app
from quantdesk.config import QuantDeskConfig
from quantdesk.data.cache import IVHistoryStore
from quantdesk.screener.ranker import score_results, zscores
from quantdesk.screener.universe import (
    build_symbol_metrics,
    find_csp_strikes,
    scan_universe,
    select_expiry,
    universe_symbols,
    usd_budget_per_position,
)

from test_filters import make_metrics, make_strike  # reuse builders


class TestZScores:
    def test_known_values(self) -> None:
        z = zscores([1.0, 2.0, 3.0])
        assert z[0] == pytest.approx(-math.sqrt(1.5), rel=1e-9)
        assert z[1] == pytest.approx(0.0, abs=1e-12)
        assert z[2] == pytest.approx(math.sqrt(1.5), rel=1e-9)

    def test_degenerate_all_zero(self) -> None:
        assert zscores([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]

    def test_empty(self) -> None:
        assert zscores([]) == []


class TestScoreResults:
    def test_ranks_richer_vol_higher(self) -> None:
        from quantdesk.screener.models import ScreenResult
        from quantdesk.screener.filters import csp_pipeline, run_filters

        cfg = QuantDeskConfig()
        pipeline = csp_pipeline(cfg, 100_000.0)
        results = []
        for sym, vrp, ivr in (("RICH", 0.10, 90.0), ("MID", 0.05, 60.0), ("THIN", 0.01, 51.0)):
            m = make_metrics(symbol=sym, vrp=vrp, iv_rank=ivr)
            results.append(
                ScreenResult(symbol=sym, metrics=m, filters=run_filters(m, pipeline))
            )
        ranked = score_results(results, cfg)
        assert [r.symbol for r in ranked] == ["RICH", "MID", "THIN"]
        assert ranked[0].score is not None and ranked[0].score.total > 0

    def test_single_candidate_scores_zero(self) -> None:
        from quantdesk.screener.models import ScreenResult
        from quantdesk.screener.filters import csp_pipeline, run_filters

        cfg = QuantDeskConfig()
        m = make_metrics()
        r = ScreenResult(
            symbol="X", metrics=m, filters=run_filters(m, csp_pipeline(cfg, 1e6))
        )
        ranked = score_results([r], cfg)
        assert ranked[0].score is not None
        assert ranked[0].score.total == 0.0

    def test_no_passing_returns_empty(self) -> None:
        from quantdesk.screener.models import ScreenResult

        assert score_results([ScreenResult(symbol="X", error="boom")], QuantDeskConfig()) == []


class TestUniverseHelpers:
    def test_universe_dedupes_preserving_order(self) -> None:
        cfg = QuantDeskConfig()
        cfg.watchlist = ["spy", "SPY", "aapl", "SPY "]
        assert universe_symbols(cfg) == ["SPY", "AAPL"]

    def test_select_expiry_prefers_band_midpoint(self) -> None:
        today = dt.date.today()
        exps = [today + dt.timedelta(days=d) for d in (7, 31, 44, 60)]
        chosen = select_expiry(exps, 30, 45)
        assert chosen == today + dt.timedelta(days=31)  # |31-37.5| < |44-37.5|

    def test_select_expiry_none_outside_band(self) -> None:
        today = dt.date.today()
        exps = [today + dt.timedelta(days=d) for d in (7, 60)]
        assert select_expiry(exps, 30, 45) is None

    def test_usd_budget_converts_cad(self) -> None:
        cfg = QuantDeskConfig()
        cfg.account.size = 100_000.0  # CAD
        cap, note = usd_budget_per_position(FakeProvider(), cfg)
        assert cap == pytest.approx(100_000 * 0.05 * 0.73)
        assert "CADUSD" in note

    def test_usd_budget_passthrough_usd(self) -> None:
        cfg = QuantDeskConfig()
        cfg.account.currency = "USD"
        cfg.account.size = 10_000.0
        cap, note = usd_budget_per_position(FakeProvider(), cfg)
        assert cap == pytest.approx(500.0)
        assert "already in USD" in note

    def test_usd_budget_fx_failure_warns(self) -> None:
        class NoFxProvider(FakeProvider):
            def get_quote(self, symbol: str):  # type: ignore[no-untyped-def]
                if symbol.endswith("=X"):
                    raise RuntimeError("no fx")
                return super().get_quote(symbol)

        cfg = QuantDeskConfig()
        cfg.account.size = 1000.0
        cap, note = usd_budget_per_position(NoFxProvider(), cfg)
        assert cap == pytest.approx(50.0)
        assert "WARNING" in note


class TestFindCspStrikes:
    def test_only_otm_band_strikes_returned(self) -> None:
        provider = FakeProvider()
        expiry = dt.date.today() + dt.timedelta(days=30)
        chain = provider.get_option_chain("X", expiry)
        strikes = find_csp_strikes(chain, 0.04, 0.0, -0.30, -0.15)
        # At sigma 25%, 30 DTE: only the 95 strike lands in [-0.30, -0.15].
        assert [s.contract.strike for s in strikes] == [95.0]
        s = strikes[0]
        assert -0.30 <= s.delta <= -0.15
        assert s.iv == pytest.approx(0.25, abs=1e-6)  # solver recovers truth
        assert s.collateral == 9_500.0
        assert s.annualized_yield > 0


class TestBuildSymbolMetrics:
    def test_metrics_assembly(self, tmp_path: Path) -> None:
        cfg = QuantDeskConfig()
        store = IVHistoryStore(tmp_path / "t.db")
        m = build_symbol_metrics(FakeProvider(), "GOODCO", cfg, store)
        assert m.spot == 100.0
        assert m.atm_iv == pytest.approx(0.25, abs=1e-6)
        assert m.vrp > 0
        assert m.iv_rank_source == "rv-bootstrap"  # only 1 own observation
        assert m.best_strike is not None
        assert m.best_strike.contract.strike == 95.0
        # The scan itself must grow our IV history.
        assert len(store.history("GOODCO")) == 1


def scan_config(tmp_path: Path, size_cad: float, watchlist: list[str]) -> Path:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "db_path": str(tmp_path / "q.db"),
                "account": {"size": size_cad},
                "watchlist": watchlist,
            }
        )
    )
    return cfg_path


SPECS = {
    "GOODCO": FakeSymbolSpec(),
    "KNIFE": FakeSymbolSpec(decline_from=4.0),
    "EARN": FakeSymbolSpec(earnings_in_days=10),
    "ILLIQ": FakeSymbolSpec(oi=5),
}


class TestScanUniverse:
    def test_scan_separates_passing_from_excluded(self, tmp_path: Path) -> None:
        from quantdesk.config import load_config

        cfg = load_config(scan_config(
            tmp_path, 300_000.0, ["GOODCO", "KNIFE", "EARN", "ILLIQ"]
        ))
        ranked, excluded, note = scan_universe(FakeProvider(SPECS), cfg)
        assert [r.symbol for r in ranked] == ["GOODCO"]
        assert {r.symbol for r in excluded} == {"KNIFE", "EARN", "ILLIQ"}
        reasons = {r.symbol: " | ".join(r.exclusion_reasons) for r in excluded}
        assert "freefall" in reasons["KNIFE"]
        assert "earnings" in reasons["EARN"]
        assert "open interest" in reasons["ILLIQ"]
        assert "CADUSD" in note

    def test_tiny_account_excludes_on_affordability(self, tmp_path: Path) -> None:
        from quantdesk.config import load_config

        cfg = load_config(scan_config(tmp_path, 100.0, ["GOODCO"]))
        ranked, excluded, _ = scan_universe(FakeProvider(SPECS), cfg)
        assert ranked == []
        assert "per-position cap" in " | ".join(excluded[0].exclusion_reasons)


class TestScanCli:
    @pytest.fixture()
    def env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[CliRunner, Path]:
        monkeypatch.setattr(
            "quantdesk.cli._provider", lambda config: FakeProvider(SPECS)
        )
        return CliRunner(), tmp_path

    def test_scan_table(self, env: tuple[CliRunner, Path]) -> None:
        runner, tmp = env
        cfg = scan_config(tmp, 300_000.0, ["GOODCO", "KNIFE", "EARN", "ILLIQ"])
        result = runner.invoke(app, ["scan", "--config", str(cfg)])
        assert result.exit_code == 0, result.output
        assert "GOODCO" in result.output
        assert "3 symbols excluded" in result.output
        assert "--explain" in result.output

    def test_scan_explain_shows_all_verdicts(self, env: tuple[CliRunner, Path]) -> None:
        runner, tmp = env
        cfg = scan_config(tmp, 300_000.0, ["GOODCO", "KNIFE"])
        result = runner.invoke(
            app, ["scan", "--explain", "KNIFE", "--config", str(cfg)]
        )
        assert result.exit_code == 0, result.output
        assert "FAIL" in result.output
        assert "freefall" in result.output
        assert "PASS" in result.output  # other filters still shown

    def test_scan_rejects_unknown_strategy(self, env: tuple[CliRunner, Path]) -> None:
        runner, tmp = env
        cfg = scan_config(tmp, 300_000.0, ["GOODCO"])
        result = runner.invoke(
            app, ["scan", "--strategy", "condor", "--config", str(cfg)]
        )
        assert result.exit_code == 1
        assert "Phase 3" in result.output
