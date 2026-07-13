"""Chain-level analytics helpers shared by the CLI and the screener."""

from __future__ import annotations

import datetime as dt

from quantdesk.analytics import black_scholes as bs
from quantdesk.data.models import OptionChain, OptionType


def atm_iv_from_chain(
    chain: OptionChain, rate: float, div_yield: float
) -> float | None:
    """ATM IV: average of solver-derived call and put IV at the ATM strike.

    Uses QuantDesk's own Brent solver on mid prices — yfinance's IV field
    is untrustworthy. Returns None if neither side is solvable.
    """
    t_years = max((chain.expiry - dt.date.today()).days, 1) / 365.0
    strike = chain.atm_strike()
    ivs: list[float] = []
    opt_types: tuple[OptionType, ...] = ("call", "put")
    for opt_type in opt_types:
        contract = chain.contract_at(opt_type, strike)
        mid = contract.mid if contract else None
        if mid is None or mid <= 0:
            continue
        try:
            ivs.append(
                bs.implied_vol(opt_type, mid, chain.spot, strike, t_years, rate, div_yield)
            )
        except ValueError:
            continue
    return sum(ivs) / len(ivs) if ivs else None
