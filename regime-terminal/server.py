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
import os
import sys
import threading
import time

# On Windows the console defaults to cp1252, which can't encode characters like
# the "→" in our banner. Force UTF-8 so output never crashes the server.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from a local .env (next to this file) into the
    environment, without overwriting vars already set. No dependency required.
    Keeps secrets like ANTHROPIC_API_KEY out of the source / git."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
    except FileNotFoundError:
        pass


_load_dotenv()

from flask import Flask, jsonify, request

import paper
from live import load_recent
from market_intel import (analyze_indicators, analyze_regime, build_prompt,
                          call_claude, entry_guidance, fetch_fear_greed,
                          fetch_news, price_levels)

app = Flask(__name__)

# ── Regime cache (stale-while-revalidate) ──────────────────────────────────── #
# analyze_regime() refits the HMM (~3 min). The regime label barely moves on
# hourly bars, so we cache it per (source, days): serve cached instantly, and
# refresh in the background once stale. Only the regime is cached — price, news,
# and Fear & Greed are re-fetched every request and stay live.
_REGIME_TTL  = 600                       # seconds a cached regime is "fresh"
_regime_cache: dict = {}                 # (source, days) -> (timestamp, regime)
_regime_lock = threading.Lock()
_refreshing: set = set()                 # keys with a background refit in flight


def _refit_async(source: str, days: int, bars) -> None:
    """Recompute the regime off the request thread, then update the cache."""
    key = (source, days)
    with _regime_lock:
        if key in _refreshing:
            return
        _refreshing.add(key)

    def _work():
        try:
            regime = analyze_regime(bars)
            _regime_cache[key] = (time.time(), regime)
        except Exception as exc:                       # keep the stale value on failure
            print(f"  [regime] background refit failed for {source}: {exc}")
        finally:
            with _regime_lock:
                _refreshing.discard(key)

    threading.Thread(target=_work, daemon=True).start()


def _cached_regime(source: str, days: int, bars) -> dict:
    key = (source, days)
    hit = _regime_cache.get(key)
    if hit:
        ts, regime = hit
        if time.time() - ts >= _REGIME_TTL:
            _refit_async(source, days, bars)           # stale: refresh, serve stale now
        return regime
    # Cold cache: compute once, synchronously (a single request pays the cost).
    with _regime_lock:
        hit = _regime_cache.get(key)
        if hit:
            return hit[1]
        regime = analyze_regime(bars)
        _regime_cache[key] = (time.time(), regime)
        return regime


def _gather(source: str, days: int) -> dict:
    """Run the full data + analysis pipeline, return a JSON-safe dict."""
    bars = load_recent(source, "BTC-USDT" if source == "kucoin" else "BTC-USD", days)
    if not bars:
        return {"error": f"No data from {source}. Try a different --source."}
    regime = _cached_regime(source, days, bars)
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
        "guidance": entry_guidance(regime, ind, levels, fg),
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


def _spot_price(source: str):
    """Latest BTC price only — fast, no regime fit (used by the paper book)."""
    bars = load_recent(source, "BTC-USDT" if source == "kucoin" else "BTC-USD", 90)
    return bars[-1].close if bars else None


@app.route("/api/portfolio")
def api_portfolio():
    source = request.args.get("source", "kucoin")
    return jsonify(paper.state(_spot_price(source)))


@app.route("/api/order", methods=["POST"])
def api_order():
    body = request.get_json(force=True, silent=True) or {}
    side = body.get("side")
    otype = body.get("type", "market")
    source = body.get("source", "kucoin")
    try:
        qty = float(body.get("qty", 0))
    except (TypeError, ValueError):
        qty = 0.0
    if side not in ("buy", "sell") or qty <= 0:
        return jsonify({"error": "need side 'buy'/'sell' and qty > 0"}), 400
    price = _spot_price(source)
    if not price:
        return jsonify({"error": "no live price available"}), 502
    limit_price = body.get("limit_price")
    if otype == "limit" and not limit_price:
        return jsonify({"error": "limit order needs limit_price"}), 400
    result = paper.place_order(side, qty, otype, price,
                               float(limit_price) if limit_price else None)
    return jsonify({"result": result, "portfolio": paper.state(price)})


@app.route("/api/portfolio/close", methods=["POST"])
def api_close():
    source = (request.get_json(force=True, silent=True) or {}).get("source", "kucoin")
    price = _spot_price(source)
    paper.close_position(price) if price else None
    return jsonify(paper.state(price))


@app.route("/api/portfolio/cancel", methods=["POST"])
def api_cancel():
    paper.cancel_pending()
    source = (request.get_json(force=True, silent=True) or {}).get("source", "kucoin")
    return jsonify(paper.state(_spot_price(source)))


@app.route("/")
def hub():
    return HUB_HTML


@app.route("/btc")
def btc_dashboard():
    return DASHBOARD_HTML


HUB_HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Trading Hub</title>
<style>
  :root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--txt:#c9d1d9;--muted:#8b949e;--accent:#58a6ff;}
  *{box-sizing:border-box;} html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);
    font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
  header{display:flex;align-items:center;gap:10px;height:48px;padding:0 16px;
    border-bottom:1px solid var(--border);background:var(--panel);}
  .brand{font-size:14px;font-weight:700;letter-spacing:.5px;margin-right:8px;}
  .tab{background:#21262d;color:var(--txt);border:1px solid var(--border);border-radius:8px;
    padding:7px 16px;font-size:13px;font-weight:600;cursor:pointer;}
  .tab.active{background:var(--accent);color:#06121f;border-color:var(--accent);}
  .frames{position:absolute;top:48px;left:0;right:0;bottom:0;}
  iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:var(--bg);}
  iframe.hidden{visibility:hidden;z-index:-1;}
</style></head><body>
<header>
  <span class="brand">⚡ TRADING HUB</span>
  <button class="tab" id="tabBtc">₿ BTC Swing</button>
  <button class="tab" id="tabStock">🎯 Stock Hunter</button>
  <span class="muted" style="margin-left:auto;font-size:12px" id="hint"></span>
</header>
<div class="frames">
  <iframe id="btc" src="/btc"></iframe>
  <iframe id="stock" src=""></iframe>
</div>
<script>
  document.getElementById('stock').src = location.protocol+'//'+location.hostname+':5001/';
  const tabs={btc:[document.getElementById('tabBtc'),document.getElementById('btc')],
              stock:[document.getElementById('tabStock'),document.getElementById('stock')]};
  function show(which){
    for(const k in tabs){const t=tabs[k][0],f=tabs[k][1],on=(k===which);
      t.classList.toggle('active',on); f.classList.toggle('hidden',!on);}
    localStorage.setItem('hubTab',which);
    document.getElementById('hint').textContent =
      which==='btc' ? 'localhost:5000/btc · live BTC' : 'localhost:5001 · stock research';
  }
  tabs.btc[0].onclick=function(){show('btc');};
  tabs.stock[0].onclick=function(){show('stock');};
  show(localStorage.getItem('hubTab')||'btc');
</script></body></html>"""


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
  .setup .headline { font-size:13.5px; line-height:1.45; margin:0 0 10px; }
  .setup .entry { font-size:20px; font-weight:700; letter-spacing:.3px; }
  .setup .stop { font-size:13px; color:var(--red); margin-top:2px; }
  .setup ul { margin:10px 0 0; padding-left:0; list-style:none; }
  .setup li { font-size:12.5px; line-height:1.5; padding:5px 0 5px 16px; position:relative;
              border-top:1px solid rgba(255,255,255,.04); color:var(--txt); }
  .setup li::before { content:"›"; position:absolute; left:0; color:var(--accent); font-weight:700; }
  .sizer .inputs { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:6px; }
  .sizer label { display:block; font-size:10px; text-transform:uppercase; letter-spacing:.5px;
                 color:var(--muted); margin-bottom:3px; }
  .sizer input { width:100%; background:#0d1117; color:var(--txt); border:1px solid var(--border);
                 border-radius:6px; padding:6px 8px; font-size:13px; }
  .sizer .out { margin-top:8px; }
  .sizer .out .v { font-weight:600; }
  .sizer .warn { font-size:12px; line-height:1.5; margin-top:8px; color:var(--amber); }
  .sizer .warn.danger { color:var(--red); }
  .trade input { width:90px; background:#0d1117; color:var(--txt); border:1px solid var(--border);
                 border-radius:6px; padding:6px 8px; font-size:13px; }
  .trade .btns { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }
  .trade .btns button { flex:1; min-width:118px; font-size:12.5px; padding:7px 8px; }
  .trade button.buy  { background:rgba(63,185,80,.15); color:var(--green); border-color:rgba(63,185,80,.4); }
  .trade button.sell { background:rgba(248,81,73,.15); color:var(--red);   border-color:rgba(248,81,73,.4); }
  .pnl-pos { color:var(--green); } .pnl-neg { color:var(--red); }
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
    <div class="card setup" id="setupCard">
      <h2>Trade Setup &amp; What To Watch</h2>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span id="setupBias" class="badge neutral">—</span>
        <div style="text-align:right">
          <div class="muted" style="font-size:10px;text-transform:uppercase;letter-spacing:1px">Target entry</div>
          <div class="entry" id="setupEntry">—</div>
          <div class="stop" id="setupStop"></div>
        </div>
      </div>
      <p class="headline" id="setupHeadline">Loading…</p>
      <ul id="setupLook"></ul>
    </div>
    <div class="card sizer" id="sizerCard" style="display:none">
      <h2>Position Sizer</h2>
      <div class="inputs">
        <div><label>Account $</label><input id="szAccount" type="number" min="0" step="100" value="10000"></div>
        <div><label>Risk %</label><input id="szRisk" type="number" min="0" step="0.25" value="1"></div>
        <div><label>Leverage ×</label><input id="szLev" type="number" min="1" step="1" value="2"></div>
      </div>
      <div class="out" id="szOut"></div>
      <div class="warn" id="szWarn"></div>
    </div>
    <div class="card trade" id="tradeCard">
      <h2>Paper Trade <span class="muted" style="text-transform:none;letter-spacing:0">· simulated, no real money</span></h2>
      <div class="row"><span class="k">Equity</span><span id="pfEquity">—</span></div>
      <div class="row"><span class="k">Cash (+ realized)</span><span id="pfCash">—</span></div>
      <div class="row"><span class="k">Position</span><span id="pfPos">flat</span></div>
      <div class="row"><span class="k">Unrealized P&amp;L</span><span id="pfUnreal">—</span></div>
      <div class="muted" id="pfPending" style="margin:6px 0 0"></div>
      <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
        <label class="muted" style="font-size:11px">Qty (BTC)</label>
        <input id="ordQty" type="number" min="0" step="0.0001" value="0">
        <span class="muted" id="ordHint" style="font-size:11px"></span>
      </div>
      <div class="btns" id="ordBtns"></div>
      <div class="muted" id="ordMsg" style="margin-top:8px"></div>
    </div>
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

function szRecalc(){
  const S=window.SETUP, card=document.getElementById('sizerCard');
  if(!S || !S.direction || !S.entry || !S.stop){ card.style.display='none'; return; }
  card.style.display='';
  const acct=parseFloat(document.getElementById('szAccount').value)||0;
  const riskPct=parseFloat(document.getElementById('szRisk').value)||0;
  const lev=Math.max(1, parseFloat(document.getElementById('szLev').value)||1);
  const entry=S.entry, stop=S.stop, long=S.direction==='long';
  const riskUsd=acct*riskPct/100;
  const perUnit=Math.abs(entry-stop);
  const units=perUnit>0 ? riskUsd/perUnit : 0;     // risk-based size: stop-out ≈ risk$
  const oq=document.getElementById('ordQty');       // prefill paper-trade qty from the sizer
  if(oq && document.activeElement!==oq) oq.value=units.toFixed(4);
  const notional=units*entry, margin=notional/lev;
  const liq= long ? entry*(1-1/lev) : entry*(1+1/lev);   // isolated, est. (no fees/maint.)
  const t1= long ? entry+1.5*perUnit : entry-1.5*perUnit;
  const t2= long ? entry+3*perUnit   : entry-3*perUnit;
  const rows=[
    ['Direction', S.direction.toUpperCase()],
    ['Entry / Stop', money(entry)+' / '+money(stop)],
    ['Risk amount', money(riskUsd)+' ('+riskPct+'%)'],
    ['Stop distance', (perUnit/entry*100).toFixed(2)+'%'],
    ['Position size', units.toFixed(4)+' BTC'],
    ['Notional', money(notional)],
    ['Margin req. ('+lev+'×)', money(margin)],
    ['Est. liquidation', money(liq)],
    ['Target 1 (1.5R)', money(t1)+' (+'+money(1.5*riskUsd)+')'],
    ['Target 2 (3R)', money(t2)+' (+'+money(3*riskUsd)+')'],
  ];
  document.getElementById('szOut').innerHTML=rows.map(r=>
    '<div class="row"><span class="k">'+r[0]+'</span><span class="v">'+r[1]+'</span></div>').join('');
  const w=[];
  if(margin>acct) w.push('⚠ Required margin exceeds account — lower size or leverage.');
  if(long ? liq>stop : liq<stop)
    w.push('⚠ Est. liquidation ('+money(liq)+') would hit BEFORE your stop — leverage too high.');
  const wd=document.getElementById('szWarn');
  wd.className='warn'+(w.length?' danger':''); wd.innerHTML=w.join('<br>');
}

function buildOrderButtons(){
  const S=window.SETUP||{}, box=document.getElementById('ordBtns'), hint=document.getElementById('ordHint');
  let html='';
  if(S.direction==='long'){
    const lp=S.hi||S.entry||0;
    html+='<button class="buy" onclick="placeOrder(\'buy\',\'limit\','+lp+')">Limit Buy @ '+money(lp)+'</button>'
         +'<button class="buy" onclick="placeOrder(\'buy\',\'market\')">Market Buy now</button>';
    hint.textContent='qty from sizer';
  } else if(S.direction==='short'){
    const lp=S.lo||S.entry||0;
    html+='<button class="sell" onclick="placeOrder(\'sell\',\'limit\','+lp+')">Limit Sell @ '+money(lp)+'</button>'
         +'<button class="sell" onclick="placeOrder(\'sell\',\'market\')">Market Sell now</button>';
    hint.textContent='qty from sizer';
  } else {
    html+='<button class="buy" onclick="placeOrder(\'buy\',\'market\')">Market Buy</button>'
         +'<button class="sell" onclick="placeOrder(\'sell\',\'market\')">Market Sell</button>';
    hint.textContent='no setup — manual';
  }
  html+='<button onclick="closePos()">Close position</button>'
       +'<button onclick="cancelLimits()">Cancel limits</button>';
  box.innerHTML=html;
}
function renderPortfolio(p){
  if(!p) return;
  document.getElementById('pfEquity').textContent=money(p.equity);
  document.getElementById('pfCash').textContent=money(p.cash);
  const pos=p.position, posEl=document.getElementById('pfPos');
  if(pos && pos.qty){
    posEl.innerHTML='<span class="pnl-'+(pos.qty>0?'pos':'neg')+'">'+(pos.qty>0?'LONG':'SHORT')
      +' '+Math.abs(pos.qty).toFixed(4)+' BTC @ '+money(pos.avg)+'</span>';
  } else posEl.textContent='flat';
  const u=document.getElementById('pfUnreal');
  u.textContent=money(p.unrealized); u.className=(p.unrealized>=0?'pnl-pos':'pnl-neg');
  const pend=p.pending||[];
  document.getElementById('pfPending').innerHTML = pend.length
    ? '⏳ Pending: '+pend.map(o=>o.side+' '+(+o.qty).toFixed(4)+' @ '+money(o.limit)).join(' · ') : '';
}
async function refreshPortfolio(){
  try{ const r=await fetch('/api/portfolio?source='+document.getElementById('source').value);
       renderPortfolio(await r.json()); }catch(e){}
}
async function placeOrder(side,type,limit){
  const qty=parseFloat(document.getElementById('ordQty').value)||0;
  const msg=document.getElementById('ordMsg');
  if(qty<=0){ msg.textContent='Enter a quantity > 0.'; return; }
  msg.textContent='placing…';
  try{
    const body={side:side,type:type,qty:qty,source:document.getElementById('source').value};
    if(type==='limit') body.limit_price=limit;
    const r=await fetch('/api/order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    if(d.error){ msg.textContent='Error: '+d.error; return; }
    const res=d.result||{};
    msg.textContent = res.status==='resting'
      ? '⏳ limit '+side+' '+qty+' BTC resting @ '+money(res.limit)
      : '✓ '+side+' '+qty+' BTC filled @ '+money(res.at);
    renderPortfolio(d.portfolio);
  }catch(e){ msg.textContent='Order failed.'; }
}
async function closePos(){
  const r=await fetch('/api/portfolio/close',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({source:document.getElementById('source').value})});
  renderPortfolio(await r.json()); document.getElementById('ordMsg').textContent='position closed.';
}
async function cancelLimits(){
  const r=await fetch('/api/portfolio/cancel',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({source:document.getElementById('source').value})});
  renderPortfolio(await r.json()); document.getElementById('ordMsg').textContent='pending limits cancelled.';
}

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

  const G=d.guidance;
  if(G){
    const bcls = G.bias==='LONG'?'long':(G.bias==='SHORT'?'avoid':'neutral');
    const bias=document.getElementById('setupBias');
    bias.className='badge '+bcls; bias.textContent=G.bias;
    document.getElementById('setupEntry').textContent=G.target_entry||'—';
    document.getElementById('setupStop').textContent=G.stop_hint?('stop '+G.stop_hint):'';
    document.getElementById('setupHeadline').textContent=G.headline||'';
    document.getElementById('setupLook').innerHTML=(G.look_for||[]).map(s=>'<li>'+s+'</li>').join('');
    window.SETUP = {direction:G.direction, entry:G.entry, stop:G.stop, lo:G.entry_lo, hi:G.entry_hi};
    if(G.direction && G.suggested_leverage && !window.SZ_LEV_TOUCHED)
      document.getElementById('szLev').value=G.suggested_leverage;
    szRecalc();
  }
  buildOrderButtons();

  if(F && F.value!=null){
    document.getElementById('needle').style.left=F.value+'%';
    document.getElementById('fgLabel').textContent=F.label;
    document.getElementById('fgVal').textContent=F.value+'/100';
  } else {
    document.getElementById('fgLabel').textContent='unavailable';
  }

  document.getElementById('news').innerHTML = (d.news||[]).slice(0,8).map(a=>{
     const inner='<span class="src">'+(a.source||'')+'</span> '+a.title;
     return a.url ? '<a href="'+a.url+'" target="_blank" rel="noopener">'+inner+'</a>'
                  : '<span>'+inner+'</span>';
  }).join('') || '<span class="muted">No headlines.</span>';
}

async function refresh(){
  const src=document.getElementById('source').value;
  try{
    const r=await fetch('/api/intel?source='+src+'&days=90');
    render(await r.json());
    refreshPortfolio();
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

// Position sizer: restore saved inputs, persist + recompute on edit.
['szAccount','szRisk','szLev'].forEach(id=>{
  const el=document.getElementById(id), saved=localStorage.getItem(id);
  if(saved!=null && saved!=='') el.value=saved;
  el.addEventListener('input', ()=>{
    if(id==='szLev') window.SZ_LEV_TOUCHED=true;
    localStorage.setItem(id, el.value); szRecalc();
  });
});
if(localStorage.getItem('szLev')!=null) window.SZ_LEV_TOUCHED=true;  // respect a manual leverage

document.getElementById('refresh').onclick=refresh;
document.getElementById('genplan').onclick=genPlan;
document.getElementById('symbol').onchange=e=>makeChart(e.target.value);

makeChart(document.getElementById('symbol').value);
buildOrderButtons();
refreshPortfolio();
refresh();
setInterval(refresh, 300000);   // refresh data panel every 5 min (chart is live on its own)
</script>
</body>
</html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BTC swing trade dashboard")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--source", default="kucoin", help="data source to warm the regime cache for")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--no-warm", action="store_true", help="skip warming the regime cache at startup")
    args = ap.parse_args()

    if not args.no_warm:
        def _warm():
            try:
                _gather(args.source, args.days)
                print(f"  [warm-up] {args.source} regime cached — panel will load instantly.")
            except Exception as exc:
                print(f"  [warm-up] {args.source} skipped: {exc}")
        threading.Thread(target=_warm, daemon=True).start()
        print(f"  Warming regime cache for '{args.source}' in the background (~3 min, one time)…")

    print(f"\n  BTC Swing Intel dashboard → http://{args.host}:{args.port}\n"
          f"  (Ctrl+C to stop)\n")
    app.run(host=args.host, port=args.port, debug=False)
