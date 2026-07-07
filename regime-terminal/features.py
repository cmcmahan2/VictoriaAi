"""
features.py — the 3 features the HMM trains on, plus standardization.

  returns        log(close_t / close_{t-1})        — direction/strength
  range          (high_t - low_t) / close_t         — intrabar volatility
  volume_change  log(volume_t / volume_{t-1})       — participation shift

These three separate bull / bear / crash / chop cleanly without leaking price
level. Gaussian HMMs are scale-sensitive, so we z-score each feature (fit the
scaler on TRAIN data only when walk-forward backtesting — no look-ahead).
"""
from __future__ import annotations

import math

EPS = 1e-9


FEATURE_NAMES = ("returns", "range", "volume_change", "rel_volume")


def _feature(name, bars, t, vol_window):
    p0, p1 = bars[t - 1], bars[t]
    if name == "returns":
        return math.log(max(p1.close, EPS) / max(p0.close, EPS))
    if name == "range":
        return (p1.high - p1.low) / max(p1.close, EPS)
    if name == "volume_change":          # the video's raw delta — noisy (see below)
        return math.log((p1.volume + EPS) / (p0.volume + EPS))
    if name == "rel_volume":             # volume vs trailing average
        lo = max(0, t - vol_window)
        avg = sum(b.volume for b in bars[lo:t]) / max(1, t - lo)
        return math.log((p1.volume + EPS) / (avg + EPS))
    raise ValueError(f"unknown feature {name!r}")


def hmm_features(bars, features=("returns", "range"), vol_window: int = 24):
    """Return (feats, idx) for the requested feature names; feats[i] aligns to
    bars[idx[i]], starting at bar 1. All features are causal (no look-ahead).

    Default is returns+range. We deliberately drop the video's `volume_change`:
    a first difference is ~0 within a stationary regime, so it's mostly noise and
    HALVES regime recovery in validation (98% -> 53%). `rel_volume` doesn't help
    either (the ratio cancels the regime's volume level). returns+range carry the
    signal. Both volume features remain selectable for your own experiments.
    """
    feats, idx = [], []
    for t in range(1, len(bars)):
        feats.append([_feature(f, bars, t, vol_window) for f in features])
        idx.append(t)
    return feats, idx


def fit_scaler(feats):
    """Per-feature (mean, std) over the given rows."""
    n = len(feats)
    d = len(feats[0])
    means = [sum(f[j] for f in feats) / n for j in range(d)]
    stds = []
    for j in range(d):
        var = sum((f[j] - means[j]) ** 2 for f in feats) / n
        stds.append(math.sqrt(var) or 1.0)
    return means, stds


def apply_scaler(feats, means, stds):
    return [[(f[j] - means[j]) / stds[j] for j in range(len(f))] for f in feats]


def standardize(feats):
    means, stds = fit_scaler(feats)
    return apply_scaler(feats, means, stds), (means, stds)
