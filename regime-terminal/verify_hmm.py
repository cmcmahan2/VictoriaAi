"""
verify_hmm.py — prove the HMM core works before layering any strategy.

The video stops at "here's a colored chart". We go further: generate hourly bars
with PLANTED regimes (known ground truth), fit the HMM blind, and measure how well
it recovers them. We also show the regime summary table and quantify how much the
smoothed (look-ahead) labels differ from the causal (tradeable) ones.

    python verify_hmm.py
"""
from __future__ import annotations

from itertools import permutations

import config
from data import PLANTED_REGIMES, synthetic_ohlcv
from features import hmm_features, standardize
from hmm import GaussianHMM


def regime_summary(states, raw_feats, n_states):
    """Per-state count + mean of each raw feature (generic over feature count)."""
    d = len(raw_feats[0])
    rows = []
    for k in range(n_states):
        members = [raw_feats[i] for i in range(len(states)) if states[i] == k]
        if not members:
            rows.append((k, 0, [0.0] * d)); continue
        m = [sum(f[j] for f in members) / len(members) for j in range(d)]
        rows.append((k, len(members), m))
    return rows


def best_label_map(pred, true_names, n_states, true_labels):
    """Brute-force assign predicted states -> planted names to maximize agreement."""
    names = sorted(set(true_names))
    if n_states != len(names):
        return None, 0.0
    best_map, best_acc = None, -1.0
    for perm in permutations(names):
        mapping = {k: perm[k] for k in range(n_states)}
        acc = sum(1 for i in range(len(pred)) if mapping[pred[i]] == true_labels[i]) / len(pred)
        if acc > best_acc:
            best_acc, best_map = acc, mapping
    return best_map, best_acc


def main():
    print("Generating synthetic hourly bars with planted regimes "
          f"({len(PLANTED_REGIMES)}: {[r[0] for r in PLANTED_REGIMES]})…")
    bars, true_labels = synthetic_ohlcv(days=150, seed=config.SEED)
    nfeat = len(config.FEATURES)
    feats_raw, idx = hmm_features(bars, features=config.FEATURES)
    true_aligned = [true_labels[i] for i in idx]
    feats_z, _ = standardize(feats_raw)
    print(f"  {len(bars)} bars -> {len(feats_z)} rows, features={config.FEATURES}\n")

    # --- matched fit: recover the planted regimes -----------------------
    K = len(PLANTED_REGIMES)
    hmm = GaussianHMM(n_states=K, n_features=nfeat, seed=config.SEED,
                      max_iter=config.HMM_MAX_ITER, min_var=config.HMM_MIN_VAR,
                      self_trans_prior=config.HMM_SELF_TRANS_PRIOR).fit(feats_z, n_init=config.HMM_N_INIT)
    print(f"HMM fit (K={K}): {hmm.n_iter_} iters, converged={hmm.converged_}, "
          f"loglik={hmm.loglik_:.1f}")

    viterbi = hmm.viterbi(feats_z)
    mapping, acc = best_label_map(viterbi, [r[0] for r in PLANTED_REGIMES], K, true_aligned)
    print(f"Regime RECOVERY vs planted ground truth: {acc*100:.1f}% agreement "
          f"(state->regime map: { {k: mapping[k] for k in mapping} })")

    hdr = " ".join(f"{('mean_'+n):>12}" for n in config.FEATURES)
    print("\nRegime summary (per state, raw feature means):")
    print(f"  {'state':>5} {'mapped':>6} {'n':>6} {hdr}")
    for k, n, means in regime_summary(viterbi, feats_raw, K):
        ms = " ".join(f"{v:>12.5f}" for v in means)
        print(f"  {k:>5} {mapping.get(k,'?'):>6} {n:>6} {ms}")

    # --- the look-ahead point: filtered (causal) vs smoothed (full-seq) --
    filt = hmm.filter_states(feats_z)
    smooth = hmm.smooth_states(feats_z)
    filt_lbl = [max(range(K), key=lambda k: p[k]) for p in filt]
    smooth_lbl = [max(range(K), key=lambda k: p[k]) for p in smooth]
    disagree = sum(1 for a, b in zip(filt_lbl, smooth_lbl) if a != b) / len(filt_lbl)
    print(f"\nCausal(filter) vs look-ahead(smooth) labels disagree on "
          f"{disagree*100:.1f}% of bars.")
    print("  -> The video trades on smoothed labels. Those use FUTURE data; only the")
    print("     causal 'filter' labels are tradeable. This gap is the look-ahead trap.")

    # --- product default: 7 regimes -------------------------------------
    print(f"\nProduct default N_STATES={config.N_STATES} characterization:")
    h7 = GaussianHMM(n_states=config.N_STATES, n_features=nfeat, seed=config.SEED,
                     max_iter=config.HMM_MAX_ITER, min_var=config.HMM_MIN_VAR,
                     self_trans_prior=config.HMM_SELF_TRANS_PRIOR).fit(feats_z, n_init=config.HMM_N_INIT)
    v7 = h7.viterbi(feats_z)
    print(f"  {'state':>5} {'n':>6} {hdr}")
    for k, n, means in regime_summary(v7, feats_raw, config.N_STATES):
        ms = " ".join(f"{v:>12.5f}" for v in means)
        print(f"  {k:>5} {n:>6} {ms}")
    print("\nCore verified. Next: auto-label regimes, layer the strategy, backtest.")


if __name__ == "__main__":
    main()
