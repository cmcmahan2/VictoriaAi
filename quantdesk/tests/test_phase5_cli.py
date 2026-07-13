"""End-to-end CLI tests for backtest, journal, and review commands."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fake_provider import FakeProvider
from quantdesk.cli import app


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[CliRunner, Path]:
    monkeypatch.setattr("quantdesk.cli._provider", lambda config: FakeProvider())
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "db_path": str(tmp_path / "q.db"),
                "backtest": {"report_dir": str(tmp_path / "reports")},
            }
        )
    )
    return CliRunner(), cfg


class TestBacktestCli:
    def test_wheel_end_to_end_with_report(
        self, env: tuple[CliRunner, Path], tmp_path: Path
    ) -> None:
        runner, cfg = env
        result = runner.invoke(app, ["backtest", "wheel", "FAKE", "--config", str(cfg)])
        assert result.exit_code == 0, result.output
        assert "SYNTHETIC" in result.output          # the warning always prints
        assert "CAGR" in result.output
        assert "B&H FAKE" in result.output           # benchmark row present
        assert "premium capture" in result.output
        reports = list((tmp_path / "reports").glob("backtest_FAKE_wheel_*.html"))
        assert len(reports) == 1                     # plotly report saved

    def test_walk_forward_mode(self, env: tuple[CliRunner, Path]) -> None:
        import datetime as dt

        runner, cfg = env
        split = (dt.date.today() - dt.timedelta(days=135)).isoformat()
        result = runner.invoke(
            app,
            ["backtest", "csp", "FAKE", "--walk-forward", split, "--config", str(cfg)],
        )
        assert result.exit_code == 0, result.output
        assert "IS Sharpe" in result.output

    def test_unknown_mode_rejected(self, env: tuple[CliRunner, Path]) -> None:
        runner, cfg = env
        result = runner.invoke(app, ["backtest", "condor", "FAKE", "--config", str(cfg)])
        assert result.exit_code == 1


class TestJournalCli:
    def test_open_list_close_review_flow(self, env: tuple[CliRunner, Path]) -> None:
        import datetime as dt

        runner, cfg = env
        expiry = (dt.date.today() + dt.timedelta(days=35)).isoformat()
        result = runner.invoke(
            app,
            [
                "journal", "open", "SHOP", "--strategy", "csp", "--strike", "95",
                "--expiry", expiry, "--credit", "0.90", "--fees", "1.50",
                "--iv", "0.32", "--config", str(cfg),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "#1 opened" in result.output

        result = runner.invoke(app, ["journal", "list", "--config", str(cfg)])
        assert "SHOP" in result.output and "open" in result.output

        result = runner.invoke(
            app,
            ["journal", "close", "1", "--cost", "30", "--reason", "take-profit",
             "--rv", "0.22", "--config", str(cfg)],
        )
        assert result.exit_code == 0, result.output
        assert "+58.50" in result.output  # 90 - 30 - 1.50, computed

        month = dt.date.today().strftime("%Y-%m")
        result = runner.invoke(app, ["review", "--month", month, "--config", str(cfg)])
        assert result.exit_code == 0, result.output
        assert "rule adherence 100%" in result.output
        assert "VRP captured" in result.output

    def test_override_requires_why(self, env: tuple[CliRunner, Path]) -> None:
        import datetime as dt

        runner, cfg = env
        expiry = (dt.date.today() + dt.timedelta(days=35)).isoformat()
        result = runner.invoke(
            app,
            ["journal", "open", "SHOP", "--strike", "95", "--expiry", expiry,
             "--credit", "0.90", "--override", "--config", str(cfg)],
        )
        assert result.exit_code == 1
        assert "requires --why" in result.output

    def test_override_flagged_in_review(self, env: tuple[CliRunner, Path]) -> None:
        import datetime as dt

        runner, cfg = env
        expiry = (dt.date.today() + dt.timedelta(days=35)).isoformat()
        runner.invoke(
            app,
            ["journal", "open", "SHOP", "--strike", "95", "--expiry", expiry,
             "--credit", "0.90", "--override", "--why", "earnings gamble",
             "--config", str(cfg)],
        )
        month = dt.date.today().strftime("%Y-%m")
        result = runner.invoke(app, ["review", "--month", month, "--config", str(cfg)])
        assert "override" in result.output
        assert "earnings gamble" in result.output
