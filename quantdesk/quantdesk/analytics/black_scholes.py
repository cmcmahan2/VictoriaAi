"""Black-Scholes-Merton pricing, Greeks, and implied volatility.

European options on an underlying with continuous dividend yield ``q``:

    d1 = (ln(S/K) + (r - q + sigma^2 / 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    call = S e^{-qT} N(d1) - K e^{-rT} N(d2)
    put  = K e^{-rT} N(-d2) - S e^{-qT} N(-d1)

Conventions (chosen for how a trader reads a chain):

* ``theta`` is **per calendar day** (annual theta / 365).
* ``vega`` is **per 1 volatility point** (i.e. per 0.01 change in sigma).
* ``rho`` is **per 1 percentage point** of rate (per 0.01 change in r).
* ``T`` is in **years** (calendar days / 365).

American-style equity options are priced here with the European model —
fine for the OTM, short-dated, dividend-light contracts QuantDesk deals
in, but a known approximation. Deep-ITM puts and calls facing an
imminent dividend carry early-exercise value the model ignores.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq

from quantdesk.data.models import OptionType

# Solver bounds: 0.01% to 500% vol covers anything a listed option prints.
_IV_LO = 1e-4
_IV_HI = 5.0


def norm_cdf(x: float) -> float:
    """Standard normal CDF via the error function (no scipy needed)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(
    spot: float, strike: float, t_years: float, rate: float, sigma: float, div_yield: float
) -> tuple[float, float]:
    sig_sqrt_t = sigma * math.sqrt(t_years)
    d1 = (
        math.log(spot / strike) + (rate - div_yield + 0.5 * sigma * sigma) * t_years
    ) / sig_sqrt_t
    return d1, d1 - sig_sqrt_t


def _validate(spot: float, strike: float, sigma: float) -> None:
    if spot <= 0 or strike <= 0:
        raise ValueError(f"spot and strike must be positive (got S={spot}, K={strike})")
    if sigma < 0:
        raise ValueError(f"sigma must be non-negative (got {sigma})")


def bs_price(
    option_type: OptionType,
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    sigma: float,
    div_yield: float = 0.0,
) -> float:
    """BSM European price. At T<=0 or sigma=0, returns the deterministic value."""
    _validate(spot, strike, sigma)
    if t_years <= 0:
        intrinsic = spot - strike if option_type == "call" else strike - spot
        return max(intrinsic, 0.0)
    if sigma == 0.0:
        fwd = spot * math.exp(-div_yield * t_years)
        pv_k = strike * math.exp(-rate * t_years)
        payoff = fwd - pv_k if option_type == "call" else pv_k - fwd
        return max(payoff, 0.0)
    d1, d2 = _d1_d2(spot, strike, t_years, rate, sigma, div_yield)
    disc_s = spot * math.exp(-div_yield * t_years)
    disc_k = strike * math.exp(-rate * t_years)
    if option_type == "call":
        return disc_s * norm_cdf(d1) - disc_k * norm_cdf(d2)
    return disc_k * norm_cdf(-d2) - disc_s * norm_cdf(-d1)


@dataclass(frozen=True)
class Greeks:
    """Full Greek set. Units documented in the module docstring."""

    price: float
    delta: float
    gamma: float
    theta_per_day: float
    vega_per_pt: float
    rho_per_pt: float


def bs_greeks(
    option_type: OptionType,
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    sigma: float,
    div_yield: float = 0.0,
) -> Greeks:
    """Analytic BSM Greeks.

    Formulas (call; put via parity relations):
        delta = e^{-qT} N(d1)
        gamma = e^{-qT} n(d1) / (S sigma sqrt(T))
        theta = -S e^{-qT} n(d1) sigma / (2 sqrt(T))
                + q S e^{-qT} N(d1) - r K e^{-rT} N(d2)      [annual]
        vega  = S e^{-qT} n(d1) sqrt(T)                       [per 1.00 vol]
        rho   = K T e^{-rT} N(d2)                             [per 1.00 rate]
    """
    _validate(spot, strike, sigma)
    if t_years <= 0 or sigma == 0.0:
        price = bs_price(option_type, spot, strike, t_years, rate, sigma, div_yield)
        if option_type == "call":
            itm = spot * math.exp(-div_yield * max(t_years, 0.0)) > strike * math.exp(
                -rate * max(t_years, 0.0)
            )
            delta = 1.0 if itm else 0.0
        else:
            itm = spot * math.exp(-div_yield * max(t_years, 0.0)) < strike * math.exp(
                -rate * max(t_years, 0.0)
            )
            delta = -1.0 if itm else 0.0
        return Greeks(price, delta, 0.0, 0.0, 0.0, 0.0)

    d1, d2 = _d1_d2(spot, strike, t_years, rate, sigma, div_yield)
    eq = math.exp(-div_yield * t_years)
    er = math.exp(-rate * t_years)
    pdf_d1 = norm_pdf(d1)
    sqrt_t = math.sqrt(t_years)

    gamma = eq * pdf_d1 / (spot * sigma * sqrt_t)
    vega_annual = spot * eq * pdf_d1 * sqrt_t

    if option_type == "call":
        delta = eq * norm_cdf(d1)
        theta_annual = (
            -spot * eq * pdf_d1 * sigma / (2.0 * sqrt_t)
            + div_yield * spot * eq * norm_cdf(d1)
            - rate * strike * er * norm_cdf(d2)
        )
        rho_annual = strike * t_years * er * norm_cdf(d2)
    else:
        delta = -eq * norm_cdf(-d1)
        theta_annual = (
            -spot * eq * pdf_d1 * sigma / (2.0 * sqrt_t)
            - div_yield * spot * eq * norm_cdf(-d1)
            + rate * strike * er * norm_cdf(-d2)
        )
        rho_annual = -strike * t_years * er * norm_cdf(-d2)

    price = bs_price(option_type, spot, strike, t_years, rate, sigma, div_yield)
    return Greeks(
        price=price,
        delta=delta,
        gamma=gamma,
        theta_per_day=theta_annual / 365.0,
        vega_per_pt=vega_annual / 100.0,
        rho_per_pt=rho_annual / 100.0,
    )


def no_arbitrage_bounds(
    option_type: OptionType,
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    div_yield: float = 0.0,
) -> tuple[float, float]:
    """(lower, upper) European no-arbitrage price bounds.

    call in [max(S e^{-qT} - K e^{-rT}, 0),  S e^{-qT}]
    put  in [max(K e^{-rT} - S e^{-qT}, 0),  K e^{-rT}]
    """
    disc_s = spot * math.exp(-div_yield * t_years)
    disc_k = strike * math.exp(-rate * t_years)
    if option_type == "call":
        return max(disc_s - disc_k, 0.0), disc_s
    return max(disc_k - disc_s, 0.0), disc_k


def implied_vol(
    option_type: OptionType,
    price: float,
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    div_yield: float = 0.0,
) -> float:
    """Implied volatility via Brent's method.

    Raises ValueError when the quoted price violates European
    no-arbitrage bounds (including prices at/below discounted intrinsic,
    where IV is undefined) or when it exceeds the price at 500% vol.
    """
    _validate(spot, strike, 1.0)
    if t_years <= 0:
        raise ValueError("cannot solve IV at or past expiry (t_years <= 0)")
    lo_bound, hi_bound = no_arbitrage_bounds(
        option_type, spot, strike, t_years, rate, div_yield
    )
    if price <= lo_bound:
        raise ValueError(
            f"price {price:.4f} at/below no-arbitrage floor {lo_bound:.4f}; "
            "IV undefined (no extrinsic value)"
        )
    if price >= hi_bound:
        raise ValueError(
            f"price {price:.4f} at/above no-arbitrage ceiling {hi_bound:.4f}"
        )

    def objective(sigma: float) -> float:
        return (
            bs_price(option_type, spot, strike, t_years, rate, sigma, div_yield) - price
        )

    f_lo = objective(_IV_LO)
    f_hi = objective(_IV_HI)
    if f_lo > 0:
        # Price below the sigma->0 limit within tolerance; effectively zero vol.
        return _IV_LO
    if f_hi < 0:
        raise ValueError(f"price {price:.4f} implies vol above {_IV_HI:.0%}")
    result = brentq(objective, _IV_LO, _IV_HI, xtol=1e-10, maxiter=200)
    return float(result)
