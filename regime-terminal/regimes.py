"""
regimes.py — turn raw HMM states into labeled, tradeable regimes.

The HMM finds N anonymous states. Here we:
  * auto-label each state from its TRAIN-data return/volatility signature into a
    name (bull/bear/crash/chop + a vol qualifier) and a STANCE: 'long' / 'neutral'
    / 'avoid'. (The video auto-labels the bull state as highest-return; we generalize.)
  * expose a CAUSAL regime stream (filtered posterior, only past data) for
    decisions, and a smoothed/viterbi stream for the chart overlay ONLY.

Nothing here looks ahead: labels are fixed from training data, and the live stream
uses the filtered posterior.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

import config
from features import apply_scaler, hmm_features, standardize
from hmm import GaussianHMM


@dataclass
class StateInfo:
    state: int
    mean_return: float    # per-bar, raw
    mean_vol: float       # mean range (volatility proxy), raw
    stance: str           # 'long' | 'neutral' | 'avoid'
    name: str             # human label, e.g. "bull (calm)", "crash"


class RegimeModel:
    def __init__(self, n_states=config.N_STATES, features=tuple(config.FEATURES),
                 seed=config.SEED):
        self.n_states = n_states
        self.features = tuple(features)
        self.seed = seed
        self.hmm: GaussianHMM | None = None
        self.scaler = None
        self.state_info: dict[int, StateInfo] = {}
        self._ret_pos = self.features.index("returns")
        self._rng_pos = self.features.index("range") if "range" in self.features else 0

    # ------------------------------------------------------------------ #
    def fit(self, bars):
        feats_raw, idx = hmm_features(bars, self.features)
        z, self.scaler = standardize(feats_raw)
        self.hmm = GaussianHMM(self.n_states, len(self.features), seed=self.seed,
                               max_iter=config.HMM_MAX_ITER, min_var=config.HMM_MIN_VAR,
                               self_trans_prior=config.HMM_SELF_TRANS_PRIOR
                               ).fit(z, n_init=config.HMM_N_INIT)
        self._classify(self.hmm.viterbi(z), feats_raw)
        return self

    def _classify(self, states, feats_raw):
        rets = [f[self._ret_pos] for f in feats_raw]
        ret_std = statistics.pstdev(rets) or 1.0
        eps = 0.10 * ret_std                       # min mean-return to call a regime directional
        # per-state raw stats
        stats = {}
        for k in range(self.n_states):
            members = [feats_raw[i] for i in range(len(states)) if states[i] == k]
            if not members:
                stats[k] = (0.0, 0.0, 0); continue
            mu = sum(f[self._ret_pos] for f in members) / len(members)
            vol = sum(f[self._rng_pos] for f in members) / len(members)
            stats[k] = (mu, vol, len(members))
        vols = [v for (_, v, n) in stats.values() if n] or [0.0]
        vmed = statistics.median(vols)
        for k, (mu, vol, n) in stats.items():
            if mu > eps:
                stance, base = "long", "bull"
            elif mu < -eps:
                # deep-negative + high-vol => crash; else bear
                stance = "avoid"
                base = "crash" if (mu < -3 * eps and vol > vmed) else "bear"
            else:
                stance, base = "neutral", "chop"
            qual = "volatile" if vol > 1.5 * vmed else ("calm" if vol < 0.66 * vmed else "")
            name = f"{base}" + (f" ({qual})" if qual else "")
            self.state_info[k] = StateInfo(k, mu, vol, stance, name)

    # ------------------------------------------------------------------ #
    def _post(self, bars, smooth=False):
        feats_raw, idx = hmm_features(bars, self.features)
        z = apply_scaler(feats_raw, *self.scaler)
        post = self.hmm.smooth_states(z) if smooth else self.hmm.filter_states(z)
        return post, idx

    def regime_stream(self, bars, smooth=False):
        """Per-bar (bar_index, state, prob, stance, name). smooth=True is LOOK-AHEAD
        (full-sequence) — for the chart overlay only; default filtered=causal."""
        post, idx = self._post(bars, smooth=smooth)
        out = []
        for p, i in zip(post, idx):
            k = max(range(self.n_states), key=lambda s: p[s])
            si = self.state_info.get(k)
            out.append((i, k, p[k], si.stance if si else "neutral",
                        si.name if si else f"state{k}"))
        return out

    def current(self, bars):
        """Latest causal regime read: (state, confidence, stance, name)."""
        stream = self.regime_stream(bars, smooth=False)
        _, k, prob, stance, name = stream[-1]
        return k, prob, stance, name
