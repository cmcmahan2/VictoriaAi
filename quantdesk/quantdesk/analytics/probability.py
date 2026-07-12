"""Probability analytics: POP, probability of touch, breakevens, assignment.

Everything here is an ESTIMATE under risk-neutral lognormal dynamics
(GBM with drift r - q). Real distributions have fat left tails, which is
precisely why the VRP exists — treat these numbers as planning inputs,
not guarantees, and always present both the delta-approximation and the
lognormal model where the UI shows POP.
"""

from __future__ import annotations

import math

from quantdesk.analytics.black_scholes import _d1_d2, norm_cdf
from quantdesk.data.models import OptionType


def prob_itm(
    option_type: OptionType,
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    sigma: float,
    div_yield: float = 0.0,
) -> float:
    """Risk-neutral probability the option finishes in the money.

    P(S_T > K) = N(d2) for calls; P(S_T < K) = N(-d2) for puts.
    """
    if t_years <= 0:
        if option_type == "call":
            return 1.0 if spot > strike else 0.0
        return 1.0 if spot < strike else 0.0
    if sigma <= 0:
        fwd = spot * math.exp((rate - div_yield) * t_years)
        if option_type == "call":
            return 1.0 if fwd > strike else 0.0
        return 1.0 if fwd < strike else 0.0
    _, d2 = _d1_d2(spot, strike, t_years, rate, sigma, div_yield)
    return norm_cdf(d2) if option_type == "call" else norm_cdf(-d2)


def pop_from_delta(delta: float) -> float:
    """Quick-and-dirty POP for a short option: 1 - |delta|.

    The standard desk approximation (delta ~ prob ITM). Biased optimistic
    because it ignores the credit received and drift; show alongside the
    lognormal POP, never alone.
    """
    return 1.0 - min(abs(delta), 1.0)


def short_put_breakeven(strike: float, credit: float) -> float:
    """Short put breakeven at expiry: strike - credit received."""
    return strike - credit


def short_call_breakeven(strike: float, credit: float) -> float:
    """Short call breakeven at expiry: strike + credit received."""
    return strike + credit


def pop_short_put(
    spot: float,
    strike: float,
    credit: float,
    t_years: float,
    rate: float,
    sigma: float,
    div_yield: float = 0.0,
) -> float:
    """Lognormal POP for a short put: P(S_T > strike - credit).

    Profit at expiry whenever spot finishes above breakeven (including
    partial-loss-avoided region between strike and breakeven).
    """
    breakeven = short_put_breakeven(strike, credit)
    if breakeven <= 0:
        return 1.0
    return 1.0 - prob_itm("put", spot, breakeven, t_years, rate, sigma, div_yield)


def pop_short_call(
    spot: float,
    strike: float,
    credit: float,
    t_years: float,
    rate: float,
    sigma: float,
    div_yield: float = 0.0,
) -> float:
    """Lognormal POP for a short call: P(S_T < strike + credit)."""
    breakeven = short_call_breakeven(strike, credit)
    return 1.0 - prob_itm("call", spot, breakeven, t_years, rate, sigma, div_yield)


def prob_touch(
    spot: float,
    barrier: float,
    t_years: float,
    rate: float,
    sigma: float,
    div_yield: float = 0.0,
) -> float:
    """Probability the underlying touches ``barrier`` at any time before T.

    Exact first-passage probability for GBM under the risk-neutral
    measure. With nu = r - q - sigma^2/2 and b = ln(B/S):

      upper barrier (b > 0):
        P = N((-b + nu T)/(sigma sqrt(T))) + e^{2 nu b / sigma^2} N((-b - nu T)/(sigma sqrt(T)))
      lower barrier (b < 0):
        P = N(( b - nu T)/(sigma sqrt(T))) + e^{2 nu b / sigma^2} N(( b + nu T)/(sigma sqrt(T)))

    Always >= prob ITM at the same strike — options are "touched" far more
    often than they finish ITM, which is why mechanical stop-losses on
    short premium get whipsawed.
    """
    if spot <= 0 or barrier <= 0:
        raise ValueError("spot and barrier must be positive")
    if t_years <= 0 or sigma <= 0:
        return 1.0 if math.isclose(spot, barrier) else 0.0
    if math.isclose(spot, barrier):
        return 1.0

    nu = rate - div_yield - 0.5 * sigma * sigma
    b = math.log(barrier / spot)
    sig_sqrt_t = sigma * math.sqrt(t_years)
    exp_term = math.exp(2.0 * nu * b / (sigma * sigma))
    if b > 0:
        p = norm_cdf((-b + nu * t_years) / sig_sqrt_t) + exp_term * norm_cdf(
            (-b - nu * t_years) / sig_sqrt_t
        )
    else:
        p = norm_cdf((b - nu * t_years) / sig_sqrt_t) + exp_term * norm_cdf(
            (b + nu * t_years) / sig_sqrt_t
        )
    return min(max(p, 0.0), 1.0)


def early_assignment_risk(
    option_type: OptionType,
    spot: float,
    strike: float,
    option_mid: float,
    dividend_before_expiry: float = 0.0,
) -> tuple[str, str]:
    """Heuristic early-assignment risk for a SHORT American option.

    Returns (level, reason) with level in {"LOW", "MODERATE", "HIGH"}.

    Rational counterparties exercise early only when the extrinsic value
    left is less than what they gain: an imminent dividend (calls) or the
    carry on deep-ITM strikes (puts). Proxy: compare remaining extrinsic
    to the dividend and to a small absolute floor. Heuristic, not a model.
    """
    intrinsic = max(
        (spot - strike) if option_type == "call" else (strike - spot), 0.0
    )
    extrinsic = max(option_mid - intrinsic, 0.0)
    if intrinsic <= 0:
        return "LOW", "option is out of the money; early assignment is irrational"
    if option_type == "call" and dividend_before_expiry > extrinsic:
        return (
            "HIGH",
            f"dividend {dividend_before_expiry:.2f} exceeds remaining extrinsic "
            f"{extrinsic:.2f} — ITM calls are routinely exercised for the dividend",
        )
    if extrinsic < 0.05:
        return (
            "HIGH",
            f"extrinsic value nearly gone ({extrinsic:.2f}); deep-ITM shorts "
            "get assigned",
        )
    if extrinsic < 0.20:
        return "MODERATE", f"extrinsic value thin ({extrinsic:.2f}); monitor daily"
    return "LOW", f"meaningful extrinsic remains ({extrinsic:.2f})"
