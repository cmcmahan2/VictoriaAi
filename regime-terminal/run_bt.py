"""run_bt.py — one-shot walk-forward backtest of the HMM regime strategy.

Fetches data directly (bypasses the shared CSV cache so it won't disturb the
live dashboard), runs the honest walk-forward backtest, prints metrics.

  python run_bt.py 365          # ~1y, long-only, leverage from config
  python run_bt.py 730 short    # ~2y, allow shorting bear/crash regimes
"""
import sys
import time

import config
from backtest import run_backtest
from data import load_kucoin

days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
allow_short = "short" in sys.argv[2:]


def progress(msg, frac):
    print(f"  [{frac*100:4.0f}%] {msg}", flush=True)


print(f"Fetching {days}d of BTC-USDT (1h) from KuCoin…", flush=True)
t0 = time.time()
bars = load_kucoin("BTC-USDT", days, "1h")
print(f"  {len(bars)} bars in {time.time()-t0:.0f}s "
      f"({(bars[-1].ts - bars[0].ts)/86400:.0f} days covered)", flush=True)

print(f"Running walk-forward backtest "
      f"(leverage {config.LEVERAGE}x, short={allow_short})…", flush=True)
t1 = time.time()
res = run_backtest(bars, config, walk_forward=True, progress=progress, allow_short=allow_short)
m = res.metrics
print(f"\nDone in {(time.time()-t1)/60:.1f} min "
      f"(folds={res.meta.get('folds')}, covered bars={res.meta.get('covered')}).\n", flush=True)


def pct(x):
    return "n/a" if x is None else f"{x*100:+.1f}%"


print("================ STRATEGY BACKTEST ================")
print(f"  span               : {m.get('span_days', 0):.0f} days")
print(f"  trades             : {m.get('trades')}")
print(f"  win rate           : {pct(m.get('win_rate'))}")
print(f"  exposure (in mkt)  : {pct(m.get('exposure'))}")
print(f"  avg trade return   : {pct(m.get('avg_trade_ret'))}")
print("  --")
print(f"  STRATEGY return    : {pct(m.get('total_return'))}")
print(f"  buy & hold return  : {pct(m.get('buy_hold_return'))}")
print(f"  alpha vs buy&hold  : {pct(m.get('alpha_vs_bh'))}")
print(f"  CAGR               : {pct(m.get('cagr'))}")
print("  --")
print(f"  Sharpe             : {m.get('sharpe', 0):.2f}")
print(f"  Sortino            : {m.get('sortino', 0):.2f}")
print(f"  max drawdown       : {pct(m.get('max_drawdown'))}")
print(f"  liquidations       : {m.get('liquidations')}")
print(f"  final equity       : ${m.get('final_equity', 0):,.0f}  (from ${m.get('start_capital', 0):,.0f})")
print("==================================================")
