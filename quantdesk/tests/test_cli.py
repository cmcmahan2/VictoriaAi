"""End-to-end CLI tests using a deterministic fake provider (no network).

The fake chain is priced with the Black-Scholes engine at a known sigma,
so the quote pipeline (IV solve -> rank -> VRP -> expected move -> render)
is verified against numbers we control.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fake_provider import RATE, FakeProvider
from quantdesk.cli import app
from quantdesk.config import QuantDeskConfig


@pytest.fixture()
def cli_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[CliRunner, Path]:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"db_path": str(tmp_path / "quantdesk.db"),
                        "data": {"risk_free_rate": RATE}})
    )
    monkeypatch.setattr(
        "quantdesk.cli._provider", lambda config: FakeProvider()
    )
    return CliRunner(), cfg_path


class TestQuoteCommand:
    def test_quote_renders_full_snapshot(
        self, cli_env: tuple[CliRunner, Path]
    ) -> None:
        runner, cfg = cli_env
        result = runner.invoke(app, ["quote", "FAKE", "--config", str(cfg)])
        assert result.exit_code == 0, result.output
        out = result.output
        assert "FAKE" in out
        assert "ATM IV" in out
        assert "25.0%" in out          # solver recovers the true sigma
        assert "VRP" in out
        assert "options rich" in out   # IV 25% > RV 20%
        assert "Expected move" in out
        assert "1/252" in out          # first IV observation recorded
        assert "IMMATURE" in out       # honest maturity label
        assert "Next earnings" in out

    def test_iv_history_accumulates(
        self, cli_env: tuple[CliRunner, Path]
    ) -> None:
        runner, cfg = cli_env
        runner.invoke(app, ["quote", "FAKE", "--config", str(cfg)])
        result = runner.invoke(app, ["quote", "FAKE", "--config", str(cfg)])
        # Same day -> upsert, still 1 observation.
        assert "1/252" in result.output


class TestRegimeCommand:
    def test_regime_renders(self, cli_env: tuple[CliRunner, Path]) -> None:
        runner, cfg = cli_env
        result = runner.invoke(app, ["regime", "--config", str(cfg)])
        assert result.exit_code == 0, result.output
        assert "ELEVATED" in result.output  # fake VIX = 20
        assert "100%" in result.output      # full sizing below 30


class TestConfigShow:
    def test_tfsa_note_shown(self, cli_env: tuple[CliRunner, Path]) -> None:
        runner, cfg = cli_env
        result = runner.invoke(app, ["config-show", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "credit spreads hidden" in result.output

    def test_default_config_file_created(self, tmp_path: Path) -> None:
        runner = CliRunner()
        cfg = tmp_path / "fresh.yaml"
        result = runner.invoke(app, ["config-show", "--config", str(cfg)])
        assert result.exit_code == 0
        assert cfg.exists()
        loaded = QuantDeskConfig.model_validate(yaml.safe_load(cfg.read_text()))
        assert loaded.account.size == 100.0
