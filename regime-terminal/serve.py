"""
serve.py — the Regime Terminal as a local web app (pure stdlib, no deps).

    cd regime-terminal && python serve.py        # open http://localhost:8000

Async + live progress: "Run Analysis" starts the engine in a BACKGROUND thread and
sends you to a progress page that streams each step (fetching data, training fold
2/6, simulating, rendering) so it never looks dead. Finished runs are kept so you
can re-open them and compare settings side-by-side.

Notes:
  * Pure-Python HMM training takes ~30s-2min per run; `pip install hmmlearn numpy`
    makes it seconds (auto-detected). The progress page shows real status either way.
  * This sandbox blocks live data hosts; use the synthetic source here. KuCoin/
    Yahoo work on your own machine.
"""
from __future__ import annotations

import http.server
import threading
import time
import urllib.parse
import uuid

import config
from backtest import run_backtest
from data import synthetic_ohlcv
from terminal import _git, current_read, render_html

config.HMM_N_INIT = 3          # keep web runs responsive (fewer restarts)
PORT = 8000

JOBS: dict[str, "Job"] = {}
LOCK = threading.Lock()        # guards JOBS + each job's mutable fields
RUN_LOCK = threading.Lock()    # serialize CPU-heavy runs (and config-global writes)


class Job:
    def __init__(self, params):
        self.id = uuid.uuid4().hex[:12]
        self.params = params
        self.status = "queued"          # queued | running | done | error
        self.frac = 0.0
        self.log: list[list] = [[0.0, "Queued…"]]
        self.result_html: str | None = None
        self.summary: dict | None = None
        self.error: str | None = None
        self.t0 = time.time()

    def progress(self, msg, frac):
        with LOCK:
            self.status = "running"
            self.frac = max(self.frac, float(frac))
            self.log.append([round(self.frac, 2), msg])


def worker(job: Job):
    g = lambda k, d="": job.params.get(k, [d])[0]
    with RUN_LOCK:                       # one heavy run at a time (avoids config races)
        try:
            config.LEVERAGE = float(g("leverage", "2.5"))
            config.CONFIRMATIONS_REQUIRED = int(g("confirms", "7"))
            config.N_STATES = max(2, min(int(g("states", "7")), 12))
            days = max(40, min(int(g("days", "180")), 730))
            fast = g("mode", "wf") == "fast"
            short = g("short", "") == "on"
            source = g("source", "synthetic")
            ticker = g("ticker", "BTC-USDT")

            job.progress(f"Fetching {source} data ({ticker}, {days}d)…", 0.05)
            if source in ("kucoin", "coinbase", "yfinance"):
                from data import get_bars
                bars = get_bars(ticker, days, source=source)
            else:
                bars = synthetic_ohlcv(days=days, drift_scale=float(g("drift", "0.2")))[0]

            cur = current_read(bars, config, progress=job.progress, allow_short=short)
            res = run_backtest(bars, config, walk_forward=not fast, progress=job.progress, allow_short=short)
            res.meta.update({"ticker": ticker, "data_source": source, "git": _git()})
            job.progress("Rendering dashboard…", 0.97)
            html_doc = render_html(cur, res, res.meta)
            m = res.metrics
            with LOCK:
                job.result_html = html_doc
                job.summary = {
                    "ticker": ticker, "source": source, "leverage": config.LEVERAGE,
                    "states": config.N_STATES, "mode": "fast" if fast else "WF",
                    "regime": cur["name"], "signal": cur["signal"].split(" ")[0],
                    "total_return": m.get("total_return", 0.0), "alpha": m.get("alpha_vs_bh", 0.0),
                    "win": m.get("win_rate", 0.0), "sharpe": m.get("sharpe", 0.0),
                    "maxdd": m.get("max_drawdown", 0.0), "trades": m.get("trades", 0),
                    "when": time.strftime("%H:%M:%S", time.localtime(job.t0)),
                }
                job.status, job.frac = "done", 1.0
                job.log.append([1.0, "Done."])
        except Exception as e:
            import traceback
            traceback.print_exc()
            with LOCK:
                job.status = "error"
                job.error = f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
BASE_CSS = """<style>
body{font:15px/1.6 ui-monospace,Menlo,Consolas,monospace;background:#070a14;color:#cbd5e1;margin:0}
.wrap{max-width:680px;margin:36px auto;padding:24px;background:#0b1020;border:1px solid #1e293b;border-radius:12px}
h1{color:#e2e8f0;margin:0 0 4px} .sub{color:#64748b;margin-bottom:18px}
label{display:block;margin:14px 0 4px;color:#94a3b8}
input,select{width:100%;box-sizing:border-box;padding:9px;background:#070a14;color:#e2e8f0;border:1px solid #334155;border-radius:7px;font:inherit}
.row{display:flex;gap:12px}.row>div{flex:1}
button{margin-top:22px;width:100%;padding:13px;background:#2563eb;color:#fff;border:0;border-radius:8px;font:inherit;font-weight:700;cursor:pointer}
button:hover{background:#1d4ed8} a{color:#38bdf8}
.note{margin-top:14px;color:#64748b;font-size:13px} .amber{color:#fbbf24}
.bar{height:12px;background:#1e293b;border-radius:6px;overflow:hidden;margin:14px 0}
.barfill{height:100%;width:0;background:#2563eb;transition:width .4s}
.log{background:#070a14;border:1px solid #1e293b;border-radius:8px;padding:12px;height:300px;overflow:auto;font-size:13px;white-space:pre-wrap}
.runs{margin-top:22px;border-top:1px solid #1e293b;padding-top:14px}
.run{display:flex;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid #16203a;font-size:13px}
.run .grow{flex:1} .pos{color:#4ade80}.neg{color:#f87171} .err{color:#f87171}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:6px 9px;border-bottom:1px solid #16203a;text-align:left}
</style>"""


def form_page():
    runs = recent_runs_html()
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Regime Terminal</title>{BASE_CSS}
</head><body><div class="wrap">
<h1>&#9670; Regime Terminal</h1>
<div class="sub">HMM regime detection + regime-gated leveraged strategy &middot; causal, walk-forward, honest</div>
<form method="POST" action="/run">
  <div class="row">
    <div><label>Data source</label><select name="source">
      <option value="synthetic">Synthetic (sandbox)</option>
      <option value="coinbase">Coinbase (e.g. BTC-USD)</option>
      <option value="kucoin">KuCoin (e.g. BTC-USDT)</option>
      <option value="yfinance">Yahoo Finance (e.g. BTC-USD)</option></select></div>
    <div><label>Ticker</label><input name="ticker" value="BTC-USDT"></div>
  </div>
  <div class="row">
    <div><label>Days (hourly bars)</label><input name="days" type="number" value="120" min="40" max="730"></div>
    <div><label>HMM states</label><input name="states" type="number" value="7" min="2" max="12"></div>
  </div>
  <div class="row">
    <div><label>Leverage (&times;)</label><input name="leverage" type="number" step="0.5" value="2.5" min="1" max="10"></div>
    <div><label>Confirmations required (of 8)</label><input name="confirms" type="number" value="7" min="1" max="8"></div>
  </div>
  <div class="row">
    <div><label>Backtest mode</label><select name="mode">
      <option value="wf">Walk-forward (honest)</option>
      <option value="fast">Fast / train-once (mildly leaky)</option></select></div>
    <div><label>Synthetic drift scale</label><input name="drift" type="number" step="0.05" value="0.2" min="0" max="1"></div>
  </div>
  <div style="margin-top:12px"><label style="display:inline">
    <input type="checkbox" name="short" style="width:auto;vertical-align:middle"> Also SHORT bear/crash regimes (instead of just sitting out)</label></div>
  <button type="submit">Run Analysis &rarr;</button>
  <div class="note"><span class="amber">&#9888;</span> Fewer states + 'Fast' mode finish quicker.
   Leverage can liquidate you; synthetic results are plumbing, not edge.</div>
</form>{runs}</div></body></html>"""


def recent_runs_html():
    with LOCK:
        done = [j for j in JOBS.values() if j.status == "done" and j.summary]
    done.sort(key=lambda j: j.t0, reverse=True)
    if not done:
        return ""
    rows = []
    for j in done[:12]:
        s = j.summary
        cls = "pos" if s["total_return"] >= 0 else "neg"
        rows.append(
            f'<div class="run"><input type="checkbox" class="cmp" value="{j.id}">'
            f'<span class="grow">{s["when"]} &middot; {s["source"]}:{s["ticker"]} &middot; '
            f'{s["states"]}st {s["leverage"]}x {s["mode"]} &middot; '
            f'<span class="{cls}">ret {s["total_return"]*100:+.1f}%</span> '
            f'(α {s["alpha"]*100:+.1f}%, win {s["win"]*100:.0f}%)</span>'
            f'<a href="/result/{j.id}">view</a></div>')
    return (f'<div class="runs"><h3 style="color:#94a3b8">Recent runs '
            f'<button type="button" style="width:auto;margin:0 0 0 8px;padding:5px 10px" '
            f'onclick="cmp()">Compare selected</button></h3>{"".join(rows)}</div>'
            '<script>function cmp(){var ids=[].slice.call(document.querySelectorAll(".cmp:checked"))'
            '.map(function(c){return c.value});if(ids.length)location="/compare?ids="+ids.join(",");}</script>')


def job_page(jid):
    if jid not in JOBS:
        return "<h1>404 — unknown job</h1>"
    js = """<script>
var ID='__ID__';
function poll(){
 fetch('/status/'+ID).then(function(r){return r.json()}).then(function(d){
  document.getElementById('bf').style.width=(d.frac*100).toFixed(0)+'%';
  document.getElementById('log').innerHTML=d.log.map(function(x){
   return '<div>'+Math.round(x[0]*100)+'%\\t'+x[1]+'</div>';}).join('');
  var L=document.getElementById('log');L.scrollTop=L.scrollHeight;
  if(d.status==='done'){location='/result/'+ID;}
  else if(d.status==='error'){document.getElementById('st').innerHTML=
   '<div class="err">Failed: '+d.error+'</div><a href="/">&larr; back</a>';}
  else{setTimeout(poll,900);}
 }).catch(function(){setTimeout(poll,1500);});
}
poll();
</script>""".replace("__ID__", jid)
    return (f"""<!doctype html><html><head><meta charset="utf-8"><title>Running…</title>{BASE_CSS}
</head><body><div class="wrap">
<h1>Running analysis…</h1>
<div class="sub">Training a Hidden Markov Model per walk-forward fold. Keep this tab open.</div>
<div class="bar"><div class="barfill" id="bf"></div></div>
<div id="st"></div>
<div class="log" id="log">Starting…</div>
<div class="note">First run can take ~30s&ndash;2min in pure Python. Install hmmlearn for seconds.</div>
</div>{js}</body></html>""")


def status_json(jid):
    import json
    if jid not in JOBS:
        return json.dumps({"status": "error", "error": "unknown job", "frac": 0, "log": []})
    j = JOBS[jid]
    with LOCK:
        return json.dumps({"status": j.status, "frac": j.frac,
                           "log": list(j.log), "error": j.error})


def result_page(jid):
    j = JOBS.get(jid)
    if not j or not j.result_html:
        return "<h1>404 — result not ready</h1>"
    back = ('<div style="position:sticky;top:0;background:#070a14;padding:10px 22px;'
            'border-bottom:1px solid #1e293b;font-family:ui-monospace,monospace">'
            '<a href="/" style="color:#38bdf8;text-decoration:none">&larr; New analysis</a></div>')
    return j.result_html.replace("<body>", "<body>" + back, 1)


def compare_page(ids_str):
    ids = [i for i in ids_str.split(",") if i]
    with LOCK:
        sums = [(i, JOBS[i].summary) for i in ids if i in JOBS and JOBS[i].summary]
    if not sums:
        return "<h1>Nothing to compare</h1><a href='/'>back</a>"
    fields = [("Source", lambda s: f'{s["source"]}:{s["ticker"]}'),
              ("States", lambda s: s["states"]), ("Leverage", lambda s: f'{s["leverage"]}x'),
              ("Mode", lambda s: s["mode"]), ("Regime", lambda s: s["regime"]),
              ("Signal", lambda s: s["signal"]),
              ("Total return", lambda s: f'{s["total_return"]*100:+.1f}%'),
              ("Alpha vs B&H", lambda s: f'{s["alpha"]*100:+.1f}%'),
              ("Win rate", lambda s: f'{s["win"]*100:.0f}%'),
              ("Sharpe", lambda s: f'{s["sharpe"]:.2f}'),
              ("Max DD", lambda s: f'{s["maxdd"]*100:.0f}%'),
              ("Trades", lambda s: s["trades"])]
    header = "".join(f"<th>{s['when']}</th>" for _, s in sums)
    rows = "".join("<tr><td>" + name + "</td>" +
                   "".join(f"<td>{fn(s)}</td>" for _, s in sums) + "</tr>"
                   for name, fn in fields)
    return (f"""<!doctype html><html><head><meta charset="utf-8"><title>Compare</title>{BASE_CSS}
</head><body><div class="wrap" style="max-width:900px">
<h1>Compare runs</h1><div class="sub"><a href="/">&larr; back</a></div>
<table><tr><th>metric</th>{header}</tr>{rows}</table></div></body></html>""")


# --------------------------------------------------------------------------- #
# server
# --------------------------------------------------------------------------- #
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, code=200, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        r = u.path
        if r in ("/", "/index.html"):
            self._send(form_page())
        elif r.startswith("/job/"):
            self._send(job_page(r.split("/", 2)[2]))
        elif r.startswith("/status/"):
            self._send(status_json(r.split("/", 2)[2]), ctype="application/json")
        elif r.startswith("/result/"):
            self._send(result_page(r.split("/", 2)[2]))
        elif r == "/compare":
            self._send(compare_page(urllib.parse.parse_qs(u.query).get("ids", [""])[0]))
        else:
            self._send("<h1>404</h1>", 404)

    def do_POST(self):
        if self.path != "/run":
            self._send("<h1>404</h1>", 404); return
        n = int(self.headers.get("Content-Length", 0))
        params = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))
        job = Job(params)
        with LOCK:
            JOBS[job.id] = job
        threading.Thread(target=worker, args=(job,), daemon=True).start()
        self.send_response(303)
        self.send_header("Location", f"/job/{job.id}")
        self.end_headers()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Regime Terminal serving at http://localhost:{args.port}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


if __name__ == "__main__":
    main()
