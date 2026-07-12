"""Tests for YAML-backed configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from quantdesk.config import QuantDeskConfig, load_config, save_config


class TestDefaults:
    def test_spec_defaults(self) -> None:
        cfg = QuantDeskConfig()
        assert cfg.account.size == 100.0  # user-confirmed starting capital
        assert cfg.account.currency == "CAD"
        assert cfg.account.account_type == "tfsa"
        assert cfg.risk.max_position_pct == 0.05
        assert cfg.risk.max_deployed_pct == 0.20
        assert cfg.risk.kelly_fraction == 0.25
        assert cfg.strategy.csp.delta_min == -0.30
        assert cfg.strategy.csp.dte_max == 45
        assert cfg.strategy.exits.take_profit_pct == 0.50
        assert cfg.strategy.exits.time_exit_dte == 21
        assert cfg.strategy.earnings_blackout is True
        assert "SPY" in cfg.watchlist and "QQQ" in cfg.watchlist
        # Canadian exposure via US cross-listings (Wealthsimple trades
        # US-listed options only; no Montreal Exchange data in yfinance).
        assert "SHOP" in cfg.watchlist and "RY" in cfg.watchlist


class TestLoadSave:
    def test_creates_default_file_when_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        cfg = load_config(path)
        assert path.exists()
        assert cfg == QuantDeskConfig()

    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        cfg = QuantDeskConfig()
        cfg.account.size = 25_000.0
        cfg.watchlist = ["SPY", "SHOP"]
        save_config(cfg, path)
        loaded = load_config(path)
        assert loaded.account.size == 25_000.0
        assert loaded.watchlist == ["SPY", "SHOP"]

    def test_partial_file_gets_defaults(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"account": {"size": 50_000}}))
        cfg = load_config(path)
        assert cfg.account.size == 50_000.0
        assert cfg.risk.max_position_pct == 0.05  # untouched default

    def test_unknown_key_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"acount": {"size": 1}}))  # typo
        with pytest.raises(ValueError):
            load_config(path)

    def test_invalid_account_type_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"account": {"account_type": "ira"}}))
        with pytest.raises(ValueError):
            load_config(path)
