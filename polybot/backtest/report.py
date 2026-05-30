"""
backtest/report.py — PHASE 4: metrics + reporting.

Reuses analyze.py for all metrics (one implementation), adds a backtest header
(config snapshot, git hash, and the LOUD orderbook/pricing caveats), and renders
an HTML report with hand-rolled inline-SVG charts (equity, drawdown, rolling win
rate, P&L distribution) — no matplotlib.

Required statements, surfaced prominently:
  * win rate with 95% Wilson CI
  * whether the win rate is significantly above 50% (p<0.05)
  * whether the CI lower bound clears the break-even win rate (avg token price)
  * that the orderbook signal is SYNTHETIC, so live results may differ materially
"""
from __future__ import annotations

import html
import os

from analyze import analyze, print_report


# --------------------------------------------------------------------------- #
# Caveats
# --------------------------------------------------------------------------- #
def orderbook_caveat(bt_cfg) -> str:
    mode = bt_cfg.orderbook_mode
    if mode == "noise":
        return ("Orderbook signal is PURE NOISE (no real information). The live "
                "25%-weight CLOB edge is ABSENT here — live results may differ materially.")
    if mode == "momentum":
        return ("Orderbook signal is a MOMENTUM PROXY (circular) — it re-expresses "
                "price momentum the other indicators already see, and FLATTERS results.")
    if mode == "edge":
        return (f"Orderbook LEAKS the realized outcome (edge={bt_cfg.orderbook_edge}). "
                "This is a deliberate LOOK-AHEAD STRESS TEST, not a result.")
    return "Orderbook signal is synthetic."


def pricing_caveat(bt_cfg) -> str:
    return (f"Token prices are MODELED, not observed (mispricing={bt_cfg.mispricing}, "
            f"spread={bt_cfg.spread}, slippage={bt_cfg.slippage}). Any edge beyond "
            f"costs comes from these assumptions, not from real Polymarket prices.")


# --------------------------------------------------------------------------- #
# Terminal
# --------------------------------------------------------------------------- #
def print_backtest_report(db_path: str, res=None) -> dict:
    start = res.starting_bankroll if res else 100.0
    r = analyze(db_path, starting_bankroll=start)
    print_report(r)
    if r.get("trades", 0) == 0:
        return r
    if res is not None and res.meta.get("data_source") == "synthetic":
        print("  " + "!" * 60)
        print("  !! SYNTHETIC DATA — these numbers validate plumbing ONLY.")
        print("  !! They are NOT an edge estimate: synthetic momentum is learnable")
        print("  !! in a way real markets are not. Run on real klines for a verdict.")
        print("  " + "!" * 60)
    if res is not None and res.meta.get("halted_at"):
        import config as _cfg
        dd = res.cfg_overrides.get("MAX_DRAWDOWN", _cfg.MAX_DRAWDOWN)
        print(f"  >> LIVE DRAWDOWN HALT would have STOPPED trading at day "
              f"{res.meta['halt_day']:.1f} ({dd*100:.0f}% drawdown). Metrics above "
              f"cover only the traded span.")
    print("  >> VALIDITY CAVEATS (read before trusting any number above) <<")
    if res is not None:
        print("   * " + orderbook_caveat(res.bt_cfg))
        print("   * " + pricing_caveat(res.bt_cfg))
        print(f"   * git={res.meta['git_hash']}  seed={res.bt_cfg.seed}  "
              f"orderbook_mode={res.bt_cfg.orderbook_mode}")
    if r["significantly_above_50"]:
        sig = "significantly ABOVE 50%"
    elif r["significant_vs_50"] and r["win_rate"] < 0.5:
        sig = "significantly BELOW 50% (worse than a coin flip)"
    else:
        sig = "NOT distinguishable from 50%"
    be = "clears" if r["above_breakeven"] else "does NOT clear"
    print(f"   * Win rate is {sig} (p={r['win_rate_pvalue_vs_50']:.3f}); "
          f"95% CI {be} the {r['breakeven_winrate']*100:.1f}% break-even price.")
    print("=" * 64)
    return r


# --------------------------------------------------------------------------- #
# SVG helpers
# --------------------------------------------------------------------------- #
def _polyline(series, width=520, height=160, pad=6, color="#2563eb"):
    if len(series) < 2:
        return ""
    lo, hi = min(series), max(series)
    rng = (hi - lo) or 1.0
    n = len(series)
    pts = []
    for i, v in enumerate(series):
        x = pad + (width - 2 * pad) * (i / (n - 1))
        y = height - pad - (height - 2 * pad) * ((v - lo) / rng)
        pts.append(f"{x:.1f},{y:.1f}")
    return f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{" ".join(pts)}"/>'


def _hline(value, series, width, height, pad=6, color="#888", dash="4"):
    lo, hi = min(series), max(series)
    rng = (hi - lo) or 1.0
    y = height - pad - (height - 2 * pad) * ((value - lo) / rng)
    return (f'<line x1="{pad}" y1="{y:.1f}" x2="{width-pad}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-dasharray="{dash}" stroke-width="1"/>')


def _chart(title, inner, width=520, height=160):
    return (f'<div class="card"><h3>{html.escape(title)}</h3>'
            f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}">'
            f'<rect width="{width}" height="{height}" fill="#fbfbfd"/>{inner}</svg></div>')


def _histogram(pnls, width=520, height=160, pad=6, bins=21):
    if not pnls:
        return ""
    lo, hi = min(pnls), max(pnls)
    if lo == hi:
        hi = lo + 1
    bw = (hi - lo) / bins
    counts = [0] * bins
    for p in pnls:
        k = min(bins - 1, int((p - lo) / bw))
        counts[k] += 1
    cmax = max(counts) or 1
    rects = []
    for i, c in enumerate(counts):
        x = pad + (width - 2 * pad) * (i / bins)
        bh = (height - 2 * pad) * (c / cmax)
        y = height - pad - bh
        col = "#16a34a" if (lo + (i + 0.5) * bw) >= 0 else "#dc2626"
        rects.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{(width-2*pad)/bins-1:.1f}" '
                     f'height="{bh:.1f}" fill="{col}" opacity="0.8"/>')
    zero = _hline(0, [lo, hi], width, height, pad, color="#000", dash="2") if lo < 0 < hi else ""
    return "".join(rects) + zero


def _rolling_winrate(wins, w=None):
    n = len(wins)
    if n == 0:
        return []
    w = w or max(20, n // 20)
    out = []
    for i in range(n):
        a = max(0, i - w + 1)
        seg = wins[a:i + 1]
        out.append(sum(seg) / len(seg))
    return out


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #
def _metric_rows(r) -> str:
    lo, hi = r["win_rate_ci95"]
    pf = "∞" if r["profit_factor"] == float("inf") else f"{r['profit_factor']:.2f}"
    cagr = "∞" if r["cagr"] == float("inf") else f"{r['cagr']*100:.1f}%"
    rows = [
        ("Trades", f"{r['trades']}"),
        ("Span (days)", f"{r['span_days']:.1f}"),
        ("Win rate", f"{r['win_rate']*100:.1f}%  (95% CI {lo*100:.1f}–{hi*100:.1f}%)"),
        ("Break-even win rate", f"{r['breakeven_winrate']*100:.1f}% (avg FAV price)"),
        ("Sig. above 50%?", ("YES" if r['significant_vs_50'] else "NO") +
            f"  (p={r['win_rate_pvalue_vs_50']:.3f})"),
        ("CI clears break-even?", "YES" if r['above_breakeven'] else "NO"),
        ("Start → Final", f"${r['starting_bankroll']:.2f} → ${r['final_bankroll']:.2f}"),
        ("Total P&L / ROI", f"${r['total_pnl']:.2f}  ({r['roi']*100:.1f}%)"),
        ("CAGR", cagr),
        ("Profit factor", pf),
        ("Avg win / loss", f"${r['avg_win']:.2f} / ${r['avg_loss']:.2f}"),
        ("Expectancy/trade", f"${r['expectancy']:.3f}"),
        ("Sharpe / Sortino", f"{r['sharpe']:.2f} / {r['sortino']:.2f}"),
        ("Max drawdown", f"{r['max_drawdown']*100:.1f}%"),
        ("Longest losing streak", f"{r['longest_losing_streak']}"),
    ]
    return "".join(
        f'<tr><td>{html.escape(k)}</td><td><b>{html.escape(v)}</b></td></tr>' for k, v in rows
    )


def build_report(db_path: str, res=None, html_path: str = "reports/backtest.html") -> dict:
    """Print the terminal report and write the HTML report. Returns the metrics."""
    r = print_backtest_report(db_path, res)
    if r.get("trades", 0) == 0:
        return r

    equity = r["_equity"]
    peaks, dd = [], []
    pk = equity[0]
    for v in equity:
        pk = max(pk, v)
        dd.append(-100.0 * (pk - v) / pk if pk > 0 else 0.0)
    roll = [x * 100 for x in _rolling_winrate(r["_wins"])]

    import math as _m
    eq_ratio = (max(equity) / min(equity)) if min(equity) > 0 else 1.0
    if eq_ratio > 20:  # orders-of-magnitude swing -> log scale for readability
        eq_plot = [_m.log10(max(v, 1e-9)) for v in equity]
        eq_base = _m.log10(max(r["starting_bankroll"], 1e-9))
        eq_title = "Equity ($, log scale)"
    else:
        eq_plot, eq_base, eq_title = equity, r["starting_bankroll"], "Equity ($)"

    charts = (
        _chart(eq_title, _polyline(eq_plot, color="#2563eb") +
               _hline(eq_base, eq_plot, 520, 160, color="#999")) +
        _chart("Drawdown (%)", _polyline(dd, color="#dc2626")) +
        _chart("Rolling win rate (%)", _polyline(roll, color="#16a34a") +
               _hline(50, roll, 520, 160, color="#999") +
               (_hline(r["breakeven_winrate"] * 100, roll, 520, 160, color="#f59e0b")
                if min(roll) <= r["breakeven_winrate"] * 100 <= max(roll) else "")) +
        _chart("P&L distribution ($)", _histogram(r["_pnls"]))
    )

    ob_cav = orderbook_caveat(res.bt_cfg) if res else "Orderbook signal is synthetic."
    pr_cav = pricing_caveat(res.bt_cfg) if res else "Token prices are modeled."
    meta = res.meta if res else {}
    cfg_json = ""
    if res:
        import json
        cfg_json = html.escape(json.dumps(
            {"backtest": res.bt_cfg.snapshot(), "overrides": res.cfg_overrides,
             "meta": res.meta}, indent=2))

    is_synth = (meta.get("data_source") == "synthetic")
    stats_ok = r["significantly_above_50"] and r["above_breakeven"]
    verdict_ok = stats_ok and not is_synth
    if is_synth:
        verdict = ("SYNTHETIC DATA — plumbing validation only. NO real edge can be "
                   "concluded; synthetic momentum is learnable in a way real markets "
                   "are not. Re-run on real BTC klines to estimate edge.")
    elif stats_ok:
        verdict = ("Win rate is significantly above 50% AND its 95% CI clears the "
                   "break-even price.")
    else:
        verdict = ("Win rate is NOT both significantly above 50% and clear of "
                   "break-even — treat as no demonstrated edge.")

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>polybot backtest</title><style>
body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f3f4f6;color:#111}}
.wrap{{max-width:1120px;margin:0 auto;padding:24px}}
h1{{margin:0 0 4px}} .sub{{color:#666;margin-bottom:16px}}
.banner{{background:#7f1d1d;color:#fff;padding:12px 16px;border-radius:8px;margin:12px 0;font-weight:600}}
.banner.amber{{background:#92400e}} .banner.ok{{background:#065f46}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px}}
.card h3{{margin:0 0 6px;font-size:13px;color:#374151}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden}}
td{{padding:6px 10px;border-bottom:1px solid #f0f0f0}} td:first-child{{color:#555}}
pre{{background:#0b1020;color:#cbd5e1;padding:12px;border-radius:8px;overflow:auto;font-size:12px}}
</style></head><body><div class="wrap">
<h1>polybot — BTC 5m backtest</h1>
<div class="sub">git {html.escape(str(meta.get('git_hash','?')))} ·
 {meta.get('trades','?')} trades · {meta.get('windows','?')} windows ·
 {meta.get('decisions_checked','?')} no-look-ahead checks passed</div>

<div class="banner {'ok' if verdict_ok else ''}">VERDICT: {html.escape(verdict)}</div>
<div class="banner">⚠ {html.escape(ob_cav)}</div>
<div class="banner amber">⚠ {html.escape(pr_cav)}</div>

<div class="grid"><div><table>{_metric_rows(r)}</table></div>
<div class="grid" style="grid-template-columns:1fr">{charts}</div></div>

<h3 style="margin-top:20px">Run configuration (reproducibility)</h3>
<pre>{cfg_json}</pre>
</div></body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
    with open(html_path, "w") as f:
        f.write(doc)
    print(f"  HTML report -> {html_path}")
    return r


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Render a report from a backtest DB")
    ap.add_argument("--db", default="backtest_trades.db")
    ap.add_argument("--html", default="reports/backtest.html")
    ap.add_argument("--start", type=float, default=100.0)
    args = ap.parse_args()
    build_report(args.db, res=None, html_path=args.html)


if __name__ == "__main__":
    main()
