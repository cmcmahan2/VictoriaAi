"""
terminal.py — the "Regime Terminal": current regime + signal + walk-forward backtest.

  python terminal.py --synthetic --days 240          # sandbox demo
  python terminal.py --ticker BTC-USD --days 730     # real data (run locally)

Outputs a terminal summary AND a self-contained HTML dashboard (dark theme): the
current regime + confidence, the live signal with its confirmation breakdown, a
regime-overlay price chart, equity vs buy-and-hold, key metrics, and the trade log.

Honesty banners are always on: regimes for DECISIONS are causal/walk-forward (the
backtest never trains on the future); synthetic results are plumbing, not edge;
leverage can liquidate.
"""
from __future__ import annotations

import argparse
import html
import os
import time

import config
from backtest import run_backtest
from regimes import RegimeModel
from strategy import Indicators, confirmations


# --------------------------------------------------------------------------- #
# current causal read (train on ALL history is fine for "now" — no future exists)
# --------------------------------------------------------------------------- #
def current_read(bars, cfg, progress=None, allow_short=False):
    if progress:
        progress("Detecting current regime…", 0.90)
    saved = cfg.HMM_N_INIT                       # the "current" snapshot needs fewer
    cfg.HMM_N_INIT = min(saved, 3)               # restarts than the validated headline
    try:
        model = RegimeModel(cfg.N_STATES, tuple(cfg.FEATURES), seed=cfg.SEED).fit(bars)
    finally:
        cfg.HMM_N_INIT = saved
    state, conf, stance, name = model.current(bars)
    ind = Indicators(bars, cfg)
    t = len(bars) - 1
    cks = confirmations(ind, t)
    n_pass = sum(1 for _, ok in cks if ok)
    # live signal
    if stance == "avoid":
        if allow_short and conf >= cfg.MIN_REGIME_CONFIDENCE:
            signal = "SHORT — enter/hold (bear/crash regime)"
        else:
            signal = "FLAT — exit / avoid (bear/crash regime)"
    elif stance == "long" and conf >= cfg.MIN_REGIME_CONFIDENCE and n_pass >= cfg.CONFIRMATIONS_REQUIRED:
        signal = f"LONG — enter/hold ({n_pass}/{cfg.CONFIRMATIONS_TOTAL} confirms)"
    elif stance == "long":
        why = "low confidence" if conf < cfg.MIN_REGIME_CONFIDENCE else f"only {n_pass}/{cfg.CONFIRMATIONS_TOTAL} confirms"
        signal = f"NEUTRAL — bull regime but {why}, wait"
    else:
        signal = "NEUTRAL — chop, wait"
    return {"state": state, "confidence": conf, "stance": stance, "name": name,
            "signal": signal, "n_pass": n_pass, "checks": cks, "price": bars[-1].close}


# --------------------------------------------------------------------------- #
# SVG helpers
# --------------------------------------------------------------------------- #
def _poly(series, w, h, pad=8, color="#38bdf8", logscale=False):
    import math
    if len(series) < 2:
        return ""
    vals = [math.log10(max(v, 1e-9)) for v in series] if logscale else series
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals)
    pts = " ".join(f"{pad+(w-2*pad)*i/(n-1):.1f},{h-pad-(h-2*pad)*(v-lo)/rng:.1f}"
                   for i, v in enumerate(vals))
    return f'<polyline fill="none" stroke="{color}" stroke-width="1.4" points="{pts}"/>'


def _stance_bands(overlay, w, h, pad=8):
    """Shaded background bands by stance behind the price line."""
    if not overlay:
        return ""
    n = len(overlay)
    col = {"long": "#16653433", "avoid": "#7f1d1d33", "neutral": "#33415533"}
    out = []
    i = 0
    while i < n:
        j = i
        st = overlay[i][2]
        while j + 1 < n and overlay[j + 1][2] == st:
            j += 1
        x0 = pad + (w - 2 * pad) * i / (n - 1)
        x1 = pad + (w - 2 * pad) * j / (n - 1)
        out.append(f'<rect x="{x0:.1f}" y="0" width="{max(0.6,x1-x0):.1f}" height="{h}" '
                   f'fill="{col.get(st, "#33415533")}"/>')
        i = j + 1
    return "".join(out)


def _chart(title, inner, w=900, h=180):
    return (f'<div class="card"><h3>{html.escape(title)}</h3>'
            f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">'
            f'<rect width="{w}" height="{h}" fill="#0b1020"/>{inner}</svg></div>')


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #
def render_html(cur, res, meta) -> str:
    import json
    m = res.metrics
    ov, eqc, bhc = res.overlay, res.equity_curve, res.bh_curve
    N = len(ov)
    step = max(1, N // 800)                        # downsample for snappy charts
    idxs = list(range(0, N, step))
    labels = [time.strftime("%m-%d %H:%M", time.gmtime(ov[i][0])) for i in idxs]
    closes = [round(ov[i][1], 4) for i in idxs]
    stances = [ov[i][2] for i in idxs]
    equity = [round(eqc[i][1], 2) for i in idxs]
    bh = [round(bhc[i][1], 2) for i in idxs]
    big = (max(equity) / max(min(equity), 1e-9) > 20) if equity else False
    cdata = json.dumps({"labels": labels, "closes": closes, "stances": stances,
                        "equity": equity, "bh": bh, "logEq": big})

    checks_html = "".join(
        f'<span class="chk {"ok" if ok else "no"}">{html.escape(n)}</span>' for n, ok in cur["checks"])

    def pct(x): return f"{x*100:.1f}%"
    cagr = "∞" if m.get("cagr") == float("inf") else pct(m.get("cagr", 0))
    rows = [
        ("Trades", m["trades"]), ("Win rate", pct(m["win_rate"])),
        ("Total return", pct(m["total_return"])), ("CAGR", cagr),
        ("Buy & hold", pct(m["buy_hold_return"])), ("Alpha vs B&H", pct(m["alpha_vs_bh"])),
        ("Sharpe", f"{m['sharpe']:.2f}"), ("Sortino", f"{m['sortino']:.2f}"),
        ("Max drawdown", pct(m["max_drawdown"])), ("Exposure", pct(m["exposure"])),
        ("Liquidations", m["liquidations"]), ("Leverage", f"{meta['leverage']}x"),
        ("Final equity", f"${m['final_equity']:,.0f}"), ("Span (days)", f"{m['span_days']:.0f}"),
    ]
    metric_rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>"
                          for k, v in rows)
    trade_rows = "".join(
        f"<tr><td>{time.strftime('%Y-%m-%d %H:%M', time.gmtime(t.entry_ts))}</td>"
        f"<td>{time.strftime('%Y-%m-%d %H:%M', time.gmtime(t.exit_ts))}</td>"
        f"<td>{t.bars_held}</td><td class='{'pos' if t.ret_pct>=0 else 'neg'}'>{t.ret_pct*100:+.1f}%</td>"
        f"<td>{html.escape(t.reason_out)}</td></tr>" for t in res.trades[-25:])

    synth = meta.get("data_source") == "synthetic"
    banners = ""
    if synth:
        banners += ('<div class="banner red">SYNTHETIC DATA — plumbing only, NOT an edge '
                    'estimate. Synthetic regimes are learnable in a way real markets are not.</div>')
    banners += ('<div class="banner amber">Regimes for decisions are CAUSAL + walk-forward '
                f'({meta.get("folds","?")} folds) — never trained on the future. The popular '
                'video trades on smoothed (look-ahead) labels; this does not.</div>')
    banners += ('<div class="banner red">Leverage is '
                f'{meta["leverage"]}x — it can LIQUIDATE you. Backtests are not guarantees.</div>')

    stance_color = {"long": "#16a34a", "avoid": "#dc2626", "neutral": "#64748b"}.get(cur["stance"], "#64748b")
    call = cur["signal"].split(" ")[0]            # LONG / FLAT / NEUTRAL

    style = """<style>
body{font:14px/1.55 ui-monospace,Menlo,Consolas,monospace;margin:0;background:#070a14;color:#cbd5e1}
.wrap{max-width:1040px;margin:0 auto;padding:22px}
h1{margin:0;color:#e2e8f0} h3{color:#94a3b8;font-size:12px;margin:0 0 6px;text-transform:uppercase;letter-spacing:.06em}
.now{display:flex;gap:14px;background:#0b1020;border:1px solid #1e293b;border-radius:12px;padding:18px;margin:12px 0}
.now .box{flex:1}
.regime{font-size:26px;font-weight:800}
.call{font-size:26px;font-weight:800;padding:3px 14px;border-radius:9px;display:inline-block}
.call-LONG{background:#14532d;color:#bbf7d0}.call-FLAT{background:#7f1d1d;color:#fecaca}.call-NEUTRAL{background:#334155;color:#e2e8f0}.call-SHORT{background:#7c2d12;color:#fed7aa}
.muted{color:#64748b;font-size:13px;margin-top:4px}
.banner{padding:9px 13px;border-radius:7px;margin:8px 0;font-weight:600}
.banner.red{background:#7f1d1d;color:#fee2e2}.banner.amber{background:#78350f;color:#fef3c7}
.card{background:#0b1020;border:1px solid #1e293b;border-radius:12px;padding:14px;margin:12px 0}
table{width:100%;border-collapse:collapse}td{padding:5px 9px;border-bottom:1px solid #16203a}td:first-child{color:#94a3b8}
.chk{display:inline-block;padding:3px 8px;margin:2px;border-radius:6px;font-size:12px}
.chk.ok{background:#14532d;color:#bbf7d0}.chk.no{background:#3f1d1d;color:#fecaca}
.pos{color:#4ade80}.neg{color:#f87171}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.chartwrap{position:relative;height:210px}
a{color:#38bdf8}
</style>"""
    head_scripts = ('<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>'
                    '<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>')
    init = """<script>
(function(){
 if(typeof Chart==='undefined'){document.querySelectorAll('.chartwrap').forEach(function(e){e.innerHTML='<div class="muted">Charts need internet (Chart.js CDN did not load).</div>';});return;}
 try{Chart.register(window['chartjs-plugin-zoom']||window.ChartZoom);}catch(e){}
 var D=__CDATA__, SC={long:'#16a34a',avoid:'#dc2626',neutral:'#64748b'};
 var zoom={zoom:{wheel:{enabled:true},pinch:{enabled:true},mode:'x'},pan:{enabled:true,mode:'x'}};
 new Chart(document.getElementById('priceChart'),{type:'line',
  data:{labels:D.labels,datasets:[{label:'Price',data:D.closes,borderWidth:1.5,pointRadius:0,
   segment:{borderColor:function(c){return SC[D.stances[c.p1DataIndex]]||'#94a3b8';}}}]},
  options:{animation:false,responsive:true,maintainAspectRatio:false,
   plugins:{legend:{display:false},zoom:zoom,
    tooltip:{callbacks:{afterLabel:function(c){return 'regime: '+D.stances[c.dataIndex];}}}},
   scales:{x:{ticks:{maxTicksLimit:8,color:'#64748b'}},y:{ticks:{color:'#64748b'}}}}});
 new Chart(document.getElementById('eqChart'),{type:'line',
  data:{labels:D.labels,datasets:[
   {label:'Strategy equity',data:D.equity,borderColor:'#38bdf8',borderWidth:1.6,pointRadius:0},
   {label:'Buy & hold',data:D.bh,borderColor:'#94a3b8',borderWidth:1.2,pointRadius:0}]},
  options:{animation:false,responsive:true,maintainAspectRatio:false,
   plugins:{legend:{labels:{color:'#cbd5e1'}},zoom:zoom},
   scales:{x:{ticks:{maxTicksLimit:8,color:'#64748b'}},
    y:{type:D.logEq?'logarithmic':'linear',ticks:{color:'#64748b'}}}}});
})();
</script>""".replace("__CDATA__", cdata)

    body = f"""<div class="wrap">
<h1>&#9670; Regime Terminal</h1>
<div class="muted">{html.escape(str(meta.get('ticker','?')))} &middot; {meta.get('bars','?')} hourly bars &middot;
 {meta.get('covered','?')} backtested &middot; {html.escape(str(meta.get('data_source','?')))} &middot;
 git {html.escape(str(meta.get('git','?')))}</div>
{banners}
<div class="now">
  <div class="box"><h3>Detected regime</h3>
    <div class="regime" style="color:{stance_color}">{html.escape(cur['name']).upper()}</div>
    <div class="muted">confidence {cur['confidence']*100:.0f}% &middot; state {cur['state']} &middot; price {cur['price']:,.2f}</div></div>
  <div class="box"><h3>Signal</h3>
    <div class="call call-{call}">{call}</div>
    <div class="muted">{html.escape(cur['signal'])}</div></div>
  <div class="box" style="flex:1.6"><h3>Confirmations {cur['n_pass']}/8</h3>
    <div>{checks_html}</div></div>
</div>
<div class="grid">
  <div class="card"><h3>Price + regime overlay &mdash; green long / gray neutral / red avoid</h3>
    <div class="chartwrap"><canvas id="priceChart"></canvas></div></div>
  <div class="card"><h3>Equity (blue) vs buy &amp; hold (gray){' &mdash; log' if big else ''}</h3>
    <div class="chartwrap"><canvas id="eqChart"></canvas></div></div>
</div>
<div class="grid">
  <div class="card"><h3>Performance (walk-forward, out-of-sample)</h3><table>{metric_rows}</table></div>
  <div class="card"><h3>Recent trades</h3><table>
    <tr><td>entry</td><td>exit</td><td>bars</td><td>return</td><td>exit reason</td></tr>
    {trade_rows}</table></div>
</div>
</div>"""
    return ("<!doctype html><html><head><meta charset=\"utf-8\"><title>Regime Terminal</title>"
            + head_scripts + style + "</head><body>" + body + init + "</body></html>")


def build_html(cur, res, meta, path):
    doc = render_html(cur, res, meta)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write(doc)


def _git():
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "?"


def main():
    ap = argparse.ArgumentParser(description="Regime Terminal")
    ap.add_argument("--ticker", default=config.TICKER)
    ap.add_argument("--days", type=int, default=240)
    ap.add_argument("--synthetic", action="store_true", help="alias for --source synthetic")
    ap.add_argument("--source", choices=["synthetic", "yfinance", "kucoin"], default=None,
                    help="data source (kucoin uses symbols like BTC-USDT)")
    ap.add_argument("--drift-scale", type=float, default=0.2)
    ap.add_argument("--leverage", type=float, default=config.LEVERAGE)
    ap.add_argument("--short", action="store_true", help="also short bear/crash regimes")
    ap.add_argument("--train-once", action="store_true", help="faster, mildly leaky (not WF)")
    ap.add_argument("--html", default="reports/regime_terminal.html")
    args = ap.parse_args()
    config.LEVERAGE = args.leverage

    source = args.source or ("synthetic" if args.synthetic else "yfinance")
    if source == "synthetic":
        from data import synthetic_ohlcv
        print(f"[synthetic] {args.days}d hourly bars (drift_scale={args.drift_scale}) — NOT real data")
        bars, _ = synthetic_ohlcv(days=args.days, drift_scale=args.drift_scale)
    else:
        from data import get_bars
        print(f"[{source}] {args.ticker} {args.days}d hourly…")
        try:
            bars = get_bars(args.ticker, args.days, source=source)
        except RuntimeError as e:
            print(f"  ✗ {e}\n  This sandbox blocks exchange/data hosts — run locally, "
                  f"or use --synthetic.")
            raise SystemExit(2)

    print("Training regime model + running walk-forward backtest (this trains an HMM "
          "per fold)…")
    cur = current_read(bars, config, allow_short=args.short)
    res = run_backtest(bars, config, walk_forward=not args.train_once, allow_short=args.short)
    res.meta.update({"ticker": args.ticker, "data_source": source, "git": _git()})

    # terminal summary
    m = res.metrics
    print("\n" + "=" * 64)
    print(f" DETECTED REGIME: {cur['name'].upper()}  (confidence {cur['confidence']*100:.0f}%)")
    print(f" SIGNAL: {cur['signal']}")
    print(f" confirmations: {cur['n_pass']}/{config.CONFIRMATIONS_TOTAL} "
          f"[{', '.join(n for n, ok in cur['checks'] if ok)}]")
    print("-" * 64)
    if m.get("trades"):
        print(f" Walk-forward {res.meta['folds']} folds, {res.meta['covered']} bars OOS, "
              f"{config.LEVERAGE}x leverage")
        print(f" Total return {m['total_return']*100:.1f}%  |  Buy&Hold {m['buy_hold_return']*100:.1f}%"
              f"  |  Alpha {m['alpha_vs_bh']*100:+.1f}%")
        print(f" Win rate {m['win_rate']*100:.0f}%  trades {m['trades']}  Sharpe {m['sharpe']:.2f}"
              f"  maxDD {m['max_drawdown']*100:.0f}%  liq {m['liquidations']}")
    else:
        print(" No backtest trades (insufficient data for a fold).")
    if source == "synthetic":
        print(" !! SYNTHETIC DATA — plumbing only, NOT an edge estimate.")
    print(f" Decisions are causal/walk-forward (no look-ahead). Leverage can liquidate.")
    print("=" * 64)

    build_html(cur, res, res.meta, args.html)
    print(f" HTML dashboard -> {args.html}")


if __name__ == "__main__":
    main()
