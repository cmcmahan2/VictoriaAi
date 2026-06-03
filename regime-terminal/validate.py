"""
validate.py — does the strategy actually have an edge? One command, honest verdict.

Fetches BTC history, runs the WALK-FORWARD backtest (train on the past, test only on
unseen data — the honest way) with fees + slippage + funding all modeled, then prints
whether it beat buy-and-hold and held up on a risk-adjusted basis.

  # the REAL test — run on your own machine (needs network):
  python validate.py --source kucoin   --ticker BTC-USDT --days 720 --short
  python validate.py --source coinbase --ticker BTC-USD  --days 365 --short

  # machinery smoke-test only (works offline; NOT evidence of real edge):
  python validate.py --source synthetic --days 365 --short

Honest by design: walk-forward (no lookahead), costs modeled, compared to buy & hold,
and it tells you plainly if there's no edge. Synthetic data can only prove the code
runs — it cannot prove the strategy makes money. Only real price history can do that.
"""
from __future__ import annotations

import argparse
import time

import config
from backtest import run_backtest
from live import load_recent


def pct(x):
    return f"{x*100:+.1f}%"


def main():
    ap = argparse.ArgumentParser(description="Validate strategy edge via walk-forward backtest")
    ap.add_argument("--source", choices=["synthetic", "kucoin", "coinbase", "yfinance"], default="kucoin")
    ap.add_argument("--ticker", default="BTC-USDT", help="data ticker (BTC-USDT kucoin, BTC-USD coinbase/yf)")
    ap.add_argument("--days", type=int, default=720, help="history to test over")
    ap.add_argument("--states", type=int, default=7)
    ap.add_argument("--leverage", type=float, default=config.LEVERAGE)
    ap.add_argument("--short", action="store_true", help="allow shorting bear/crash regimes")
    ap.add_argument("--no-walk-forward", action="store_true", help="train once (faster, but optimistic)")
    args = ap.parse_args()

    config.N_STATES = max(2, min(args.states, 12))
    config.LEVERAGE = args.leverage
    config.HMM_N_INIT = 4

    print(f"Fetching {args.days}d of {args.ticker} from {args.source} …")
    t0 = time.time()
    bars = load_recent(args.source, args.ticker, args.days)
    print(f"  {len(bars)} bars in {time.time()-t0:.1f}s. Running walk-forward backtest "
          f"(lev {args.leverage:g}x, short={args.short}) …")

    t0 = time.time()
    res = run_backtest(bars, config, walk_forward=not args.no_walk_forward, allow_short=args.short)
    m = res.metrics
    if m.get("trades", 0) == 0:
        print("No trades taken over this window — nothing to score (try more --days or --short).")
        return

    beat_bh = m["alpha_vs_bh"] > 0
    survived = m["liquidations"] == 0
    if not survived:
        verdict = f"DANGER — liquidated {m['liquidations']}x. Leverage too high or stops missing."
    elif beat_bh and m["sharpe"] >= 1.0:
        verdict = "STRONG — beat buy & hold AND solid risk-adjusted (Sharpe >= 1), no liquidations."
    elif beat_bh:
        verdict = "PROMISING — beat buy & hold, but Sharpe is modest. Test more windows before trusting."
    else:
        verdict = "WEAK — did NOT beat buy & hold. Edge not demonstrated; don't risk real money on this yet."

    bar = "=" * 64
    rows = [
        "", bar, f"  STRATEGY VALIDATION — {args.ticker}  ({args.source})", bar,
        f"  window        : {m['span_days']:.0f} days, {res.meta['bars']} bars, "
        f"walk-forward={'no' if args.no_walk_forward else 'YES'}, {res.meta.get('folds', '?')} folds",
        f"  leverage      : {args.leverage:g}x      costs: fees+slip+funding modeled",
        "  " + "-" * 60,
        f"  strategy return : {pct(m['total_return'])}      (CAGR {pct(m['cagr'])})",
        f"  buy & hold      : {pct(m['buy_hold_return'])}",
        f"  ALPHA vs hold   : {pct(m['alpha_vs_bh'])}   <- the number that matters",
        "  " + "-" * 60,
        f"  Sharpe / Sortino: {m['sharpe']:.2f} / {m['sortino']:.2f}",
        f"  max drawdown    : {pct(-abs(m['max_drawdown']))}",
        f"  win rate        : {m['win_rate']*100:.0f}%   over {m['trades']} trades "
        f"(avg {pct(m['avg_trade_ret'])}/trade)",
        f"  time in market  : {m['exposure']*100:.0f}%      liquidations: {m['liquidations']}",
        bar,
        f"  VERDICT: {verdict}",
        bar,
    ]
    if args.source == "synthetic":
        rows += ["  NOTE: SYNTHETIC data — this only proves the pipeline runs end to end.",
                 "  It is NOT evidence of real edge. Re-run with --source kucoin/coinbase",
                 "  on a machine with network for the real answer.", bar]
    print("\n".join(rows))


if __name__ == "__main__":
    main()
