"""Known-value, parity, finite-difference, and IV round-trip tests for BSM.

Acceptance criteria (Phase 1): prices/Greeks match reference values to
1e-4 on an ITM/ATM/OTM x 7/30/90/365 DTE x vol 10-80% matrix, and the
IV solver round-trips price -> IV -> price.
"""

from __future__ import annotations

import itertools

import pytest

from quantdesk.analytics.black_scholes import (
    Greeks,
    bs_greeks,
    bs_price,
    implied_vol,
    no_arbitrage_bounds,
)

# The acceptance matrix: moneyness x DTE x vol, both option types.
MONEYNESS = (0.85, 1.0, 1.15)  # K = S * m -> ITM/ATM/OTM per side
DTES = (7, 30, 90, 365)
VOLS = (0.10, 0.20, 0.40, 0.80)
SPOT, RATE, DIV = 100.0, 0.045, 0.012


def matrix() -> list[tuple[str, float, float, float]]:
    cases = []
    for opt_type, m, dte, sigma in itertools.product(
        ("call", "put"), MONEYNESS, DTES, VOLS
    ):
        cases.append((opt_type, SPOT * m, dte / 365.0, sigma))
    return cases


class TestKnownValues:
    """Textbook reference values."""

    def test_classic_atm_call(self) -> None:
        # S=100 K=100 T=1 r=5% sigma=20% q=0: canonical BSM example.
        assert bs_price("call", 100, 100, 1.0, 0.05, 0.20) == pytest.approx(
            10.450584, abs=1e-4
        )

    def test_classic_atm_put(self) -> None:
        assert bs_price("put", 100, 100, 1.0, 0.05, 0.20) == pytest.approx(
            5.573526, abs=1e-4
        )

    def test_hull_example(self) -> None:
        # Hull, "Options, Futures and Other Derivatives": S=42 K=40
        # r=10% sigma=20% T=0.5 -> c=4.76, p=0.81 (2 dp).
        assert bs_price("call", 42, 40, 0.5, 0.10, 0.20) == pytest.approx(4.76, abs=5e-3)
        assert bs_price("put", 42, 40, 0.5, 0.10, 0.20) == pytest.approx(0.81, abs=5e-3)

    def test_atm_vega_per_point(self) -> None:
        # Annual vega = S * n(d1) * sqrt(T); d1=0.35 -> n(d1)=0.375240
        g = bs_greeks("call", 100, 100, 1.0, 0.05, 0.20)
        assert g.vega_per_pt == pytest.approx(0.375240, abs=1e-3)

    def test_atm_call_delta(self) -> None:
        # delta = N(d1) = N(0.35) = 0.636831
        g = bs_greeks("call", 100, 100, 1.0, 0.05, 0.20)
        assert g.delta == pytest.approx(0.636831, abs=1e-4)


class TestPutCallParity:
    """call - put = S e^{-qT} - K e^{-rT} across the whole matrix."""

    @pytest.mark.parametrize("strike_mult,dte,sigma", list(
        itertools.product(MONEYNESS, DTES, VOLS)
    ))
    def test_parity(self, strike_mult: float, dte: int, sigma: float) -> None:
        import math

        k = SPOT * strike_mult
        t = dte / 365.0
        c = bs_price("call", SPOT, k, t, RATE, sigma, DIV)
        p = bs_price("put", SPOT, k, t, RATE, sigma, DIV)
        lhs = c - p
        rhs = SPOT * math.exp(-DIV * t) - k * math.exp(-RATE * t)
        assert lhs == pytest.approx(rhs, abs=1e-9)


class TestGreeksAgainstFiniteDifferences:
    """Analytic Greeks must agree with numeric derivatives of the price."""

    @pytest.mark.parametrize("opt_type,strike,t,sigma", matrix())
    def test_all_greeks(
        self, opt_type: str, strike: float, t: float, sigma: float
    ) -> None:
        g: Greeks = bs_greeks(opt_type, SPOT, strike, t, RATE, sigma, DIV)  # type: ignore[arg-type]

        h_s = SPOT * 1e-4
        delta_fd = (
            bs_price(opt_type, SPOT + h_s, strike, t, RATE, sigma, DIV)  # type: ignore[arg-type]
            - bs_price(opt_type, SPOT - h_s, strike, t, RATE, sigma, DIV)  # type: ignore[arg-type]
        ) / (2 * h_s)
        assert g.delta == pytest.approx(delta_fd, abs=1e-5)

        gamma_fd = (
            bs_price(opt_type, SPOT + h_s, strike, t, RATE, sigma, DIV)  # type: ignore[arg-type]
            - 2 * bs_price(opt_type, SPOT, strike, t, RATE, sigma, DIV)  # type: ignore[arg-type]
            + bs_price(opt_type, SPOT - h_s, strike, t, RATE, sigma, DIV)  # type: ignore[arg-type]
        ) / (h_s**2)
        assert g.gamma == pytest.approx(gamma_fd, abs=1e-5)

        h_t = min(t * 1e-3, 1e-4)
        theta_annual_fd = -(
            bs_price(opt_type, SPOT, strike, t + h_t, RATE, sigma, DIV)  # type: ignore[arg-type]
            - bs_price(opt_type, SPOT, strike, t - h_t, RATE, sigma, DIV)  # type: ignore[arg-type]
        ) / (2 * h_t)
        assert g.theta_per_day * 365.0 == pytest.approx(theta_annual_fd, abs=1e-3)

        h_v = 1e-5
        vega_annual_fd = (
            bs_price(opt_type, SPOT, strike, t, RATE, sigma + h_v, DIV)  # type: ignore[arg-type]
            - bs_price(opt_type, SPOT, strike, t, RATE, sigma - h_v, DIV)  # type: ignore[arg-type]
        ) / (2 * h_v)
        assert g.vega_per_pt * 100.0 == pytest.approx(vega_annual_fd, abs=1e-4)

        h_r = 1e-6
        rho_annual_fd = (
            bs_price(opt_type, SPOT, strike, t, RATE + h_r, sigma, DIV)  # type: ignore[arg-type]
            - bs_price(opt_type, SPOT, strike, t, RATE - h_r, sigma, DIV)  # type: ignore[arg-type]
        ) / (2 * h_r)
        assert g.rho_per_pt * 100.0 == pytest.approx(rho_annual_fd, abs=1e-4)


class TestImpliedVol:
    @pytest.mark.parametrize("opt_type,strike,t,sigma", matrix())
    def test_round_trip(
        self, opt_type: str, strike: float, t: float, sigma: float
    ) -> None:
        price = bs_price(opt_type, SPOT, strike, t, RATE, sigma, DIV)  # type: ignore[arg-type]
        lo, _ = no_arbitrage_bounds(opt_type, SPOT, strike, t, RATE, DIV)  # type: ignore[arg-type]
        if price - lo < 1e-8:
            pytest.skip("price has no meaningful extrinsic value; IV undefined")
        iv = implied_vol(opt_type, price, SPOT, strike, t, RATE, DIV)  # type: ignore[arg-type]
        assert iv == pytest.approx(sigma, abs=1e-6)
        reprice = bs_price(opt_type, SPOT, strike, t, RATE, iv, DIV)  # type: ignore[arg-type]
        assert reprice == pytest.approx(price, abs=1e-4)

    def test_price_below_intrinsic_raises(self) -> None:
        # Deep ITM call quoted below its discounted intrinsic: no IV exists.
        with pytest.raises(ValueError, match="floor"):
            implied_vol("call", 10.0, 100.0, 85.0, 30 / 365, 0.045)

    def test_price_above_ceiling_raises(self) -> None:
        with pytest.raises(ValueError, match="ceiling"):
            implied_vol("call", 101.0, 100.0, 100.0, 30 / 365, 0.045)

    def test_expired_raises(self) -> None:
        with pytest.raises(ValueError, match="expiry"):
            implied_vol("call", 5.0, 100.0, 100.0, 0.0, 0.045)


class TestEdgeCases:
    def test_expiry_returns_intrinsic(self) -> None:
        assert bs_price("call", 110, 100, 0.0, 0.05, 0.2) == 10.0
        assert bs_price("put", 110, 100, 0.0, 0.05, 0.2) == 0.0

    def test_zero_vol_returns_discounted_payoff(self) -> None:
        import math

        price = bs_price("call", 110, 100, 1.0, 0.05, 0.0)
        assert price == pytest.approx(110 - 100 * math.exp(-0.05), abs=1e-9)

    def test_negative_inputs_raise(self) -> None:
        with pytest.raises(ValueError):
            bs_price("call", -1, 100, 1.0, 0.05, 0.2)
        with pytest.raises(ValueError):
            bs_price("call", 100, 100, 1.0, 0.05, -0.2)

    def test_call_price_monotone_in_vol(self) -> None:
        prices = [bs_price("call", 100, 105, 0.25, 0.05, v) for v in (0.1, 0.2, 0.4, 0.8)]
        assert prices == sorted(prices)
