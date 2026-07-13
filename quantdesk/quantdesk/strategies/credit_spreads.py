"""Put credit spreads: defined-risk premium selling. MARGIN ACCOUNTS ONLY.

Sell a put in the target delta band, buy a put ``width`` lower. Risk is
capped at (width - credit) so no cash-secured collateral is needed —
but that requires a margin account, and registered accounts (TFSA)
cannot hold them. Every proposal is tagged ``requires_margin_account``.
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


class PutCreditSpread(Strategy):
    name = "put-credit-spread"

    def propose(
        self,
        chain: OptionChain,
        config: QuantDeskConfig,
        div_yield: float = 0.0,
    ) -> list[TradeProposal]:
        csp_cfg = config.strategy.csp
        spread_cfg = config.strategy.spreads
        rate = config.data.risk_free_rate
        dte = max((chain.expiry - dt.date.today()).days, 1)
        t_years = dte / 365.0
        width = spread_cfg.width
        min_credit = width * spread_cfg.min_credit_fraction

        shorts = find_csp_strikes(
            chain, rate, div_yield, csp_cfg.delta_min, csp_cfg.delta_max
        )
        proposals: list[TradeProposal] = []
        for short in shorts:
            short_k = short.contract.strike
            long_contract = chain.contract_at("put", short_k - width)
            if long_contract is None:
                continue  # no listed strike exactly one width below
            long_mid = long_contract.mid
            if long_mid is None or long_mid <= 0:
                continue
            credit = short.mid - long_mid
            if credit < min_credit:
                continue  # not paid enough for the risk — hard requirement
            try:
                long_iv = bs.implied_vol(
                    "put", long_mid, chain.spot, long_contract.strike,
                    t_years, rate, div_yield,
                )
            except ValueError:
                continue

            g_short = bs.bs_greeks(
                "put", chain.spot, short_k, t_years, rate, short.iv, div_yield
            )
            g_long = bs.bs_greeks(
                "put", chain.spot, long_contract.strike, t_years, rate,
                long_iv, div_yield,
            )
            max_loss = (width - credit) * 100.0
            breakeven = short_k - credit
            pop_model = prob.pop_short_put(
                chain.spot, short_k, credit, t_years, rate, short.iv, div_yield
            )
            annualized_yield = (credit * 100.0 / max_loss) * (365.0 / dte)
            thesis = (
                f"Sell the {chain.underlying} {short_k:g}/{long_contract.strike:g} "
                f"put spread ({dte} DTE) for ~{credit:.2f} — risking "
                f"${max_loss:,.0f} to make ${credit * 100:,.0f} "
                f"({credit / width:.0%} of the {width:g} width; minimum "
                f"{spread_cfg.min_credit_fraction:.0%}). Defined risk below "
                f"{long_contract.strike:g}; breakeven {breakeven:.2f}, model POP "
                f"{pop_model:.0%}. MARGIN ACCOUNT REQUIRED — not available in "
                f"registered accounts."
            )
            proposals.append(
                TradeProposal(
                    strategy=self.name,
                    underlying=chain.underlying,
                    spot=chain.spot,
                    expiry=chain.expiry,
                    dte=dte,
                    legs=[
                        ProposalLeg(
                            action="sell", contract=short.contract, price=short.mid
                        ),
                        ProposalLeg(
                            action="buy", contract=long_contract, price=long_mid
                        ),
                    ],
                    net_credit=credit,
                    max_profit=credit * 100.0,
                    max_loss=max_loss,
                    collateral=max_loss,  # defined-risk margin requirement
                    breakevens=[breakeven],
                    pop_delta=prob.pop_from_delta(short.delta),
                    pop_model=pop_model,
                    annualized_yield_on_collateral=annualized_yield,
                    greeks=PositionGreeks(
                        delta_shares=(-g_short.delta + g_long.delta) * 100.0,
                        gamma_shares=(-g_short.gamma + g_long.gamma) * 100.0,
                        theta_usd_day=(-g_short.theta_per_day + g_long.theta_per_day)
                        * 100.0,
                        vega_usd_pt=(-g_short.vega_per_pt + g_long.vega_per_pt)
                        * 100.0,
                    ),
                    requires_margin_account=True,
                    warnings=[],
                    exit_plan=build_exit_plan(credit, config.strategy.exits),
                    thesis=thesis,
                )
            )
        proposals.sort(
            key=lambda p: p.annualized_yield_on_collateral, reverse=True
        )
        return proposals
