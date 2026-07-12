"""Tests for POP, probability of touch, breakevens, assignment heuristics."""

from __future__ import annotations

import math

import pytest

from quantdesk.analytics.black_scholes import norm_cdf
from quantdesk.analytics.probability import (
    early_assignment_risk,
    pop_from_delta,
    pop_short_call,
    pop_short_put,
    prob_itm,
    prob_touch,
    short_call_breakeven,
    short_put_breakeven,
)


class TestProbITM:
    def test_call_put_probs_sum_to_one(self) -> None:
        c = prob_itm("call", 100, 95, 30 / 365, 0.05, 0.30)
        p = prob_itm("put", 100, 95, 30 / 365, 0.05, 0.30)
        assert c + p == pytest.approx(1.0, abs=1e-12)

    def test_deep_itm_call_near_one(self) -> None:
        assert prob_itm("call", 100, 50, 30 / 365, 0.05, 0.20) > 0.999

    def test_deep_otm_put_near_zero(self) -> None:
        assert prob_itm("put", 100, 50, 30 / 365, 0.05, 0.20) < 0.001

    def test_expired(self) -> None:
        assert prob_itm("call", 110, 100, 0.0, 0.05, 0.2) == 1.0
        assert prob_itm("put", 110, 100, 0.0, 0.05, 0.2) == 0.0

    def test_matches_n_d2_analytic(self) -> None:
        s, k, t, r, sigma = 100.0, 105.0, 45 / 365, 0.04, 0.25
        d2 = (
            math.log(s / k) + (r - 0.5 * sigma**2) * t
        ) / (sigma * math.sqrt(t))
        assert prob_itm("call", s, k, t, r, sigma) == pytest.approx(
            norm_cdf(d2), abs=1e-12
        )


class TestPOP:
    def test_pop_from_delta(self) -> None:
        assert pop_from_delta(-0.30) == pytest.approx(0.70)
        assert pop_from_delta(0.15) == pytest.approx(0.85)

    def test_breakevens(self) -> None:
        assert short_put_breakeven(100, 2.5) == 97.5
        assert short_call_breakeven(100, 2.5) == 102.5

    def test_zero_credit_pop_equals_prob_otm(self) -> None:
        s, k, t, r, sigma = 100.0, 95.0, 30 / 365, 0.05, 0.30
        pop = pop_short_put(s, k, 0.0, t, r, sigma)
        assert pop == pytest.approx(1.0 - prob_itm("put", s, k, t, r, sigma), abs=1e-12)

    def test_credit_improves_pop(self) -> None:
        s, k, t, r, sigma = 100.0, 95.0, 30 / 365, 0.05, 0.30
        assert pop_short_put(s, k, 2.0, t, r, sigma) > pop_short_put(
            s, k, 0.5, t, r, sigma
        )

    def test_short_call_pop(self) -> None:
        s, k, t, r, sigma = 100.0, 110.0, 30 / 365, 0.05, 0.30
        pop = pop_short_call(s, k, 1.0, t, r, sigma)
        assert pop == pytest.approx(
            1.0 - prob_itm("call", s, k + 1.0, t, r, sigma), abs=1e-12
        )
        assert 0.5 < pop < 1.0


class TestProbTouch:
    def test_touch_geq_itm(self) -> None:
        # An option is touched at least as often as it finishes ITM.
        s, k, t, r, sigma = 100.0, 90.0, 45 / 365, 0.04, 0.35
        assert prob_touch(s, k, t, r, sigma) >= prob_itm("put", s, k, t, r, sigma)

    def test_at_barrier_is_certain(self) -> None:
        assert prob_touch(100.0, 100.0, 30 / 365, 0.05, 0.3) == 1.0

    def test_zero_drift_reflection_identity(self) -> None:
        # With nu = r - q - sigma^2/2 = 0, P(touch) = 2 * N(-|b| / (sigma sqrt(T))).
        sigma, t = 0.30, 60 / 365
        rate = 0.5 * sigma**2  # q=0 -> nu = 0
        s, barrier = 100.0, 110.0
        b = math.log(barrier / s)
        expected = 2 * norm_cdf(-abs(b) / (sigma * math.sqrt(t)))
        assert prob_touch(s, barrier, t, rate, sigma) == pytest.approx(
            expected, abs=1e-10
        )

    def test_farther_barrier_less_likely(self) -> None:
        s, t, r, sigma = 100.0, 30 / 365, 0.05, 0.30
        near = prob_touch(s, 95.0, t, r, sigma)
        far = prob_touch(s, 80.0, t, r, sigma)
        assert near > far

    def test_expired_zero_unless_at_barrier(self) -> None:
        assert prob_touch(100.0, 90.0, 0.0, 0.05, 0.3) == 0.0

    def test_invalid_inputs_raise(self) -> None:
        with pytest.raises(ValueError):
            prob_touch(-1.0, 90.0, 0.1, 0.05, 0.3)


class TestEarlyAssignment:
    def test_otm_is_low(self) -> None:
        level, _ = early_assignment_risk("put", 100.0, 95.0, 1.50)
        assert level == "LOW"

    def test_itm_call_before_dividend_is_high(self) -> None:
        # ITM call, mid 5.10 vs intrinsic 5.00 -> extrinsic 0.10 < dividend 0.50.
        level, reason = early_assignment_risk("call", 105.0, 100.0, 5.10, 0.50)
        assert level == "HIGH"
        assert "dividend" in reason

    def test_deep_itm_no_extrinsic_is_high(self) -> None:
        level, _ = early_assignment_risk("put", 80.0, 100.0, 20.01)
        assert level == "HIGH"

    def test_itm_with_plenty_extrinsic_is_low(self) -> None:
        level, _ = early_assignment_risk("put", 98.0, 100.0, 3.50)
        assert level == "LOW"

    def test_thin_extrinsic_is_moderate(self) -> None:
        level, _ = early_assignment_risk("put", 95.0, 100.0, 5.10)
        assert level == "MODERATE"
