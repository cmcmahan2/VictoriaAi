"""
analyze.py — post-hoc performance analyzer.

Runs on any database written with logger.py's schema, live or backtest:
    python analyze.py --db backtest_trades.db
    python analyze.py --db trades.db

Also exposes pure-stdlib stat helpers (Wilson interval, normal CDF, Sharpe,
Sortino, drawdown, streaks, significance test) that backtest/report.py reuses, so
there is one implementation of each metric.
"""
from __future__ import annotations

import argparse
import math
import sqlite3
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Stat primitives (stdlib only)
# --------------------------------------------------------------------------- #
Z95 = 1.959963984540054  # two-sided 95%


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def wilson_interval(wins: int, n: int, z: float = Z95) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion. Honest on small n."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def winrate_pvalue(wins: int, n: int, p0: float = 0.5) -> float:
    """Two-sided p-value that the win rate differs from p0 (normal approx)."""
    if n == 0:
        return 1.0
    se = math.sqrt(p0 * (1 - p0) / n)
    if se == 0:
        return 1.0
    z = (wins / n - p0) / se
    return 2.0 * (1.0 - norm_cdf(abs(z)))


def sharpe(returns: list[float], periods_per_year: float) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    return (mean / sd) * math.sqrt(periods_per_year)


def sortino(returns: list[float], periods_per_year: float) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("inf")
    dd = math.sqrt(sum(r * r for r in downside) / len(downside))
    if dd == 0:
        return 0.0
    return (mean / dd) * math.sqrt(periods_per_year)


def max_drawdown(equity: list[float]) -> float:
    """Largest peak-to-trough fractional drop along an equity curve."""
    peak = equity[0] if equity else 0.0
    worst = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return worst


def longest_losing_streak(wins: list[int]) -> int:
    cur = best = 0
    for w in wins:
        cur = 0 if w else cur + 1
        best = max(best, cur)
    return best


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
@dataclass
class Trade:
    ts: int
    hour: int
    confidence: float
    fav_price: float
    fav_stake: float
    fav_won: int
    pnl: float
    bankroll_before: float | None
    bankroll_after: float | None


def load_trades(db_path: str) -> list[Trade]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT ts, hour, confidence, fav_price, fav_stake, fav_won, pnl, "
        "bankroll_before, bankroll_after FROM trades ORDER BY ts"
    ).fetchall()
    conn.close()
    return [Trade(**dict(r)) for r in rows]


def analyze(db_path: str, starting_bankroll: float = 100.0) -> dict:
    trades = load_trades(db_path)
    n = len(trades)
    if n == 0:
        return {"trades": 0}

    wins = [t.fav_won for t in trades]
    nwins = sum(wins)
    pnls = [t.pnl for t in trades]
    total_pnl = sum(pnls)

    # equity curve (cumulative pnl from a fixed start)
    equity, bal = [], starting_bankroll
    for p in pnls:
        bal += p
        equity.append(bal)
    final = equity[-1]

    gains = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    profit_factor = (sum(gains) / abs(sum(losses))) if losses else float("inf")
    avg_win = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    expectancy = total_pnl / n

    # per-trade fractional returns for risk-adjusted metrics
    rets = []
    for t in trades:
        base = t.bankroll_before if t.bankroll_before else starting_bankroll
        rets.append(t.pnl / base if base else 0.0)

    span_days = max((trades[-1].ts - trades[0].ts) / 86400.0, 1e-9)
    trades_per_year = n / (span_days / 365.0)
    years = span_days / 365.0
    # CAGR annualizes the total return; guard the overflow that arises when a huge
    # return is annualized over a tiny span (e.g. a sub-day synthetic smoke test).
    try:
        cagr = ((final / starting_bankroll) ** (1 / years) - 1) if years > 0 and final > 0 else 0.0
    except OverflowError:
        cagr = float("inf")

    lo, hi = wilson_interval(nwins, n)
    pval = winrate_pvalue(nwins, n)
    avg_fav_price = sum(t.fav_price for t in trades) / n
    # break-even win rate: paying avg_fav_price for a $1 token, ignoring hedge,
    # you need to win at least avg_fav_price of the time just to break even.
    breakeven_wr = avg_fav_price

    # per-hour and per-confidence-bucket breakdowns
    by_hour: dict[int, list[Trade]] = {}
    for t in trades:
        by_hour.setdefault(t.hour, []).append(t)
    buckets = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
    by_bucket: dict[str, list[Trade]] = {f"{a:.1f}-{b:.1f}": [] for a, b in buckets}
    for t in trades:
        for a, b in buckets:
            if a <= t.confidence < b:
                by_bucket[f"{a:.1f}-{b:.1f}"].append(t)
                break

    def grp(ts: list[Trade]) -> dict:
        if not ts:
            return {"n": 0, "winrate": 0.0, "pnl": 0.0}
        w = sum(x.fav_won for x in ts)
        return {"n": len(ts), "winrate": w / len(ts), "pnl": sum(x.pnl for x in ts)}

    return {
        "trades": n,
        "wins": nwins,
        "win_rate": nwins / n,
        "win_rate_ci95": (lo, hi),
        "win_rate_pvalue_vs_50": pval,
        "significant_vs_50": pval < 0.05,
        "breakeven_winrate": breakeven_wr,
        "above_breakeven": (lo > breakeven_wr),
        "total_pnl": total_pnl,
        "final_bankroll": final,
        "starting_bankroll": starting_bankroll,
        "roi": (final - starting_bankroll) / starting_bankroll,
        "cagr": cagr,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "sharpe": sharpe(rets, trades_per_year),
        "sortino": sortino(rets, trades_per_year),
        "max_drawdown": max_drawdown(equity),
        "longest_losing_streak": longest_losing_streak(wins),
        "avg_fav_price": avg_fav_price,
        "span_days": span_days,
        "by_hour": {h: grp(v) for h, v in sorted(by_hour.items())},
        "by_confidence": {k: grp(v) for k, v in by_bucket.items()},
        "_equity": equity,
        "_wins": wins,
        "_pnls": pnls,
    }


def _fmt_pct(x: float) -> str:
    return f"{x*100:.1f}%"


def print_report(r: dict) -> None:
    if r.get("trades", 0) == 0:
        print("No trades in database.")
        return
    lo, hi = r["win_rate_ci95"]
    sig = "YES" if r["significant_vs_50"] else "NO  <-- NOT distinguishable from a coin flip"
    abv = "YES" if r["above_breakeven"] else "NO  <-- CI lower bound is below break-even"
    print("=" * 64)
    print(" PERFORMANCE REPORT")
    print("=" * 64)
    print(f" Trades                 {r['trades']}")
    print(f" Span                   {r['span_days']:.1f} days")
    print(f" Win rate               {_fmt_pct(r['win_rate'])}  "
          f"(95% CI {_fmt_pct(lo)}–{_fmt_pct(hi)})")
    print(f" Break-even win rate    {_fmt_pct(r['breakeven_winrate'])}  "
          f"(avg FAV price)")
    print(f" Sig. above 50%?        {sig}  (p={r['win_rate_pvalue_vs_50']:.3f})")
    print(f" CI clears break-even?  {abv}")
    print("-" * 64)
    print(f" Start / Final          ${r['starting_bankroll']:.2f} -> ${r['final_bankroll']:.2f}")
    print(f" Total P&L              ${r['total_pnl']:.2f}   ROI {_fmt_pct(r['roi'])}")
    print(f" CAGR                   {_fmt_pct(r['cagr'])}")
    print(f" Profit factor          {r['profit_factor']:.2f}")
    print(f" Avg win / Avg loss     ${r['avg_win']:.2f} / ${r['avg_loss']:.2f}")
    print(f" Expectancy / trade     ${r['expectancy']:.3f}")
    print(f" Sharpe / Sortino       {r['sharpe']:.2f} / {r['sortino']:.2f}  (annualized)")
    print(f" Max drawdown           {_fmt_pct(r['max_drawdown'])}")
    print(f" Longest losing streak  {r['longest_losing_streak']}")
    print("-" * 64)
    print(" By confidence bucket:")
    for k, g in r["by_confidence"].items():
        if g["n"]:
            print(f"   {k}   n={g['n']:<5} win={_fmt_pct(g['winrate']):<7} pnl=${g['pnl']:.2f}")
    print(" By UTC hour (top movers):")
    hours = sorted(r["by_hour"].items(), key=lambda kv: kv[1]["pnl"], reverse=True)
    for h, g in hours[:6]:
        if g["n"]:
            print(f"   {h:02d}:00  n={g['n']:<5} win={_fmt_pct(g['winrate']):<7} pnl=${g['pnl']:.2f}")
    print("=" * 64)


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze a polybot trade database.")
    ap.add_argument("--db", default="trades.db", help="path to SQLite trade DB")
    ap.add_argument("--start", type=float, default=100.0, help="starting bankroll")
    args = ap.parse_args()
    print_report(analyze(args.db, args.start))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:  # e.g. piped into `head`; exit quietly
        import os
        import sys
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
