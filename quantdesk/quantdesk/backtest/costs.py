"""Transaction cost model: per-contract fees + spread slippage.

Slippage = 50% of a *modeled* bid-ask spread (you trade at mid minus
half the spread when selling, plus half when buying). The spread model
is deliberately punitive for cheap, short-dated, far-OTM contracts —
the ones retail actually gets hurt on:

    spread = max(floor, price x base_pct x (1 + 2|ln(S/K)|) x sqrt(30 / max(dte, 5)))

TODO(user): confirm Wealthsimple's current fee schedule (per-contract
fee and any assignment/exercise fee) — defaults live in config.yaml.
"""

from __future__ import annotations

import math

from pydantic import BaseModel

SPREAD_FLOOR = 0.02       # no listed option trades tighter than 2 cents wide
BASE_SPREAD_PCT = 0.04    # 4% of price for ATM 30 DTE — realistic for liquid names


class CostModel(BaseModel):
    per_contract_fee: float
    commission: float = 0.0

    def modeled_spread(
        self, option_price: float, spot: float, strike: float, dte_days: int
    ) -> float:
        """Modeled full bid-ask spread in $ per share."""
        if option_price <= 0:
            return SPREAD_FLOOR
        moneyness_adj = 1.0 + 2.0 * abs(math.log(spot / strike))
        dte_adj = math.sqrt(30.0 / max(dte_days, 5))
        return max(option_price * BASE_SPREAD_PCT * moneyness_adj * dte_adj, SPREAD_FLOOR)

    def slippage_per_share(
        self, option_price: float, spot: float, strike: float, dte_days: int
    ) -> float:
        """Half the modeled spread — what you give up vs mid on one side."""
        return 0.5 * self.modeled_spread(option_price, spot, strike, dte_days)

    def fees_per_side(self, contracts: int = 1) -> float:
        """Fixed costs for one fill (open OR close)."""
        return self.commission + self.per_contract_fee * contracts

    def sell_proceeds(
        self,
        option_price: float,
        spot: float,
        strike: float,
        dte_days: int,
        contracts: int = 1,
    ) -> float:
        """Net $ received selling at mid, after slippage and fees."""
        slip = self.slippage_per_share(option_price, spot, strike, dte_days)
        return max(option_price - slip, 0.0) * 100.0 * contracts - self.fees_per_side(
            contracts
        )

    def buy_cost(
        self,
        option_price: float,
        spot: float,
        strike: float,
        dte_days: int,
        contracts: int = 1,
    ) -> float:
        """Net $ paid buying at mid, after slippage and fees."""
        slip = self.slippage_per_share(option_price, spot, strike, dte_days)
        return (option_price + slip) * 100.0 * contracts + self.fees_per_side(contracts)
