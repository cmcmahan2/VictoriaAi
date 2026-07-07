"""
research_backtest.py — honest head-to-head of evidence-backed strategies.

Tests the strategies with the most published evidence in crypto trend research:
  - Buy & Hold                    (benchmark; also a LEVERAGED benchmark)
  - 200-period SMA trend filter   (Faber tactical timing — long only when above trend)
  - MA crossover 20/100           (Grayscale/academic: beat buy-hold on return AND Sharpe)
  - Time-series momentum          (Moskowitz/Rohrbach: long if trailing return > 0)
  - Donchian channel breakout     (classic Turtle trend-following: buy N-high, exit N-low)
plus an optional VOLATILITY-TARGET position-sizing overlay (proven to lift Sharpe).

Honest by construction:
  * STANDARD textbook parameters — NOT optimized on this data (no curve-fit).
  * Signal at close[t] is applied to the return t -> t+1 (no look-ahead).
  * Fees + slippage charged on turnover; funding drag while levered; liquidation modeled.
  * Scored on what matters for a LEVERAGE trader: Sharpe and max drawdown — not just raw
    return. In a historic bull nothing beats buy-hold's raw return, but you cannot safely
    leverage buy-hold through an 80% drawdown without being liquidated.

  python research_backtest.py --source github            # real BTC (works in sandbox)
  python research_backtest.py --source kucoin --lev 2    # real, on your machine
"""
from __future__ import annotations

import argparse
import math
import statistics
import time

import config
from data import load_github_btc
from live import load_recent


# --------------------------------------------------------------------------- #
# data prep
# --------------------------------------------------------------------------- #
def resample_daily(bars):
    """Aggregate hourly (or finer) Bars into daily OHLC. Trend research is done on
    daily bars — it matches the literature and avoids hourly noise / overtrading."""
    days = {}
    for b in bars:
        key = int(b.ts // 86400)
        d = days.get(key)
        if d is None:
            days[key] = [b.ts, b.open, b.high, b.low, b.close, b.volume]
        else:
            d[2] = max(d[2], b.high)
            d[3] = min(d[3], b.low)
            d[4] = b.close
            d[5] += b.volume
    out = [days[k] for k in sorted(days)]
    return out   # list of [ts, o, h, l, c, v]


def _sma(vals, p):
    out = [None] * len(vals)
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= p:
            s -= vals[i - p]
        if i >= p - 1:
            out[i] = s / p
    return out


# --------------------------------------------------------------------------- #
# strategies: each returns a list `pos[t]` in [-1, +1], causal (uses data <= t).
# pos[t] is the desired direction DECIDED at close[t], applied to return t->t+1.
# --------------------------------------------------------------------------- #
def s_buy_hold(closes, highs, lows):
    return [1.0] * len(closes)


def s_sma_filter(closes, highs, lows, period=200, allow_short=False):
    sma = _sma(closes, period)
    pos = []
    for t in range(len(closes)):
        if sma[t] is None:
            pos.append(0.0)
        elif closes[t] > sma[t]:
            pos.append(1.0)
        else:
            pos.append(-1.0 if allow_short else 0.0)
    return pos


def s_ma_cross(closes, highs, lows, fast=20, slow=100, allow_short=False):
    sf, ss = _sma(closes, fast), _sma(closes, slow)
    pos = []
    for t in range(len(closes)):
        if sf[t] is None or ss[t] is None:
            pos.append(0.0)
        elif sf[t] > ss[t]:
            pos.append(1.0)
        else:
            pos.append(-1.0 if allow_short else 0.0)
    return pos


def s_ts_momentum(closes, highs, lows, lookback=90, allow_short=True):
    pos = []
    for t in range(len(closes)):
        if t < lookback or closes[t - lookback] <= 0:
            pos.append(0.0)
            continue
        r = closes[t] / closes[t - lookback] - 1.0
        if r > 0:
            pos.append(1.0)
        else:
            pos.append(-1.0 if allow_short else 0.0)
    return pos


def s_donchian(closes, highs, lows, entry=20, exit=10, allow_short=False):
    """Turtle System-1: go long on a break above the `entry`-day high, exit on a break
    below the `exit`-day low. (Short side symmetric when allow_short.)"""
    pos = [0.0] * len(closes)
    state = 0.0
    for t in range(len(closes)):
        if t < entry:
            pos[t] = 0.0
            continue
        hi_n = max(highs[t - entry:t])      # prior `entry` bars (exclusive of t)
        lo_n = min(lows[t - entry:t])
        hi_x = max(highs[t - exit:t])
        lo_x = min(lows[t - exit:t])
        if state <= 0 and closes[t] > hi_n:
            state = 1.0
        elif state >= 0 and closes[t] < lo_n and allow_short:
            state = -1.0
        elif state > 0 and closes[t] < lo_x:
            state = 0.0
        elif state < 0 and closes[t] > hi_x:
            state = 0.0
        pos[t] = state
    return pos


# --------------------------------------------------------------------------- #
# simulation engine (leverage, vol-target, costs, funding, liquidation)
# --------------------------------------------------------------------------- #
def realized_vol(rets, t, k=30):
    if t < k:
        return None
    window = rets[t - k + 1:t + 1]
    if len(window) < 2:
        return None
    return statistics.pstdev(window)


def simulate(daily, pos, leverage=1.0, vol_target=None, lev_cap=3.0,
             ppy=365, cfg=config, funding_on=True):
    """Run a position series through the cost model. Returns metrics dict + equity curve.

    leverage   : fixed exposure multiplier if vol_target is None
    vol_target : annualized vol target (e.g. 0.60). If set, exposure is scaled so that
                 pos * (target/realized_vol), capped at lev_cap — the proven overlay.
    """
    closes = [d[4] for d in daily]
    rets = [0.0] + [closes[t] / closes[t - 1] - 1.0 for t in range(1, len(closes))]
    cost_rate = (cfg.FEE_BPS + cfg.SLIPPAGE_BPS) / 1e4
    funding_day = (cfg.FUNDING_BPS_PER_8H / 1e4 * 3.0) if funding_on else 0.0   # 3 windows/day
    tgt_per_period = (vol_target / math.sqrt(ppy)) if vol_target else None

    # effective signed exposure each day
    exposure = [0.0] * len(closes)
    for t in range(len(closes)):
        if vol_target:
            sig = realized_vol(rets, t, 30)
            lev = min(lev_cap, tgt_per_period / sig) if sig and sig > 0 else 0.0
        else:
            lev = leverage
        exposure[t] = pos[t] * lev

    eq = 1.0
    curve = [eq]
    bar_rets = []
    n_trades = 0
    liquidated = False
    in_pos_days = 0
    for t in range(1, len(closes)):
        ex = exposure[t - 1]                          # held yesterday's exposure over t-1->t
        pnl = ex * rets[t]
        fund = abs(ex) * funding_day
        growth = 1.0 + pnl - fund
        if growth <= 0:                               # liquidation
            eq = 0.0
            liquidated = True
            curve.append(eq)
            bar_rets.append(-1.0)
            break
        eq *= growth
        # rebalance cost to move to today's exposure
        turn = abs(exposure[t] - exposure[t - 1]) * cost_rate
        if turn > 0:
            n_trades += 1 if abs(exposure[t] - exposure[t - 1]) > 1e-9 else 0
        eq *= (1.0 - turn)
        curve.append(eq)
        bar_rets.append(eq / curve[-2] - 1.0 if curve[-2] else 0.0)
        if abs(ex) > 1e-9:
            in_pos_days += 1

    # metrics
    total_ret = curve[-1] - 1.0
    years = (len(closes) / ppy) or 1e-9
    cagr = (curve[-1]) ** (1 / years) - 1 if curve[-1] > 0 else -1.0
    sharpe = _sharpe(bar_rets, ppy)
    mdd = _max_dd(curve)
    return {
        "total_return": total_ret, "cagr": cagr, "sharpe": sharpe,
        "max_dd": mdd, "exposure": in_pos_days / max(len(closes) - 1, 1),
        "flips": _count_flips(pos), "liquidated": liquidated,
        "final": curve[-1],
    }, curve


def _sharpe(rets, ppy):
    if len(rets) < 2:
        return 0.0
    m = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    return (m / sd) * math.sqrt(ppy) if sd else 0.0


def _max_dd(curve):
    peak, worst = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst


def _count_flips(pos):
    flips, prev = 0, 0.0
    for p in pos:
        if abs(p - prev) > 1e-9:
            flips += 1
        prev = p
    return flips


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #
def pct(x):
    return f"{x*100:+.0f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="github",
                    choices=["github", "kucoin", "coinbase", "yfinance"])
    ap.add_argument("--ticker", default="BTC-USDT")
    ap.add_argument("--lev", type=float, default=2.0, help="fixed leverage for the comparison")
    ap.add_argument("--vol-target", type=float, default=0.60, help="annual vol target for overlay")
    args = ap.parse_args()

    print(f"Loading {args.source} BTC history…")
    t0 = time.time()
    if args.source == "github":
        bars = load_github_btc(days=100000)          # full dataset
    else:
        bars = load_recent(args.source, args.ticker, 1000)
    # scrub corrupt rows (early Bitstamp data has inf/NaN/sentinel prices like 1.7e308)
    n_raw = len(bars)
    bars = [b for b in bars
            if all(math.isfinite(x) and 0 < x < 1e7 for x in (b.open, b.high, b.low, b.close))]
    if len(bars) < n_raw:
        print(f"  scrubbed {n_raw - len(bars)} corrupt bars")
    daily = resample_daily(bars)
    closes = [d[4] for d in daily]
    highs = [d[2] for d in daily]
    lows = [d[3] for d in daily]
    start_d = time.strftime("%Y-%m-%d", time.gmtime(daily[0][0]))
    end_d = time.strftime("%Y-%m-%d", time.gmtime(daily[-1][0]))
    bh_total = closes[-1] / closes[0] - 1.0
    print(f"  {len(daily)} daily bars  {start_d} → {end_d}  "
          f"({len(daily)/365:.1f}y)   buy&hold spot: {pct(bh_total)}   "
          f"loaded in {time.time()-t0:.1f}s\n")

    L = args.lev
    # (label, position series, leverage, vol_target, funding_on)
    runs = [
        (f"Buy & Hold (1x spot)",          s_buy_hold(closes, highs, lows),                 1.0, None,            False),
        (f"Buy & Hold ({L:g}x)",           s_buy_hold(closes, highs, lows),                 L,   None,            True),
        (f"SMA-200 filter ({L:g}x)",       s_sma_filter(closes, highs, lows, 200, False),   L,   None,            True),
        (f"MA 20/100 long-flat ({L:g}x)",  s_ma_cross(closes, highs, lows, 20, 100, False), L,   None,            True),
        (f"MA 20/100 long-short ({L:g}x)", s_ma_cross(closes, highs, lows, 20, 100, True),  L,   None,            True),
        (f"TS-momentum 90d ({L:g}x)",      s_ts_momentum(closes, highs, lows, 90, True),    L,   None,            True),
        (f"Donchian 20/10 ({L:g}x)",       s_donchian(closes, highs, lows, 20, 10, False),  L,   None,            True),
        (f"MA 20/100 + VOL-TARGET",        s_ma_cross(closes, highs, lows, 20, 100, False), 1.0, args.vol_target, True),
        (f"TS-mom 90d + VOL-TARGET",       s_ts_momentum(closes, highs, lows, 90, True),    1.0, args.vol_target, True),
    ]

    W = 96
    print("=" * W)
    print(f"  {'STRATEGY':<28}{'TotRet':>10}{'CAGR':>8}{'Sharpe':>8}"
          f"{'MaxDD':>8}{'Expo':>7}{'Flips':>7}{'vs B&H':>9}")
    print("-" * W)
    rows = []
    for label, pos, lev, vt, fund in runs:
        m, _ = simulate(daily, pos, leverage=lev, vol_target=vt, funding_on=fund)
        alpha = m["total_return"] - bh_total
        liq = "  LIQUIDATED" if m["liquidated"] else ""
        rows.append((label, m, alpha, liq))
        print(f"  {label:<28}{pct(m['total_return']):>10}{pct(m['cagr']):>8}"
              f"{m['sharpe']:>8.2f}{pct(-m['max_dd']):>8}"
              f"{m['exposure']*100:>6.0f}%{m['flips']:>7}{pct(alpha):>9}{liq}")
    print("=" * W)

    # honest verdict: best by Sharpe among non-liquidated, leverage-bearing strategies
    survivors = [(l, m, a) for l, m, a, liq in rows if not m["liquidated"]]
    best = max(survivors, key=lambda r: r[1]["sharpe"])
    print(f"\n  Best risk-adjusted (Sharpe): {best[0]}  "
          f"— Sharpe {best[1]['sharpe']:.2f}, maxDD {pct(-best[1]['max_dd'])}, "
          f"alpha {pct(best[2])} vs buy & hold.")
    print("  NOTE: raw return in a historic bull favors buy-hold; for a LEVERAGE trader")
    print("  the goal is high Sharpe + shallow drawdown so leverage doesn't liquidate you.")
    print(f"  Data: {start_d}→{end_d}. Re-run on your machine with --source kucoin for")
    print("  recent data, and forward-test in paper before risking a cent.")


if __name__ == "__main__":
    main()
