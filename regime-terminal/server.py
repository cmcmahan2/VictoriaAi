"""
server.py — BTC Swing Trade Dashboard (live chart + AI intelligence panel)

A tiny Flask app that pairs a live TradingView candlestick chart with our own
intelligence layer (regime HMM, indicators, Fear & Greed, news, Claude plan).

  pip install flask anthropic
  ANTHROPIC_API_KEY=sk-ant-...  python server.py
  # then open http://localhost:5000

Routes:
  GET /                         the dashboard
  GET /api/intel?source=&days=  regime + indicators + sentiment + news (JSON)
  GET /api/plan?source=&days=   the above + Claude swing-trade plan (costs 1 API call)

The live chart is TradingView's free embed (no key). The AI plan is on a button
so you only spend an API call when you actually want a fresh read.
"""
from __future__ import annotations

import argparse

from flask import Flask, jsonify, request

from live import load_recent
from market_intel import (analyze_indicators, analyze_regime, build_prompt,
                          call_claude, fetch_fear_greed, fetch_news, price_levels)

app = Flask(__name__)


def _gather(source: str, days: int) -> dict:
    """Run the full data + analysis pipeline, return a JSON-safe dict."""
    bars = load_recent(source, "BTC-USDT" if source == "kucoin" else "BTC-USD", days)
    if not bars:
        return {"error": f"No data from {source}. Try a different --source."}
    regime = analyze_regime(bars)
    ind    = analyze_indicators(bars)
    levels = price_levels(bars)
    fg     = fetch_fear_greed()
    news   = fetch_news()
    return {
        "regime": regime,
        "indicators": {
            "n_pass": ind["n_pass"], "n_total": ind["n_total"],
            "rsi": ind["rsi"], "macd_hist": ind["macd_hist"], "adx": ind["adx"],
            "momentum": ind["momentum"], "sma_200": ind["sma_200"],
            "above_200": ind["above_200"],
            "checks": [{"name": n, "ok": ok} for n, ok in ind["checks"]],
        },
        "levels": levels,
        "fear_greed": fg,
        "news": news,
        "_bars": bars,          # kept for the plan endpoint, stripped before jsonify
    }


@app.route("/api/intel")
def api_intel():
    source = request.args.get("source", "kucoin")
    days   = int(request.args.get("days", 90))
    data = _gather(source, days)
    data.pop("_bars", None)
    return jsonify(data)


@app.route("/api/plan")
def api_plan():
    source = request.args.get("source", "kucoin")
    days   = int(request.args.get("days", 90))
    data = _gather(source, days)
    if data.get("error"):
        return jsonify(data)
    bars = data.pop("_bars")
    # reconstruct the rich indicators dict for the prompt
    ind_full = analyze_indicators(bars)
    prompt = build_prompt(data["regime"], ind_full, data["levels"],
                          data["fear_greed"], data["news"])
    plan = call_claude(prompt)
    if plan is None:
        data["plan"] = None
        data["plan_error"] = "Set ANTHROPIC_API_KEY before starting the server to enable AI plans."
    else:
        data["plan"] = plan
    return jsonify(data)


@app.route("/")
def index():
    return DASHBOARD_HTML


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>BTC Swing Intel</title>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --border:#30363d; --txt:#c9d1d9;
          --muted:#8b949e; --green:#3fb950; --red:#f85149; --amber:#d29922;
          --accent:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
  header { display:flex; align-items:baseline; gap:18px; flex-wrap:wrap;
           padding:12px 20px; border-bottom:1px solid var(--border); background:var(--panel); }
  header h1 { font-size:16px; margin:0; letter-spacing:.5px; }
  #price { font-size:22px; font-weight:700; }
  .chg { font-size:14px; font-weight:600; }
  .up { color:var(--green); } .down { color:var(--red); }
  .controls { margin-left:auto; display:flex; gap:8px; align-items:center; }
  select,button { background:#21262d; color:var(--txt); border:1px solid var(--border);
                  border-radius:6px; padding:6px 10px; font-size:13px; cursor:pointer; }
  button.primary { background:var(--accent); color:#06121f; border-color:var(--accent); font-weight:600; }
  button:disabled { opacity:.5; cursor:wait; }
  .wrap { display:flex; height:calc(100vh - 58px); }
  .chart { flex:2; min-width:0; border-right:1px solid var(--border); }
  #tv_chart { width:100%; height:100%; }
  .panel { flex:1; min-width:340px; max-width:460px; overflow-y:auto; padding:16px; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:10px;
          padding:14px; margin-bottom:14px; }
  .card h2 { margin:0 0 10px; font-size:12px; text-transform:uppercase;
             letter-spacing:1px; color:var(--muted); }
  .badge { display:inline-block; padding:4px 12px; border-radius:20px; font-weight:700;
           font-size:14px; }
  .badge.long { background:rgba(63,185,80,.15); color:var(--green); }
  .badge.avoid{ background:rgba(248,81,73,.15); color:var(--red); }
  .badge.neutral{ background:rgba(210,153,34,.15); color:var(--amber); }
  .row { display:flex; justify-content:space-between; padding:5px 0; font-size:14px;
         border-bottom:1px solid rgba(255,255,255,.04); }
  .row:last-child { border-bottom:none; }
  .row .k { color:var(--muted); }
  .gauge { height:14px; border-radius:7px; margin:8px 0 4px;
           background:linear-gradient(90deg,#f85149,#d29922,#3fb950); position:relative; }
  .gauge .needle { position:absolute; top:-3px; width:3px; height:20px; background:#fff;
                   border-radius:2px; box-shadow:0 0 4px #000; }
  .checks { display:grid; grid-template-columns:1fr 1fr; gap:4px 12px; font-size:12.5px; }
  .checks div::before { margin-right:6px; }
  .pass::before { content:"✓"; color:var(--green); }
  .fail::before { content:"✗"; color:var(--red); }
  .news a, .news span { color:var(--txt); text-decoration:none; font-size:12.5px;
                        display:block; padding:4px 0; border-bottom:1px solid rgba(255,255,255,.04); }
  .news .src { color:var(--accent); font-size:11px; }
  pre.plan { white-space:pre-wrap; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
             font-size:13px; line-height:1.5; color:var(--txt); margin:0; }
  .muted { color:var(--muted); font-size:12px; }
  .spin { color:var(--accent); }
</style>
</head>
<body>
<header>
  <h1>₿ SWING INTEL</h1>
  <span id="price">—</span>
  <span id="chg24" class="chg"></span>
  <span id="chg7" class="chg"></span>
  <div class="controls">
    <select id="symbol" title="chart feed">
      <option value="BINANCE:BTCUSDT">BINANCE:BTCUSDT</option>
      <option value="COINBASE:BTCUSD">COINBASE:BTCUSD</option>
      <option value="BITSTAMP:BTCUSD">BITSTAMP:BTCUSD</option>
    </select>
    <select id="source" title="analysis data source">
      <option value="kucoin">data: kucoin</option>
      <option value="coinbase">data: coinbase</option>
      <option value="yfinance">data: yfinance</option>
      <option value="github">data: github (offline)</option>
    </select>
    <button id="refresh">↻ Refresh</button>
    <button id="genplan" class="primary">⚡ AI Plan</button>
  </div>
</header>

<div class="wrap">
  <div class="chart"><div id="tv_chart"></div></div>
  <div class="panel">
    <div class="card" id="planCard">
      <h2>AI Swing Plan</h2>
      <pre class="plan" id="plan">Press “⚡ AI Plan” for a fresh swing-trade read.</pre>
    </div>
    <div class="card">
      <h2>Regime &amp; Technicals</h2>
      <div class="row"><span class="k">Regime</span><span id="regime">—</span></div>
      <div class="row"><span class="k">Confidence</span><span id="conf">—</span></div>
      <div class="row"><span class="k">Confirmations</span><span id="confirm">—</span></div>
      <div class="row"><span class="k">RSI(14)</span><span id="rsi">—</span></div>
      <div class="row"><span class="k">Macro trend</span><span id="trend">—</span></div>
      <div class="checks" id="checks" style="margin-top:10px"></div>
    </div>
    <div class="card">
      <h2>Fear &amp; Greed</h2>
      <div class="gauge"><div class="needle" id="needle" style="left:0%"></div></div>
      <div class="row"><span class="k" id="fgLabel">—</span><span id="fgVal">—</span></div>
    </div>
    <div class="card">
      <h2>Latest BTC Headlines</h2>
      <div class="news" id="news"><span class="muted">Loading…</span></div>
    </div>
    <p class="muted">Analysis is causal (no look-ahead). The AI plan is guidance, not a
       guarantee — you place the trade. Stops are mandatory.</p>
  </div>
</div>

<script src="https://s3.tradingview.com/tv.js"></script>
<script>
function makeChart(sym){
  document.getElementById('tv_chart').innerHTML='';
  new TradingView.widget({
    container_id:'tv_chart', autosize:true, symbol:sym, interval:'60',
    timezone:'Etc/UTC', theme:'dark', style:'1', locale:'en',
    studies:['RSI@tv-basicstudies','MASimple@tv-basicstudies'],
    hide_side_toolbar:false
  });
}

function pct(x){ return x==null ? '—' : (x>0?'▲':'▼')+Math.abs(x).toFixed(1)+'%'; }
function money(x){ return x==null ? '—' : '$'+Math.round(x).toLocaleString(); }

function render(d){
  if(d.error){ document.getElementById('price').textContent=d.error; return; }
  const L=d.levels, R=d.regime, I=d.indicators, F=d.fear_greed;
  document.getElementById('price').textContent = money(L.current);
  const c24=document.getElementById('chg24'); c24.textContent=pct(L.change_24h)+' 24h';
  c24.className='chg '+(L.change_24h>=0?'up':'down');
  const c7=document.getElementById('chg7'); c7.textContent=pct(L.change_7d)+' 7d';
  c7.className='chg '+(L.change_7d>=0?'up':'down');

  const stance=(R.stance||'').toLowerCase();
  const cls = stance==='long'?'long':(stance==='avoid'?'avoid':'neutral');
  document.getElementById('regime').innerHTML='<span class="badge '+cls+'">'+(R.stance||'?').toUpperCase()+'</span>';
  document.getElementById('conf').textContent=(R.confidence*100).toFixed(0)+'%';
  document.getElementById('confirm').textContent=I.n_pass+'/'+I.n_total+' passing';
  document.getElementById('rsi').textContent = I.rsi==null?'—':
     I.rsi.toFixed(1)+(I.rsi>70?'  (overbought)':I.rsi<30?'  (oversold)':'');
  document.getElementById('trend').textContent = I.above_200?'above 200h SMA ↑':'below 200h SMA ↓';

  document.getElementById('checks').innerHTML = I.checks.map(c=>
     '<div class="'+(c.ok?'pass':'fail')+'">'+c.name+'</div>').join('');

  if(F && F.value!=null){
    document.getElementById('needle').style.left=F.value+'%';
    document.getElementById('fgLabel').textContent=F.label;
    document.getElementById('fgVal').textContent=F.value+'/100';
  } else {
    document.getElementById('fgLabel').textContent='unavailable';
  }

  document.getElementById('news').innerHTML = (d.news||[]).slice(0,8).map(a=>
     '<span><span class="src">'+(a.source||'')+'</span> '+a.title+'</span>').join('')
     || '<span class="muted">No headlines.</span>';
}

async function refresh(){
  const src=document.getElementById('source').value;
  try{
    const r=await fetch('/api/intel?source='+src+'&days=90');
    render(await r.json());
  }catch(e){ document.getElementById('price').textContent='fetch error'; }
}

async function genPlan(){
  const btn=document.getElementById('genplan'), src=document.getElementById('source').value;
  const out=document.getElementById('plan');
  btn.disabled=true; out.innerHTML='<span class="spin">Analyzing market &amp; generating plan…</span>';
  try{
    const r=await fetch('/api/plan?source='+src+'&days=90');
    const d=await r.json(); render(d);
    out.textContent = d.plan || d.plan_error || 'No plan returned.';
  }catch(e){ out.textContent='Error generating plan.'; }
  btn.disabled=false;
}

document.getElementById('refresh').onclick=refresh;
document.getElementById('genplan').onclick=genPlan;
document.getElementById('symbol').onchange=e=>makeChart(e.target.value);

makeChart(document.getElementById('symbol').value);
refresh();
setInterval(refresh, 300000);   // refresh data panel every 5 min (chart is live on its own)
</script>
</body>
</html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BTC swing trade dashboard")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    print(f"\n  BTC Swing Intel dashboard → http://{args.host}:{args.port}\n"
          f"  (Ctrl+C to stop)\n")
    app.run(host=args.host, port=args.port, debug=False)
