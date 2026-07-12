"""End-to-end CLI tests using a deterministic fake provider (no network).

The fake chain is priced with the Black-Scholes engine at a known sigma,
so the quote pipeline (IV solve -> rank -> VRP -> expected move -> render)
is verified against numbers we control.
"""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from quantdesk.analytics.black_scholes import bs_price
from quantdesk.cli import app
from quantdesk.config import QuantDeskConfig
from quantdesk.data.models import (
    Bar,
    OptionChain,
    OptionContract,
    OptionType,
    PriceHistory,
    Quote,
)
from quantdesk.data.provider import DataProvider

TRUE_SIGMA = 0.25
SPOT = 100.0
RATE = 0.04


class FakeProvider(DataProvider):
    """Deterministic provider: GBM-ish history, BS-priced chain at 25% vol."""

    def get_quote(self, symbol: str) -> Quote:
        price = 20.0 if symbol.startswith("^") else SPOT  # ^VIX -> 20
        return Quote(symbol=symbol, price=price, timestamp=dt.datetime.now())

    def get_price_history(self, symbol: str, years: int = 5) -> PriceHistory:
        # Alternating +/- daily log return sized for ~20% annualized CC vol.
        a = 0.20 / math.sqrt(252)
        bars: list[Bar] = []
        price = SPOT
        start = dt.date.today() - dt.timedelta(days=200)
        for i in range(130):
            price *= math.exp(a if i % 2 else -a)
            bars.append(
                Bar(
                    date=start + dt.timedelta(days=i),
                    open=price,
                    high=price * 1.005,
                    low=price * 0.995,
                    close=price,
                    volume=1e6,
                )
            )
        return PriceHistory(symbol=symbol, bars=bars)

    def get_expirations(self, symbol: str) -> list[dt.date]:
        return [dt.date.today() + dt.timedelta(days=d) for d in (7, 30, 60)]

    def get_option_chain(self, symbol: str, expiry: dt.date) -> OptionChain:
        t = (expiry - dt.date.today()).days / 365.0
        strikes = [90.0, 95.0, 100.0, 105.0, 110.0]

        def contract(opt_type: OptionType, strike: float) -> OptionContract:
            fair = bs_price(opt_type, SPOT, strike, t, RATE, TRUE_SIGMA)
            return OptionContract(
                contract_symbol=f"{symbol}-{opt_type}-{strike}",
                underlying=symbol,
                option_type=opt_type,
                strike=strike,
                expiry=expiry,
                bid=fair - 0.01,
                ask=fair + 0.01,
                last=fair,
                volume=1000,
                open_interest=5000,
            )

        return OptionChain(
            underlying=symbol,
            spot=SPOT,
            expiry=expiry,
            calls=[contract("call", k) for k in strikes],
            puts=[contract("put", k) for k in strikes],
            fetched_at=dt.datetime.now(dt.timezone.utc),
        )

    def get_dividend_yield(self, symbol: str) -> float:
        return 0.0

    def get_next_earnings(self, symbol: str) -> dt.date | None:
        return dt.date.today() + dt.timedelta(days=50)


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
        assert loaded.account.size == 10_000.0
