"""Covered calls: sell OTM calls against 100 owned shares.

Same VRP logic as the CSP, opposite side. The one extra input is cost
basis — a strike below basis locks in a stock loss if assigned, which
the proposal flags loudly rather than hides.
"""

from __future__ import annotations

import datetime as dt

from quantdesk.analytics import black_scholes as bs
from quantdesk.analytics import probability as prob
from quantdesk.config import QuantDeskConfig
from quantdesk.data.models import OptionChain
from quantdesk.strategies.base import (
    PositionGreeks,
    ProposalLeg,
    Strategy,
    TradeProposal,
    build_exit_plan,
)


class CoveredCall(Strategy):
    name = "covered-call"

    def __init__(self, cost_basis: float | None = None) -> None:
        # None => basis unknown; spot is used with a warning.
        self.cost_basis = cost_basis

    def propose(
        self,
        chain: OptionChain,
        config: QuantDeskConfig,
        div_yield: float = 0.0,
    ) -> list[TradeProposal]:
        cc_delta_min, cc_delta_max = 0.15, 0.30  # mirror of the CSP band
        rate = config.data.risk_free_rate
        dte = max((chain.expiry - dt.date.today()).days, 1)
        t_years = dte / 365.0

        basis_warning: list[str] = []
        basis = self.cost_basis
        if basis is None:
            basis = chain.spot
            basis_warning = [
                "cost basis not provided — using spot; pass --cost-basis for real numbers"
            ]

        proposals: list[TradeProposal] = []
        for contract in chain.calls:
            if contract.strike <= chain.spot:
                continue  # write OTM calls only
            mid = contract.mid
            if mid is None or mid <= 0:
                continue
            try:
                iv = bs.implied_vol(
                    "call", mid, chain.spot, contract.strike, t_years, rate, div_yield
                )
            except ValueError:
                continue
            greeks = bs.bs_greeks(
                "call", chain.spot, contract.strike, t_years, rate, iv, div_yield
            )
            if not (cc_delta_min <= greeks.delta <= cc_delta_max):
                continue

            strike = contract.strike
            credit = mid
            warnings = list(basis_warning)
            if strike < basis:
                warnings.append(
                    f"strike {strike:g} is BELOW cost basis {basis:,.2f} — "
                    "assignment locks in a stock loss"
                )
            pop_model = prob.pop_short_call(
                chain.spot, strike, credit, t_years, rate, iv, div_yield
            )
            annualized_yield = (credit / chain.spot) * (365.0 / dte)
            thesis = (
                f"Sell the {chain.underlying} {strike:g} call ({dte} DTE) for "
                f"~{credit:.2f} against 100 owned shares — {annualized_yield:.1%} "
                f"annualized on current stock value. Keeps the premium unless "
                f"spot finishes above {strike:g}; if called away, total exit is "
                f"{strike + credit - basis:+.2f}/share vs basis {basis:,.2f}. "
                f"Lognormal odds the call expires worthless: {pop_model:.0%}."
            )
            proposals.append(
                TradeProposal(
                    strategy=self.name,
                    underlying=chain.underlying,
                    spot=chain.spot,
                    expiry=chain.expiry,
                    dte=dte,
                    legs=[ProposalLeg(action="sell", contract=contract, price=credit)],
                    net_credit=credit,
                    max_profit=(strike - basis + credit) * 100.0,
                    max_loss=(basis - credit) * 100.0,  # stock to zero, net of credit
                    collateral=0.0,  # covered by the shares, no new cash
                    breakevens=[basis - credit],
                    pop_delta=prob.pop_from_delta(greeks.delta),
                    pop_model=pop_model,
                    annualized_yield_on_collateral=annualized_yield,
                    greeks=PositionGreeks(
                        # Short call only: the shares' +100 delta is portfolio
                        # context (Phase 4 aggregates it), not the option's.
                        delta_shares=-greeks.delta * 100.0,
                        gamma_shares=-greeks.gamma * 100.0,
                        theta_usd_day=-greeks.theta_per_day * 100.0,
                        vega_usd_pt=-greeks.vega_per_pt * 100.0,
                    ),
                    warnings=warnings,
                    exit_plan=build_exit_plan(credit, config.strategy.exits),
                    thesis=thesis,
                )
            )
        proposals.sort(
            key=lambda p: p.annualized_yield_on_collateral, reverse=True
        )
        return proposals
