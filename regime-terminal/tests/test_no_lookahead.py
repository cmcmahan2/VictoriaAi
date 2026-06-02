"""
tests/test_no_lookahead.py — prove regime decisions can't see the future.

  1. The CAUSAL filtered regime for any past bar is byte-identical when future bars
     are wildly tampered (model trained on past, scaler fit on past, filter forward
     only). This is what the backtest/terminal use for decisions.
  2. The SMOOTHED regime (forward-backward — what the popular video trades on) DOES
     change when the future is tampered: proof it's look-ahead, hence excluded from
     decisions.

Runs with or without pytest:
    python tests/test_no_lookahead.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.HMM_N_INIT = 1  # fast + deterministic for the test

from data import Bar, synthetic_ohlcv
from regimes import RegimeModel


def _tamper_future(bars, cut, factor=3.0):
    return [b if b.ts < bars[cut].ts else
            Bar(b.ts, b.open * factor, b.high * factor, b.low * factor,
                b.close * factor, b.volume) for b in bars]


def _prefix(stream, cut_ts, bars):
    cut_idx = next(i for i, b in enumerate(bars) if b.ts >= cut_ts)
    return [(i, st, round(p, 9)) for (i, k, p, st, nm) in stream if i < cut_idx]


def test_filtered_regime_is_causal():
    bars, _ = synthetic_ohlcv(days=30, seed=config.SEED, drift_scale=0.4)
    cut = len(bars) * 2 // 3
    cut_ts = bars[cut].ts
    # train the model on PAST data only (scaler + HMM params are causal)
    model = RegimeModel(n_states=4, features=("returns", "range"), seed=config.SEED).fit(bars[:cut])
    tampered = _tamper_future(bars, cut)

    base = _prefix(model.regime_stream(bars, smooth=False), cut_ts, bars)
    alt = _prefix(model.regime_stream(tampered, smooth=False), cut_ts, bars)
    assert base, "expected pre-cutoff bars"
    assert base == alt, "LOOK-AHEAD: tampering the future changed a causal past regime"


def test_smoothed_regime_is_lookahead():
    bars, _ = synthetic_ohlcv(days=30, seed=config.SEED, drift_scale=0.4)
    cut = len(bars) * 2 // 3
    cut_ts = bars[cut].ts
    model = RegimeModel(n_states=4, features=("returns", "range"), seed=config.SEED).fit(bars[:cut])
    tampered = _tamper_future(bars, cut)

    base = _prefix(model.regime_stream(bars, smooth=True), cut_ts, bars)
    alt = _prefix(model.regime_stream(tampered, smooth=True), cut_ts, bars)
    # smoothing reads the whole sequence, so tampering the future MUST move some
    # past label — that's exactly why it's unusable for trading.
    assert base != alt, "smoothed labels unexpectedly causal (test assumption broken)"


def _run_all():
    for t in [test_filtered_regime_is_causal, test_smoothed_regime_is_lookahead]:
        t(); print(f"  PASS  {t.__name__}")
    print("\n2 tests passed: causal filter is look-ahead-free; smoothing is not.")


if __name__ == "__main__":
    _run_all()
