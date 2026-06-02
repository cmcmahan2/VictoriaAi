"""
serve.py — the Regime Terminal as a local web app (pure stdlib, no deps).

    cd regime-terminal && python serve.py
    # open http://localhost:8000

A form (ticker / days / leverage / confirmations / data source) + a "Run Analysis"
button. On submit it runs the REAL engine (current regime, walk-forward backtest)
and renders the same dashboard you get from terminal.py — interactive, like the
video, but with the honest causal/walk-forward internals.

Notes:
  * Training a pure-Python HMM per walk-forward fold takes ~30s-2min; the page
    blocks while it runs (single-user local tool). Use 'fast (train-once)' for a
    quick look, or fewer days/states. hmmlearn would make this instant.
  * This sandbox blocks Yahoo Finance, so use the synthetic source here; real data
    works when you run it on your own machine.
"""
from __future__ import annotations

import http.server
import urllib.parse

import config
from backtest import run_backtest
from data import synthetic_ohlcv
from terminal import _git, current_read, render_html

config.HMM_N_INIT = 3  # keep web runs responsive (fewer restarts than validation)

PORT = 8000

FORM = """<!doctype html><html><head><meta charset="utf-8"><title>Regime Terminal</title>
<style>
body{font:15px/1.6 ui-monospace,Menlo,Consolas,monospace;background:#070a14;color:#cbd5e1;margin:0}
.wrap{max-width:640px;margin:40px auto;padding:24px;background:#0b1020;border:1px solid #1e293b;border-radius:12px}
h1{color:#e2e8f0;margin:0 0 4px} .sub{color:#64748b;margin-bottom:20px}
label{display:block;margin:14px 0 4px;color:#94a3b8}
input,select{width:100%;box-sizing:border-box;padding:9px;background:#070a14;color:#e2e8f0;border:1px solid #334155;border-radius:7px;font:inherit}
.row{display:flex;gap:12px}.row>div{flex:1}
button{margin-top:22px;width:100%;padding:13px;background:#2563eb;color:#fff;border:0;border-radius:8px;font:inherit;font-weight:700;cursor:pointer}
button:hover{background:#1d4ed8}
.note{margin-top:14px;color:#64748b;font-size:13px}
.amber{color:#fbbf24}
</style></head><body><div class="wrap">
<h1>&#9670; Regime Terminal</h1>
<div class="sub">HMM regime detection + regime-gated leveraged strategy &middot; causal, walk-forward, honest</div>
<form method="POST" action="/run">
  <div class="row">
    <div><label>Data source</label>
      <select name="source"><option value="synthetic">Synthetic (sandbox)</option>
      <option value="kucoin">KuCoin (e.g. BTC-USDT)</option>
      <option value="yfinance">Yahoo Finance (e.g. BTC-USD)</option></select></div>
    <div><label>Ticker</label><input name="ticker" value="BTC-USDT"></div>
  </div>
  <div class="row">
    <div><label>Days (hourly bars)</label><input name="days" type="number" value="180" min="40" max="730"></div>
    <div><label>HMM states</label><input name="states" type="number" value="7" min="2" max="12"></div>
  </div>
  <div class="row">
    <div><label>Leverage (&times;)</label><input name="leverage" type="number" step="0.5" value="2.5" min="1" max="10"></div>
    <div><label>Confirmations required (of 8)</label><input name="confirms" type="number" value="7" min="1" max="8"></div>
  </div>
  <div class="row">
    <div><label>Backtest mode</label>
      <select name="mode"><option value="wf">Walk-forward (honest)</option>
      <option value="fast">Fast / train-once (mildly leaky)</option></select></div>
    <div><label>Synthetic drift scale</label><input name="drift" type="number" step="0.05" value="0.2" min="0" max="1"></div>
  </div>
  <button type="submit">Run Analysis &rarr;</button>
  <div class="note"><span class="amber">&#9888;</span> Trains an HMM per fold in pure Python &mdash;
   give it ~30s&ndash;2min. Leverage can liquidate you; synthetic results are plumbing, not edge.</div>
</form></div></body></html>"""

BACK = ('<div style="position:sticky;top:0;background:#070a14;padding:10px 22px;'
        'border-bottom:1px solid #1e293b"><a href="/" style="color:#38bdf8;'
        'text-decoration:none">&larr; Run another analysis</a></div>')


def run_analysis(p):
    g = lambda k, d="": p.get(k, [d])[0]
    config.LEVERAGE = float(g("leverage", "2.5"))
    config.CONFIRMATIONS_REQUIRED = int(g("confirms", "7"))
    config.N_STATES = int(g("states", "7"))
    days = max(40, min(int(g("days", "180")), 730))
    fast = g("mode", "wf") == "fast"
    source = g("source", "synthetic")
    ticker = g("ticker", "BTC-USDT")
    if source in ("kucoin", "yfinance"):
        from data import get_bars
        bars = get_bars(ticker, days, source=source)   # raises if blocked/no pkg
        src = source
    else:
        bars = synthetic_ohlcv(days=days, drift_scale=float(g("drift", "0.2")))[0]
        src = "synthetic"
    cur = current_read(bars, config)
    res = run_backtest(bars, config, walk_forward=not fast)
    res.meta.update({"ticker": ticker, "data_source": src, "git": _git()})
    return BACK + render_html(cur, res, res.meta)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(FORM if self.path in ("/", "/index.html") else "<h1>404</h1>",
                   200 if self.path in ("/", "/index.html") else 404)

    def do_POST(self):
        if self.path != "/run":
            self._send("<h1>404</h1>", 404); return
        n = int(self.headers.get("Content-Length", 0))
        params = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))
        try:
            self._send(run_analysis(params))
        except Exception as e:
            self._send(BACK + f'<div style="padding:30px;color:#f87171">'
                       f'<h2>Analysis failed</h2><pre>{type(e).__name__}: {e}</pre>'
                       f'<p>If using real data: this sandbox blocks Yahoo Finance — '
                       f'run locally, or pick the synthetic source.</p></div>', 500)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    srv = http.server.HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Regime Terminal serving at http://localhost:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


if __name__ == "__main__":
    main()
