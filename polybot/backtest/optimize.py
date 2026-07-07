"""
backtest/optimize.py — PHASE 6: parameter sweep, walk-forward evaluated.

Searches SIGNAL_THRESHOLD, KELLY_FRACTION, HEDGE_FRACTION, and the orderbook WEIGHT
(a stand-in for sweeping WEIGHTS). CRUCIALLY, every candidate is scored by
walk-forward OUT-OF-SAMPLE performance — never a single in-sample split — and the
ranked table flags sets that look great in-sample but fall apart out-of-sample
(the overfit trap).

  python -m backtest.optimize --days 120 --synthetic
  python -m backtest.optimize --days 180 --random 20          # random search
"""
from __future__ import annotations

import argparse
import itertools
import random

import config
from backtest.data import synthetic_candles, get_candles
from backtest.pricing import BacktestConfig
from backtest.walkforward import walk_forward

# Default grid (kept small; each candidate costs a full walk-forward). Use --random
# for broader, cheaper coverage of the space below.
GRID = {
    "SIGNAL_THRESHOLD": [0.10, 0.15, 0.20],
    "KELLY_FRACTION": [0.15, 0.25],
}
RANDOM_SPACE = {
    "SIGNAL_THRESHOLD": [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25],
    "KELLY_FRACTION": [0.10, 0.15, 0.20, 0.25],
    "HEDGE_FRACTION": [0.25, 0.35, 0.45],
    "OB_WEIGHT": [0.10, 0.18, 0.25, 0.35],  # orderbook_imbal weight (rest renormalized)
}


def make_weights(ob_weight: float) -> dict:
    """WEIGHTS with orderbook_imbal set to ob_weight, the other 6 renormalized."""
    base = dict(config.WEIGHTS)
    others = {k: v for k, v in base.items() if k != "orderbook_imbal"}
    s = sum(others.values())
    factor = (1.0 - ob_weight) / s if s > 0 else 0.0
    out = {k: v * factor for k, v in others.items()}
    out["orderbook_imbal"] = ob_weight
    return out


def to_overrides(cand: dict) -> dict:
    """Turn a candidate (possibly incl. OB_WEIGHT) into cfg_overrides for the engine."""
    ov = {k: v for k, v in cand.items() if k != "OB_WEIGHT"}
    if "OB_WEIGHT" in cand:
        ov["WEIGHTS"] = make_weights(cand["OB_WEIGHT"])
    return ov


def candidates(args) -> list[dict]:
    if args.random:
        rng = random.Random(config.RANDOM_SEED)
        seen, out = set(), []
        while len(out) < args.random and len(seen) < 10000:
            cand = {k: rng.choice(v) for k, v in RANDOM_SPACE.items()}
            key = tuple(sorted(cand.items()))
            if key not in seen:
                seen.add(key); out.append(cand)
        return out
    keys = list(GRID)
    return [dict(zip(keys, vals)) for vals in itertools.product(*(GRID[k] for k in keys))]


def _load(args):
    if args.synthetic:
        return synthetic_candles(days=args.days)
    try:
        return get_candles(days=args.days)
    except RuntimeError as e:
        print(f"\n  ✗ {e}\n  Sandbox blocks exchanges — use --synthetic for a demo.\n")
        raise SystemExit(2)


def label(cand: dict) -> str:
    short = {"SIGNAL_THRESHOLD": "thr", "KELLY_FRACTION": "kel",
             "HEDGE_FRACTION": "hdg", "OB_WEIGHT": "obw"}
    return " ".join(f"{short.get(k,k)}={v}" for k, v in cand.items())


def main():
    ap = argparse.ArgumentParser(description="Phase 6 — walk-forward parameter sweep")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--random", type=int, default=0, help="random-search N candidates")
    ap.add_argument("--train", type=int, default=30)
    ap.add_argument("--test", type=int, default=7)
    ap.add_argument("--step", type=int, default=7)
    ap.add_argument("--mispricing", type=float, default=BacktestConfig.mispricing)
    args = ap.parse_args()

    candles = _load(args)
    bt = BacktestConfig(mispricing=args.mispricing)
    cands = candidates(args)
    print(f"Evaluating {len(cands)} candidates via walk-forward "
          f"({args.train}d/{args.test}d/{args.step}d) on {args.days}d "
          f"{'synthetic' if args.synthetic else 'real'} data…\n")

    results = []
    for c in cands:
        ov = to_overrides(c)
        folds, is_agg, oos_agg = walk_forward(
            candles, bt, args.train, args.test, args.step, grid=None, fixed_params=ov)
        gap = is_agg["expectancy"] - oos_agg["expectancy"]
        results.append((c, is_agg, oos_agg, gap))

    # rank by OUT-OF-SAMPLE expectancy — the only number that counts
    results.sort(key=lambda r: r[2]["expectancy"], reverse=True)

    print("=" * 86)
    print(f" {'rank':>4} | {'parameters':>30} | {'IS exp':>7} | {'OOS exp':>7} "
          f"{'OOS win':>7} {'OOSn':>5} | {'overfit?':>8}")
    print("-" * 86)
    for i, (c, is_a, oos_a, gap) in enumerate(results, 1):
        overfit = "OVERFIT" if gap > abs(oos_a["expectancy"]) + 0.05 else ""
        print(f" {i:>4} | {label(c):>30} | {is_a['expectancy']:>7.3f} | "
              f"{oos_a['expectancy']:>7.3f} {oos_a['win_rate']*100:>6.1f}% "
              f"{oos_a['trades']:>5} | {overfit:>8}")
    print("=" * 86)
    best = results[0]
    print(f" BEST OUT-OF-SAMPLE: {label(best[0])}  ->  OOS expectancy "
          f"${best[2]['expectancy']:.3f}/trade, win {best[2]['win_rate']*100:.1f}%")
    print(" Rank is by OOS only. 'OVERFIT' = strong in-sample, weak out-of-sample —")
    print(" do NOT deploy those. Synthetic data can't prove edge; run on real klines.")


if __name__ == "__main__":
    main()
