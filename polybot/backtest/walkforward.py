"""
backtest/walkforward.py — PHASE 5: walk-forward, out-of-sample only.

In-sample optimization that you then report on is the cardinal sin of backtesting.
Here we roll forward: optimize parameters on each TRAIN fold, then evaluate the
chosen params on the UNTOUCHED next TEST fold. We report the concatenated
out-of-sample stream, and compare it to in-sample to quantify overfitting. A large
IS↔OOS gap means the "edge" is fake.

  python -m backtest.walkforward --days 120 --synthetic
  python -m backtest.walkforward --days 180 --train 30 --test 7 --step 7

Each fold's optimizer grids SIGNAL_THRESHOLD (cheap, high-impact). optimize.py
(Phase 6) sweeps the full param space; here the point is the train/test discipline.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import config
from analyze import sharpe, wilson_interval
from backtest.data import synthetic_candles, get_candles
from backtest.engine import run_backtest
from backtest.pricing import BacktestConfig

DAY = 86400

# Per-fold optimization grid (kept small; the discipline matters more than breadth)
DEFAULT_GRID = {"SIGNAL_THRESHOLD": [0.10, 0.15, 0.20, 0.25]}


def slice_candles(candles, start_ts, end_ts):
    return [c for c in candles if start_ts <= c.ts < end_ts]


def metrics_from_rows(rows, start_bankroll: float = config.STARTING_BANKROLL) -> dict:
    """Bankroll-independent OOS metrics from a trade stream (reuses analyze stats)."""
    n = len(rows)
    if n == 0:
        return {"trades": 0, "win_rate": 0.0, "expectancy": 0.0,
                "total_pnl": 0.0, "sharpe": 0.0, "final": start_bankroll, "ci": (0.0, 0.0)}
    wins = sum(r.fav_won for r in rows)
    pnl = sum(r.pnl for r in rows)
    rets = [r.pnl / (r.bankroll_before or start_bankroll) for r in rows]
    span = max((rows[-1].ts - rows[0].ts) / DAY, 1e-9)
    tpy = n / (span / 365.0)
    return {
        "trades": n, "win_rate": wins / n, "expectancy": pnl / n,
        "total_pnl": pnl, "sharpe": sharpe(rets, tpy),
        "final": start_bankroll + pnl, "ci": wilson_interval(wins, n),
    }


def _grid_combos(grid: dict) -> list[dict]:
    import itertools
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in itertools.product(*(grid[k] for k in keys))]


def _score(m: dict) -> float:
    """Optimizer objective on a TRAIN fold: expectancy, but require enough trades
    (thin samples overfit). Returns -inf below the trade floor."""
    if m["trades"] < 20:
        return float("-inf")
    return m["expectancy"]


def optimize_on(candles_train, bt_cfg: BacktestConfig, grid: dict):
    """Grid-search params on a TRAIN fold; return (best_params, best_train_metrics)."""
    best_params, best_metrics, best = {}, None, float("-inf")
    for combo in _grid_combos(grid):
        res = run_backtest(candles_train, bt_cfg, cfg_overrides=combo)
        m = metrics_from_rows(res.rows)
        s = _score(m)
        if s > best:
            best, best_params, best_metrics = s, combo, m
    return best_params, (best_metrics or metrics_from_rows([]))


@dataclass
class Fold:
    idx: int
    train_span: tuple
    test_span: tuple
    params: dict
    is_metrics: dict
    oos_metrics: dict


def walk_forward(candles, bt_cfg: BacktestConfig,
                 train_days=30, test_days=7, step_days=7,
                 grid: dict | None = DEFAULT_GRID,
                 fixed_params: dict | None = None):
    """Roll train→test windows. If grid is given, optimize params per train fold.
    If grid is None, use `fixed_params` unchanged on every fold — used by
    optimize.py to score a single candidate parameter set out-of-sample."""
    if not candles:
        return [], {}, {}
    t0, t1 = candles[0].ts, candles[-1].ts
    folds: list[Fold] = []
    oos_rows_all = []
    start = t0
    i = 0
    while start + (train_days + test_days) * DAY <= t1 + DAY:
        tr_s, tr_e = start, start + train_days * DAY
        te_s, te_e = tr_e, tr_e + test_days * DAY
        train = slice_candles(candles, tr_s, tr_e)
        test = slice_candles(candles, te_s, te_e)

        if grid:
            params, is_m = optimize_on(train, bt_cfg, grid)
        else:
            params = dict(fixed_params or {})
            is_m = metrics_from_rows(run_backtest(train, bt_cfg, cfg_overrides=params).rows)

        oos_res = run_backtest(test, bt_cfg, cfg_overrides=params)
        oos_m = metrics_from_rows(oos_res.rows)
        oos_rows_all.extend(oos_res.rows)

        folds.append(Fold(i, (tr_s, tr_e), (te_s, te_e), params, is_m, oos_m))
        start += step_days * DAY
        i += 1

    # aggregate: in-sample = average across folds; out-of-sample = the whole stream
    def avg(key):
        vals = [f.is_metrics[key] for f in folds if f.is_metrics["trades"]]
        return sum(vals) / len(vals) if vals else 0.0

    is_agg = {"win_rate": avg("win_rate"), "expectancy": avg("expectancy"),
              "sharpe": avg("sharpe"), "trades": sum(f.is_metrics["trades"] for f in folds)}
    oos_agg = metrics_from_rows(oos_rows_all)
    return folds, is_agg, oos_agg


def _load(args):
    if args.synthetic:
        return synthetic_candles(days=args.days)
    try:
        return get_candles(days=args.days)
    except RuntimeError as e:
        print(f"\n  ✗ {e}\n  Sandbox blocks exchanges — use --synthetic for a demo.\n")
        raise SystemExit(2)


def main():
    ap = argparse.ArgumentParser(description="Phase 5 — walk-forward validation")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--train", type=int, default=30)
    ap.add_argument("--test", type=int, default=7)
    ap.add_argument("--step", type=int, default=7)
    ap.add_argument("--mispricing", type=float, default=BacktestConfig.mispricing)
    args = ap.parse_args()

    candles = _load(args)
    bt = BacktestConfig(mispricing=args.mispricing)
    folds, is_agg, oos_agg = walk_forward(
        candles, bt, args.train, args.test, args.step, grid=DEFAULT_GRID)

    if not folds:
        print("Not enough data for one train+test fold."); return

    print("=" * 72)
    print(f" WALK-FORWARD  ({args.train}d train -> {args.test}d test, step {args.step}d, "
          f"{len(folds)} folds)")
    print("=" * 72)
    print(f" {'fold':>4} | {'best param':>22} | {'IS exp':>7} {'IS win':>6} | "
          f"{'OOS exp':>7} {'OOS win':>7} {'OOSn':>5}")
    print("-" * 72)
    for f in folds:
        p = ",".join(f"{k.split('_')[-1]}={v}" for k, v in f.params.items())
        print(f" {f.idx:>4} | {p:>22} | {f.is_metrics['expectancy']:>7.3f} "
              f"{f.is_metrics['win_rate']*100:>5.1f}% | {f.oos_metrics['expectancy']:>7.3f} "
              f"{f.oos_metrics['win_rate']*100:>6.1f}% {f.oos_metrics['trades']:>5}")
    print("-" * 72)
    lo, hi = oos_agg["ci"]
    print(f" IN-SAMPLE  (avg/fold): expectancy ${is_agg['expectancy']:.3f}  "
          f"win {is_agg['win_rate']*100:.1f}%  sharpe {is_agg['sharpe']:.2f}")
    print(f" OUT-OF-SAMPLE (stream): expectancy ${oos_agg['expectancy']:.3f}  "
          f"win {oos_agg['win_rate']*100:.1f}% (95% CI {lo*100:.1f}-{hi*100:.1f}%)  "
          f"sharpe {oos_agg['sharpe']:.2f}  n={oos_agg['trades']}")
    gap = is_agg["expectancy"] - oos_agg["expectancy"]
    print(f" OVERFIT GAP (IS-OOS expectancy): ${gap:.3f}  "
          f"{'<-- large gap: edge likely overfit/fake' if gap > abs(oos_agg['expectancy']) + 0.05 else ''}")
    print("=" * 72)
    print(" NOTE: only OUT-OF-SAMPLE numbers reflect a deployable edge. Synthetic data")
    print(" cannot prove edge — run on real klines. Orderbook is synthetic throughout.")


if __name__ == "__main__":
    main()
