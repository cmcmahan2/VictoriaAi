"""Cost model: loads config/costs.yaml and computes per-fill costs.

The Phase 3 backtester and Phase 7 executor both import from here so paper
and live share one cost implementation. Fee rates are per-market dynamic on
Polymarket — the yaml holds doc-derived category defaults, and `staleness_ok`
gates "trusted" backtest runs on a recent live refresh (phase0_recon.py stamps
`meta.last_verified_live` when it succeeds).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "costs.yaml"


@dataclass(frozen=True)
class CostModel:
    taker_base_rates: dict[str, float]
    maker_rate: float
    default_half_spread: float
    per_bucket_half_spread: dict[str, float]
    last_verified_live: dt.date | None
    max_fee_staleness_days: int

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "CostModel":
        raw = yaml.safe_load(path.read_text())
        verified = raw["meta"].get("last_verified_live")
        return cls(
            taker_base_rates={k: float(v) for k, v in raw["fees"]["taker_base_rates"].items()},
            maker_rate=float(raw["fees"]["maker_rate"]),
            default_half_spread=float(raw["spread_model"]["default_half_spread"]),
            per_bucket_half_spread={
                k: float(v) for k, v in (raw["spread_model"].get("per_bucket") or {}).items()
            },
            last_verified_live=dt.date.fromisoformat(verified) if verified else None,
            max_fee_staleness_days=int(raw["meta"]["max_fee_staleness_days"]),
        )

    def staleness_ok(self, today: dt.date | None = None) -> bool:
        if self.last_verified_live is None:
            return False
        today = today or dt.date.today()
        return (today - self.last_verified_live).days <= self.max_fee_staleness_days

    def taker_fee(self, category: str, shares: float, price: float) -> float:
        """Fee Structure V2: shares * base_rate * p * (1-p), taker side only."""
        if not 0.0 < price < 1.0:
            raise ValueError(f"price must be in (0,1), got {price}")
        rate = self.taker_base_rates.get(category, self.taker_base_rates["other"])
        return shares * rate * price * (1.0 - price)

    def half_spread(self, bucket: str) -> float:
        return self.per_bucket_half_spread.get(bucket, self.default_half_spread)
