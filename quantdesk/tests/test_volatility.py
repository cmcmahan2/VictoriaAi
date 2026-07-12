"""Known-value and property tests for the realized-vol suite and IV stats."""

from __future__ import annotations

import math

import numpy as np
import pytest

from quantdesk.analytics.volatility import (
    TRADING_DAYS,
    close_to_close_vol,
    expected_move,
    iv_history_maturity,
    iv_percentile,
    iv_rank,
    parkinson_vol,
    realized_vol_suite,
    straddle_implied_move,
    vrp,
    yang_zhang_vol,
)


class TestCloseToClose:
    def test_alternating_series_exact(self) -> None:
        # Log returns alternate +a, -a, +a, -a with a = ln(1.05).
        # mean = 0, sample std = sqrt(4a^2 / 3) = 2a/sqrt(3).
        closes = [100.0, 105.0, 100.0, 105.0, 100.0]
        a = math.log(1.05)
        expected = 2 * a / math.sqrt(3) * math.sqrt(TRADING_DAYS)
        assert close_to_close_vol(closes, 4) == pytest.approx(expected, rel=1e-12)

    def test_constant_prices_zero_vol(self) -> None:
        assert close_to_close_vol([50.0] * 30, 20) == 0.0

    def test_recovers_gbm_sigma(self) -> None:
        rng = np.random.default_rng(42)
        sigma = 0.30
        daily = sigma / math.sqrt(TRADING_DAYS)
        returns = rng.normal(0.0, daily, 5000)
        closes = list(100.0 * np.exp(np.cumsum(returns)))
        est = close_to_close_vol(closes, 4999)
        assert est == pytest.approx(sigma, rel=0.05)

    def test_insufficient_data_raises(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            close_to_close_vol([100.0] * 20, 20)  # needs window+1


class TestParkinson:
    def test_constant_range_exact(self) -> None:
        # H/L = 1.02 every day: sigma = sqrt(ln(1.02)^2 / (4 ln 2) * 252).
        highs = [102.0] * 20
        lows = [100.0] * 20
        expected = math.sqrt(math.log(1.02) ** 2 / (4 * math.log(2)) * TRADING_DAYS)
        assert parkinson_vol(highs, lows, 20) == pytest.approx(expected, rel=1e-12)

    def test_blind_to_overnight_gaps(self) -> None:
        # All movement in gaps, zero intraday range -> Parkinson sees nothing.
        highs = [100.0, 110.0, 100.0, 110.0]
        lows = list(highs)
        assert parkinson_vol(highs, lows, 4) == 0.0

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(ValueError, match="equal length"):
            parkinson_vol([1.0, 2.0], [1.0], 2)


class TestYangZhang:
    def test_constant_prices_zero(self) -> None:
        flat = [100.0] * 30
        assert yang_zhang_vol(flat, flat, flat, flat, 20) == 0.0

    def test_captures_overnight_gaps_where_parkinson_cannot(self) -> None:
        # Price only moves overnight: O_i = C_{i-1} * (1 +/- 5%), flat intraday.
        closes = [100.0]
        opens, highs, lows = [100.0], [100.0], [100.0]
        factor = 1.05
        for i in range(1, 30):
            o = closes[-1] * (factor if i % 2 else 1 / factor)
            opens.append(o)
            highs.append(o)
            lows.append(o)
            closes.append(o)
        yz = yang_zhang_vol(opens, highs, lows, closes, 20)
        pk = parkinson_vol(highs, lows, 20)
        assert pk == 0.0
        assert yz > 0.5  # ~5% daily overnight moves = huge annualized vol

    def test_recovers_gbm_sigma_gap_free(self) -> None:
        # Continuous GBM sampled at open/close with intraday extremes:
        # YZ should land near true sigma. Range-based estimators are
        # biased low under discrete sampling (observed high/low misses
        # the true extremes), so use fine steps + a tolerance that
        # allows the residual documented bias.
        rng = np.random.default_rng(7)
        sigma = 0.25
        n = 2000
        steps_per_day = 100
        dt_step = 1.0 / (TRADING_DAYS * steps_per_day)
        opens, highs, lows, closes = [], [], [], []
        price = 100.0
        for _ in range(n):
            path = [price]
            for _ in range(steps_per_day):
                path.append(
                    path[-1]
                    * math.exp(sigma * math.sqrt(dt_step) * rng.standard_normal())
                )
            opens.append(path[0])
            highs.append(max(path))
            lows.append(min(path))
            closes.append(path[-1])
            price = path[-1]
        est = yang_zhang_vol(opens, highs, lows, closes, n - 1)
        assert est == pytest.approx(sigma, rel=0.12)


class TestSuite:
    def test_suite_keys_with_ample_data(self) -> None:
        n = 120
        rng = np.random.default_rng(1)
        closes = list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))))
        opens = closes
        highs = [c * 1.01 for c in closes]
        lows = [c * 0.99 for c in closes]
        suite = realized_vol_suite(opens, highs, lows, closes)
        assert set(suite) == {
            "cc_20d", "cc_30d", "cc_60d", "cc_90d", "parkinson_20d", "yang_zhang_20d",
        }

    def test_suite_omits_windows_without_data(self) -> None:
        closes = [100.0] * 40  # enough for 20/30d, not 60/90d
        suite = realized_vol_suite(closes, closes, closes, closes)
        assert "cc_20d" in suite and "cc_30d" in suite
        assert "cc_60d" not in suite and "cc_90d" not in suite


class TestIVStats:
    def test_iv_rank_midpoint(self) -> None:
        assert iv_rank(0.30, [0.10, 0.50]) == pytest.approx(50.0)

    def test_iv_rank_extremes_clip(self) -> None:
        assert iv_rank(0.05, [0.10, 0.50]) == 0.0
        assert iv_rank(0.60, [0.10, 0.50]) == 100.0

    def test_iv_rank_flat_history_returns_50(self) -> None:
        assert iv_rank(0.20, [0.20, 0.20, 0.20]) == 50.0

    def test_iv_rank_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            iv_rank(0.2, [])

    def test_iv_percentile(self) -> None:
        hist = [0.10, 0.20, 0.30, 0.40]
        assert iv_percentile(0.35, hist) == 75.0
        assert iv_percentile(0.05, hist) == 0.0

    def test_maturity_label(self) -> None:
        assert "12/252" in iv_history_maturity(12)
        assert "IMMATURE" in iv_history_maturity(12)
        assert "mature" in iv_history_maturity(300)
        assert "252/252" in iv_history_maturity(300)


class TestVRPAndMoves:
    def test_vrp_sign(self) -> None:
        assert vrp(0.25, 0.18) == pytest.approx(0.07)
        assert vrp(0.15, 0.20) < 0

    def test_expected_move_one_year(self) -> None:
        assert expected_move(100.0, 0.20, 365) == pytest.approx(20.0)

    def test_expected_move_30d(self) -> None:
        assert expected_move(100.0, 0.20, 30) == pytest.approx(
            100 * 0.20 * math.sqrt(30 / 365)
        )

    def test_straddle_implied_move(self) -> None:
        assert straddle_implied_move(3.0, 2.0, 100.0) == pytest.approx(0.05)

    def test_negative_days_raises(self) -> None:
        with pytest.raises(ValueError):
            expected_move(100.0, 0.2, -1)
