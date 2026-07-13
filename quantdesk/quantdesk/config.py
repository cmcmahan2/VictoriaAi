"""Single source of truth for account, risk, and strategy parameters.

Backed by ``config.yaml`` next to the database. Everything downstream —
screener thresholds, strategy bands, sizing caps, cost model — reads
from here, never from constants scattered in modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Config base: unknown keys raise (typo protection beats silent defaults)."""

    model_config = ConfigDict(extra="forbid")

DEFAULT_CONFIG_PATH = Path("config.yaml")
DEFAULT_DB_PATH = Path("quantdesk.db")

# Curated liquid seed watchlist (Phase 2 expands to ~150 names).
#
# Canadian names are included via their US cross-listings: Wealthsimple
# supports US-listed options only, and yfinance carries no Montreal
# Exchange chains, so the NYSE listings of TSX companies are the
# tradeable path for Canadian exposure.
DEFAULT_WATCHLIST: list[str] = [
    # Canada via US listings
    "SHOP", "RY", "TD", "BMO", "BNS", "CM",
    "ENB", "TRP", "SU", "CNQ",
    "CP", "CNI", "BCE", "MFC", "NTR", "AEM", "CCJ", "BN", "EWC",
    # US broad market + sectors
    "SPY", "QQQ", "IWM", "DIA",
    "XLF", "XLE", "XLK", "XLV", "XLI", "XLP", "XLU", "XLY", "XLB", "XLRE", "XLC",
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
    "JPM", "BAC", "WFC", "GS",
    "XOM", "CVX", "COP",
    "JNJ", "PFE", "UNH", "ABBV",
    "KO", "PEP", "PG", "WMT", "COST", "MCD",
    "DIS", "NFLX", "CRM", "ORCL", "INTC", "CSCO", "QCOM", "AVGO", "MU", "TXN",
    "BA", "CAT", "DE", "GE", "HON", "UPS",
    "V", "MA", "PYPL",
    "T", "VZ", "TMUS",
    "F", "GM", "UBER",
    "GLD", "SLV", "TLT", "HYG", "EEM", "FXI",
]


class AccountConfig(StrictModel):
    # Account size is in CAD (user's home currency); collateral math for
    # US options is USD. Phase 4 sizing converts via a live CADUSD=X
    # quote from the provider — never a hardcoded rate.
    currency: str = "CAD"
    # User-confirmed starting capital (2026-07); expected to grow.
    size: float = Field(default=100.0, gt=0)
    # tfsa | margin — gates strategy availability. Credit spreads are
    # hidden for TFSA (registered-account strategy limits, plus CRA
    # business-income caution for high-frequency option writing).
    account_type: Literal["tfsa", "margin"] = "tfsa"


class RiskConfig(StrictModel):
    max_position_pct: float = Field(default=0.05, gt=0, le=1)
    max_deployed_pct: float = Field(default=0.20, gt=0, le=1)
    kelly_fraction: float = Field(default=0.25, gt=0, le=1)
    max_positions_per_sector: int = Field(default=2, ge=1)
    correlation_warning: float = Field(default=0.70, gt=0, le=1)


class CspStrategyConfig(StrictModel):
    delta_min: float = -0.30
    delta_max: float = -0.15
    dte_min: int = 30
    dte_max: int = 45
    min_annualized_yield: float = 0.12


class ExitConfig(StrictModel):
    take_profit_pct: float = 0.50
    time_exit_dte: int = 21
    stop_loss_credit_multiple: float = 2.0


class SpreadStrategyConfig(StrictModel):
    width: float = Field(default=5.0, gt=0)
    # Minimum credit as a fraction of width (spec: >= 1/3). Selling
    # spreads for less is picking up pennies without the pay.
    min_credit_fraction: float = Field(default=1 / 3, gt=0, lt=1)


class StrategyConfig(StrictModel):
    csp: CspStrategyConfig = CspStrategyConfig()
    spreads: SpreadStrategyConfig = SpreadStrategyConfig()
    exits: ExitConfig = ExitConfig()
    earnings_blackout: bool = True


class CostsConfig(StrictModel):
    # Wealthsimple Core tier, charged in USD (US-listed options only).
    # TODO(user): still pending final confirmation against WS fee page;
    # Premium/Generation tiers advertise reduced options fees.
    per_contract_fee: float = Field(default=0.75, ge=0)
    commission: float = Field(default=0.0, ge=0)


class ScreenerWeights(StrictModel):
    """Composite-score weights (z-scored components)."""

    vrp: float = 0.30
    iv_rank: float = 0.30
    liquidity: float = 0.20
    premium_yield: float = 0.20


class ScreenerConfig(StrictModel):
    min_open_interest: int = Field(default=500, ge=0)
    min_option_volume: int = Field(default=1, ge=0)
    max_spread_pct: float = Field(default=0.05, gt=0)
    iv_rank_min: float = Field(default=50.0, ge=0, le=100)
    freefall_dma_ratio: float = Field(default=0.85, gt=0, le=1)
    # Below this many own-IV observations, IV rank is bootstrapped from
    # the rolling realized-vol distribution and labeled as such.
    own_iv_history_min_days: int = Field(default=60, ge=1)
    max_workers: int = Field(default=8, ge=1)
    weights: ScreenerWeights = ScreenerWeights()


class BacktestConfig(StrictModel):
    # IV proxy = RV20 x richness. 1.15 approximates the long-run VRP
    # (implied ~15% above realized); recalibrate against your own
    # measured VRP as IV history accumulates.
    iv_richness: float = Field(default=1.15, gt=0)
    report_dir: Path = Path("reports")


class DataConfig(StrictModel):
    risk_free_rate: float = 0.04  # annualized; used by BS when no curve
    chain_cache_ttl_seconds: float = 15 * 60
    history_cache_ttl_seconds: float = 24 * 60 * 60
    quote_cache_ttl_seconds: float = 5 * 60


class QuantDeskConfig(StrictModel):
    account: AccountConfig = AccountConfig()
    risk: RiskConfig = RiskConfig()
    strategy: StrategyConfig = StrategyConfig()
    screener: ScreenerConfig = ScreenerConfig()
    backtest: BacktestConfig = BacktestConfig()
    costs: CostsConfig = CostsConfig()
    data: DataConfig = DataConfig()
    watchlist: list[str] = Field(default_factory=lambda: list(DEFAULT_WATCHLIST))
    db_path: Path = DEFAULT_DB_PATH


def load_config(path: Path | None = None) -> QuantDeskConfig:
    """Load config from YAML, creating a default file if none exists.

    Unknown keys in the file raise (typo protection beats silent defaults).
    """
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        config = QuantDeskConfig()
        save_config(config, cfg_path)
        return config
    raw: Any = yaml.safe_load(cfg_path.read_text()) or {}
    return QuantDeskConfig.model_validate(raw)


def save_config(config: QuantDeskConfig, path: Path | None = None) -> None:
    cfg_path = path or DEFAULT_CONFIG_PATH
    data = config.model_dump(mode="json")
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False))
