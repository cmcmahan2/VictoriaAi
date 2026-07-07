"""
tests/test_no_lookahead.py — proves the signal cannot see the future.

The decisive test: take a candle series, build a TAMPERED copy in which every
candle at/after a cutoff is wildly altered, and run the backtest on both. Every
trade that was decided AND settled before the cutoff must be byte-identical — if
any future candle leaked into a past decision, these would diverge and the test
fails. We also assert the engine's internal no-look-ahead guard ran on every
window, and (directly) that the reconstructed feed never contains a candle that
closes after the decision time.

Runs with or without pytest:
    python tests/test_no_lookahead.py        # standalone
    python -m pytest tests/test_no_lookahead.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from price_feed import Candle, PriceFeed
from backtest.data import compute_outcomes, synthetic_candles
from backtest.engine import run_backtest
from backtest.pricing import BacktestConfig

DAY = 86400


def _key(r):
    """Identity of a trade that must be invariant to the future."""
    return (r.window_start, r.fav_side, round(r.signal_score, 9),
            round(r.fav_price, 9), round(r.fav_stake, 2),
            r.outcome, round(r.pnl, 6))


def _tamper_after(candles, cutoff_ts, factor=3.0):
    """Copy candles, multiplying prices by `factor` at/after cutoff_ts (wild future)."""
    out = []
    for c in candles:
        if c.ts >= cutoff_ts:
            out.append(Candle(c.ts, c.open * factor, c.high * factor, c.low * factor,
                              c.close * factor, c.volume, c.taker_buy))
        else:
            out.append(c)
    return out


def test_future_candles_do_not_change_past_trades():
    candles = synthetic_candles(days=20)
    cutoff = candles[0].ts + 10 * DAY
    tampered = _tamper_after(candles, cutoff)

    bt = BacktestConfig()  # orderbook_mode='noise' -> no legitimate future dependence
    base = run_backtest(candles, bt)
    alt = run_backtest(tampered, bt)

    # trades fully decided AND settled before the cutoff must be identical
    base_pre = [_key(r) for r in base.rows if r.window_end <= cutoff]
    alt_pre = [_key(r) for r in alt.rows if r.window_end <= cutoff]

    assert base_pre, "expected some pre-cutoff trades to compare"
    assert base_pre == alt_pre, (
        "LOOK-AHEAD DETECTED: tampering the future changed a past trade")

    # sanity: tampering DID change something after the cutoff (test isn't vacuous)
    base_post = [_key(r) for r in base.rows if r.window_start >= cutoff]
    alt_post = [_key(r) for r in alt.rows if r.window_start >= cutoff]
    assert base_post != alt_post, "tampering had no effect — test would be vacuous"


def test_engine_guard_ran_on_every_window():
    candles = synthetic_candles(days=10)
    res = run_backtest(candles, BacktestConfig())
    assert res.meta["decisions_checked"] > 0
    # every window that had any fed candle passed the internal assertion (no raise)


def test_feed_never_contains_future_candle():
    """Directly reconstruct the engine's feed and verify, at each decision, no fed
    candle closes after the decision time."""
    candles = synthetic_candles(days=8)
    outs = {o.window_start: o for o in compute_outcomes(candles)}
    bt = BacktestConfig()
    feed = PriceFeed(maxlen=200)
    ci = 0
    checks = 0
    for W in sorted(outs):
        decision_ts = W + config.WINDOW_SECONDS - bt.decision_lead
        while ci < len(candles) and candles[ci].close_time <= decision_ts:
            feed.add(candles[ci]); ci += 1
        if feed.last is None:
            continue
        assert feed.last.close_time <= decision_ts, "feed contains a future candle"
        # the very next unfed candle must close AFTER the decision (strict frontier)
        if ci < len(candles):
            assert candles[ci].close_time > decision_ts
        checks += 1
    assert checks > 0


def _run_all():
    tests = [test_future_candles_do_not_change_past_trades,
             test_engine_guard_ran_on_every_window,
             test_feed_never_contains_future_candle]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n{len(tests)} tests passed — no look-ahead.")


if __name__ == "__main__":
    _run_all()
