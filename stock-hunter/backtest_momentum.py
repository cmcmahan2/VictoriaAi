"""
backtest_momentum.py — honest cross-sectional momentum backtest (flexible harness).

Each rebalance: rank the eligible universe by momentum, buy the top-N equal-weighted,
hold `--rebalance` months, repeat. Optional liquidity gate and 200-day trend filter
(point-in-time). Compared to SPY and the equal-weight universe. Turnover is charged.

HONEST LIMITS:
  • PRICE FACTORS ONLY (no point-in-time fundamentals in free data).
  • SURVIVORSHIP BIAS — today's listed tickers only; delisted losers missing, so
    returns are OVERSTATED. Beating SPY is necessary, not sufficient.

Usage:
  python backtest_momentum.py --max 1200 --years 5 --top 25
  python backtest_momentum.py --max 1200 --years 5 --top 25 --liquidity --trend --rebalance 3
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd
import yfinance as yf

from hunt import get_universe

MPY = 12


def sample_universe(max_n: int | None) -> list[str]:
    syms = get_universe()
    if max_n and len(syms) > max_n:
        step = len(syms) / max_n
        syms = [syms[int(i * step)] for i in range(max_n)]
    return syms


def download_panels(symbols: list[str], years: int, chunk: int = 150):
    """Return (close, volume) DataFrames aligned by date."""
    period = f"{years + 2}y"
    closes, vols = {}, {}
    n = len(symbols)
    for i in range(0, n, chunk):
        batch = symbols[i:i + chunk]
        print(f"  download {i+1}-{min(i+chunk, n)}/{n}…", flush=True)
        try:
            data = yf.download(batch, period=period, interval="1d", auto_adjust=True,
                               group_by="ticker", threads=True, progress=False)
        except Exception as exc:
            print(f"    batch failed: {exc}"); continue
        for s in batch:
            try:
                c = data[s]["Close"].dropna() if len(batch) > 1 else data["Close"].dropna()
                v = data[s]["Volume"].reindex(c.index) if len(batch) > 1 else data["Volume"].reindex(c.index)
            except (KeyError, TypeError):
                continue
            if len(c) > 260:
                closes[s], vols[s] = c, v
    return pd.DataFrame(closes), pd.DataFrame(vols)


def metrics(monthly: pd.Series) -> dict:
    monthly = monthly.dropna()
    if monthly.empty:
        return {}
    eq = (1 + monthly).cumprod()
    yrs = len(monthly) / MPY
    return {
        "total": eq.iloc[-1] - 1,
        "cagr": eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0.0,
        "sharpe": (monthly.mean() / monthly.std() * np.sqrt(MPY)) if monthly.std() else 0.0,
        "maxdd": (eq / eq.cummax() - 1).min(),
        "months": len(monthly),
    }


def run(close, vol, spy, top, cost_bps, lookback=12, hold=1,
        trend=False, liquidity=False, min_price=5.0, min_dvol=5e6) -> dict:
    m = close.resample("ME").last()
    fwd = m.shift(-1) / m - 1.0
    sig = m.shift(1) / m.shift(1 + lookback) - 1.0          # lookback-mo momentum, skip latest mo
    sma200 = close.rolling(200).mean().resample("ME").last()
    dvol_m = (close * vol).rolling(21).mean().resample("ME").last()    # ~1mo avg dollar volume
    spy_m = spy.resample("ME").last().pct_change().shift(-1)

    mom_rets, ew_rets, spy_rets, idx = [], [], [], []
    prev, hold_ctr = set(), 0
    cost = cost_bps / 1e4
    for t in m.index:
        if t not in spy_m.index or pd.isna(spy_m.loc[t]):
            continue
        s = sig.loc[t].dropna()
        f = fwd.loc[t].dropna()
        elig = s.index.intersection(f.index)
        if liquidity:
            ok = (m.loc[t] > min_price) & (dvol_m.loc[t] > min_dvol)
            elig = elig.intersection(ok[ok].index)
        if trend:
            up = m.loc[t] > sma200.loc[t]
            elig = elig.intersection(up[up].index)
        if len(elig) < top * 2:
            continue
        if hold_ctr % hold == 0:                            # re-rank only on rebalance months
            picks = list(s.loc[elig].sort_values(ascending=False).head(top).index)
            turnover = len(set(picks) - prev) / top
            prev = set(picks)
        else:
            picks = [p for p in prev if p in f.index] or list(s.loc[elig].sort_values(ascending=False).head(top).index)
            turnover = 0.0
        hold_ctr += 1
        port = f.loc[picks].mean() - 2 * turnover * cost
        mom_rets.append(port)
        ew_rets.append(f.loc[elig].mean())
        spy_rets.append(spy_m.loc[t])
        idx.append(t)

    return {
        "momentum": metrics(pd.Series(mom_rets, index=idx)),
        "equal_weight": metrics(pd.Series(ew_rets, index=idx)),
        "spy": metrics(pd.Series(spy_rets, index=idx)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Cross-sectional momentum backtest")
    ap.add_argument("--max", type=int, default=1200)
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--lookback", type=int, default=12, help="momentum lookback in months")
    ap.add_argument("--rebalance", type=int, default=1, help="hold period in months")
    ap.add_argument("--trend", action="store_true", help="require price > 200-day SMA")
    ap.add_argument("--liquidity", action="store_true", help="require $5+ price and liquid $-volume")
    args = ap.parse_args()

    t0 = time.time()
    tag = (f"top{args.top} look{args.lookback} hold{args.rebalance}"
           f"{' +trend' if args.trend else ''}{' +liq' if args.liquidity else ''}")
    print(f"=== CONFIG: {tag} ===", flush=True)
    print(f"Universe (cap {args.max}, evenly sampled)…", flush=True)
    syms = sample_universe(args.max)
    print(f"  {len(syms)} tickers", flush=True)

    print("Downloading price+volume history…", flush=True)
    close, vol = download_panels(syms, args.years)
    keep = close.shape[1]
    close = close.tail(args.years * 252 + 320)
    vol = vol.reindex(close.index)
    print(f"  {keep} tickers with usable history", flush=True)

    spy = yf.download("SPY", period=f"{args.years+2}y", interval="1d",
                      auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    print("Backtesting…", flush=True)
    res = run(close, vol, spy, args.top, args.cost_bps, args.lookback, args.rebalance,
              args.trend, args.liquidity)

    print(f"\nDone in {(time.time()-t0)/60:.1f} min.  [{tag}]\n")
    print("=" * 78)
    print(f"  {'STRATEGY':<26}{'TotRet':>10}{'CAGR':>8}{'Sharpe':>8}{'MaxDD':>8}{'Months':>8}")
    print("-" * 78)
    for key, label in [("momentum", f"Momentum top-{args.top}"),
                       ("spy", "SPY (the market)"),
                       ("equal_weight", "Equal-weight universe")]:
        x = res.get(key, {})
        if not x:
            print(f"  {label:<26}{'no data':>10}"); continue
        print(f"  {label:<26}{x['total']*100:>9.0f}%{x['cagr']*100:>7.0f}%"
              f"{x['sharpe']:>8.2f}{x['maxdd']*100:>7.0f}%{x['months']:>8}")
    print("=" * 78)
    mom, sp = res.get("momentum", {}), res.get("spy", {})
    if mom and sp:
        print(f"\n  Momentum vs SPY: {(mom['cagr']-sp['cagr'])*100:+.1f}% CAGR  |  "
              f"Sharpe {mom['sharpe']:.2f} vs {sp['sharpe']:.2f}  "
              f"{'✅ BEATS' if mom['sharpe'] > sp['sharpe'] else '❌ trails'} SPY (Sharpe)")
    print("  ⚠ Survivorship-biased → real edge is smaller.")


if __name__ == "__main__":
    main()
