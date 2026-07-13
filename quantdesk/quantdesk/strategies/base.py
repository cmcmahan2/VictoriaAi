"""Strategy ABC and the TradeProposal model — the unit of decision support.

A proposal is everything the trader needs to place (or reject) the trade
manually: legs, credit, risk numbers, both POP estimates, entry Greeks,
an exit plan, and a plain-English thesis. Proposals never execute.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from pydantic import BaseModel

from quantdesk.config import ExitConfig, QuantDeskConfig
from quantdesk.data.models import OptionChain, OptionContract


class ProposalLeg(BaseModel):
    action: Literal["sell", "buy"]
    contract: OptionContract
    quantity: int = 1
    price: float  # mid used for analysis; fills will differ


class PositionGreeks(BaseModel):
    """Entry Greeks for the whole position, in trader units per 1x size.

    delta_shares: share-equivalent exposure (delta x 100 per contract)
    gamma_shares: change in delta_shares per $1 spot move
    theta_usd_day: dollars earned (+) or paid (-) per calendar day
    vega_usd_pt: dollars per 1 vol-point change in IV
    """

    delta_shares: float
    gamma_shares: float
    theta_usd_day: float
    vega_usd_pt: float


class ExitPlan(BaseModel):
    """Mechanical exits attached to every proposal. Deviating = freelancing.

    take_profit_buyback: close when the short can be bought back at this
      price (default 50% of credit received).
    time_exit_dte: close at this many DTE regardless of P&L (gamma risk
      grows as expiry nears; the last dollars are the most expensive).
    stop_loss_buyback: close if buyback cost reaches this level
      (credit x (1 + multiple) => loss = multiple x credit).
    """

    take_profit_buyback: float
    time_exit_dte: int
    stop_loss_buyback: float
    rules: list[str]


def build_exit_plan(net_credit: float, exits: ExitConfig) -> ExitPlan:
    tp = net_credit * (1.0 - exits.take_profit_pct)
    stop = net_credit * (1.0 + exits.stop_loss_credit_multiple)
    return ExitPlan(
        take_profit_buyback=tp,
        time_exit_dte=exits.time_exit_dte,
        stop_loss_buyback=stop,
        rules=[
            f"Take profit: buy back at {tp:.2f} "
            f"({exits.take_profit_pct:.0%} of the {net_credit:.2f} credit kept)",
            f"Time exit: close at {exits.time_exit_dte} DTE regardless of P&L",
            f"Stop loss: close if buyback reaches {stop:.2f} "
            f"(loss = {exits.stop_loss_credit_multiple:g}x credit received)",
        ],
    )


class TradeProposal(BaseModel):
    strategy: str
    underlying: str
    spot: float
    expiry: dt.date
    dte: int
    legs: list[ProposalLeg]
    net_credit: float                       # per share; positive = credit
    max_profit: float                       # $ per 1x position
    max_loss: float                         # $ per 1x position (worst case)
    collateral: float                       # $ tied up (cash secured / defined risk)
    breakevens: list[float]
    pop_delta: float                        # 1 - |delta| quick estimate
    pop_model: float                        # lognormal breakeven model estimate
    annualized_yield_on_collateral: float
    greeks: PositionGreeks
    requires_margin_account: bool = False
    warnings: list[str] = []
    exit_plan: ExitPlan
    thesis: str


class Strategy(ABC):
    """A strategy turns one option chain into ranked TradeProposals."""

    name: ClassVar[str]

    @abstractmethod
    def propose(
        self,
        chain: OptionChain,
        config: QuantDeskConfig,
        div_yield: float = 0.0,
    ) -> list[TradeProposal]:
        """Return proposals ranked best-first. Empty list = nothing qualifies."""
