"""Cash-secured puts — the workhorse VRP harvest.

Sell an OTM put inside the target delta band, fully collateralized by
cash. Assignment is an acceptable outcome (it feeds the wheel), which
is why the freefall and earnings filters upstream matter: only take
assignment risk in names you would own at that price.
"""

from __future__ import annotations

import datetime as dt

from quantdesk.analytics import black_scholes as bs
from quantdesk.analytics import probability as prob
from quantdesk.config import QuantDeskConfig
from quantdesk.data.models import OptionChain
from quantdesk.screener.universe import find_csp_strikes
from quantdesk.strategies.base import (
    PositionGreeks,
    ProposalLeg,
    Strategy,
    TradeProposal,
    build_exit_plan,
)


class CashSecuredPut(Strategy):
    name = "csp"

    def propose(
        self,
        chain: OptionChain,
        config: QuantDeskConfig,
        div_yield: float = 0.0,
    ) -> list[TradeProposal]:
        csp_cfg = config.strategy.csp
        rate = config.data.risk_free_rate
        dte = max((chain.expiry - dt.date.today()).days, 1)
        t_years = dte / 365.0

        candidates = find_csp_strikes(
            chain, rate, div_yield, csp_cfg.delta_min, csp_cfg.delta_max
        )
        proposals: list[TradeProposal] = []
        for cand in candidates:
            strike = cand.contract.strike
            credit = cand.mid
            greeks = bs.bs_greeks(
                "put", chain.spot, strike, t_years, rate, cand.iv, div_yield
            )
            breakeven = prob.short_put_breakeven(strike, credit)
            pop_model = prob.pop_short_put(
                chain.spot, strike, credit, t_years, rate, cand.iv, div_yield
            )
            warnings: list[str] = []
            if cand.annualized_yield < csp_cfg.min_annualized_yield:
                warnings.append(
                    f"annualized yield {cand.annualized_yield:.1%} below the "
                    f"{csp_cfg.min_annualized_yield:.0%} minimum — thin pay for the risk"
                )
            thesis = (
                f"Sell the {chain.underlying} {strike:g} put ({dte} DTE) for "
                f"~{credit:.2f} against ${strike * 100:,.0f} cash collateral — "
                f"{cand.annualized_yield:.1%} annualized if it expires worthless. "
                f"At {cand.delta:.2f} delta the market assigns roughly a "
                f"{abs(cand.delta):.0%} chance of finishing ITM; the lognormal "
                f"model puts profit probability at {pop_model:.0%} "
                f"(breakeven {breakeven:.2f}). This is a VRP harvest: IV "
                f"{cand.iv:.1%} on this strike vs recent realized vol — you are "
                f"selling insurance, and assignment at an effective "
                f"{breakeven:.2f} cost basis must be an acceptable outcome."
            )
            proposals.append(
                TradeProposal(
                    strategy=self.name,
                    underlying=chain.underlying,
                    spot=chain.spot,
                    expiry=chain.expiry,
                    dte=dte,
                    legs=[
                        ProposalLeg(action="sell", contract=cand.contract, price=credit)
                    ],
                    net_credit=credit,
                    max_profit=credit * 100.0,
                    max_loss=(strike - credit) * 100.0,  # underlying to zero
                    collateral=strike * 100.0,
                    breakevens=[breakeven],
                    pop_delta=prob.pop_from_delta(cand.delta),
                    pop_model=pop_model,
                    annualized_yield_on_collateral=cand.annualized_yield,
                    greeks=PositionGreeks(
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
        # find_csp_strikes already ranks by annualized yield, best first.
        return proposals
