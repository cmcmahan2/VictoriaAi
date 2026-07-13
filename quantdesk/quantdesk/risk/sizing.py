"""Position sizing: fractional Kelly, hard-capped, VIX-regime scaled.

Sizing philosophy, in order of authority:
  1. Fixed-fraction hard caps ALWAYS bind (max % of account per position,
     max % deployed). Kelly can only size DOWN from the cap, never up.
  2. Kelly fraction is estimated from the proposal's POP and the payoff
     structure ENFORCED BY THE EXIT PLAN (full credit if it expires,
     stop-loss multiple if it doesn't) — not from the theoretical
     stock-to-zero max loss, which would produce useless microscopic
     sizes, and not from raw max profit, which would overbet. This is an
     estimate built on an estimate; the quarter-Kelly default multiplier
     exists precisely because inputs are noisy.
  3. The VIX regime multiplier scales the result (x0.5 above VIX 30,
     x0.0 above 40 — new-trade freeze).
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from quantdesk.analytics.regime import classify_regime
from quantdesk.config import QuantDeskConfig


def kelly_binary(p_win: float, win: float, loss: float) -> float:
    """Kelly optimal bankroll fraction for a binary bet.

    f* = (p*b - q) / b   where b = win/loss, q = 1 - p.

    Floored at 0 (negative edge => no bet). ``win`` and ``loss`` are both
    positive magnitudes per unit risked.
    """
    if not 0.0 <= p_win <= 1.0:
        raise ValueError(f"p_win must be in [0,1] (got {p_win})")
    if win <= 0 or loss <= 0:
        raise ValueError("win and loss must be positive magnitudes")
    b = win / loss
    f_star = (p_win * b - (1.0 - p_win)) / b
    return max(f_star, 0.0)


class SizeRecommendation(BaseModel):
    contracts: int
    collateral_per_contract: float
    collateral_total: float
    kelly_raw: float            # full-Kelly fraction of account
    kelly_applied: float        # after fractional multiplier
    cap_fraction: float         # fixed-fraction hard cap
    regime_multiplier: float
    final_fraction: float       # what was actually used
    notes: list[str]


def recommend_size(
    account_usd: float,
    collateral_per_contract: float,
    pop: float,
    win_per_contract: float,
    loss_per_contract: float,
    vix: float,
    config: QuantDeskConfig,
) -> SizeRecommendation:
    """Contracts to trade for one proposal, per the sizing hierarchy above.

    ``win_per_contract``: credit kept if the trade wins (dollars).
    ``loss_per_contract``: loss at the enforced stop (dollars) — pass the
    exit-plan stop loss, not the theoretical max.
    """
    if account_usd <= 0 or collateral_per_contract <= 0:
        raise ValueError("account and collateral must be positive")

    notes: list[str] = []
    kelly_raw = kelly_binary(pop, win_per_contract, loss_per_contract)
    kelly_applied = kelly_raw * config.risk.kelly_fraction
    cap = config.risk.max_position_pct
    fraction = min(kelly_applied, cap)
    if kelly_applied >= cap:
        notes.append(
            f"Kelly ({kelly_applied:.1%}) above the fixed cap — capped at {cap:.1%}."
        )
    if kelly_raw == 0.0:
        notes.append(
            "Kelly sees NO EDGE at this POP/payoff (estimate) — size zero; "
            "if you trade it anyway, that is discretion, not process."
        )

    regime = classify_regime(vix)
    fraction *= regime.sizing_multiplier
    if regime.sizing_multiplier < 1.0:
        notes.extend(regime.notes)

    contracts = math.floor(fraction * account_usd / collateral_per_contract)
    if contracts == 0 and fraction > 0:
        notes.append(
            f"Account too small: {fraction:.1%} of ${account_usd:,.0f} = "
            f"${fraction * account_usd:,.0f} < ${collateral_per_contract:,.0f} "
            "collateral for a single contract. Honest answer: zero contracts."
        )
    return SizeRecommendation(
        contracts=contracts,
        collateral_per_contract=collateral_per_contract,
        collateral_total=contracts * collateral_per_contract,
        kelly_raw=kelly_raw,
        kelly_applied=kelly_applied,
        cap_fraction=cap,
        regime_multiplier=regime.sizing_multiplier,
        final_fraction=fraction,
        notes=notes,
    )
