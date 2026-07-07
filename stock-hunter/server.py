"""
server.py — Stock Hunter research dashboard.

NOT an auto-trader. It surfaces the multi-factor screen's top names and gives you
everything to research a pick by hand: live chart, the score breakdown (why it
ranked), fundamentals, analyst view, earnings date, and research links.

  pip install flask yfinance
  python server.py            # http://localhost:5001
  python server.py --refresh  # re-run the hunt on startup (slow), else use picks.json

Routes:
  GET /                     the dashboard
  GET /api/picks            latest ranked picks (from picks.json)
  GET /api/stock/<symbol>   on-demand fundamentals + research detail (yfinance)
  POST /api/hunt            kick off a background re-scan (capped universe for speed)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from flask import Flask, jsonify

import yfinance as yf

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))
PICKS = os.path.join(HERE, "picks.json")

_detail_cache: dict = {}          # symbol -> (ts, data)
_hunt = {"running": False, "msg": "", "ts": 0}


def load_picks() -> dict:
    try:
        with open(PICKS, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"generated": 0, "picks": []}


@app.route("/api/picks")
def api_picks():
    d = load_picks()
    d["hunt"] = _hunt
    return jsonify(d)


@app.route("/api/stock/<symbol>")
def api_stock(symbol: str):
    symbol = symbol.upper()[:8]
    hit = _detail_cache.get(symbol)
    if hit and time.time() - hit[0] < 600:
        return jsonify(hit[1])
    try:
        info = yf.Ticker(symbol).info
    except Exception as exc:
        return jsonify({"symbol": symbol, "error": f"lookup failed: {exc}"})
    px = info.get("currentPrice") or info.get("regularMarketPrice")
    tgt = info.get("targetMeanPrice")
    data = {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector"), "industry": info.get("industry"),
        "price": px,
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"), "forward_pe": info.get("forwardPE"),
        "pb": info.get("priceToBook"),
        "margin": info.get("profitMargins"), "roe": info.get("returnOnEquity"),
        "rev_growth": info.get("revenueGrowth"), "earn_growth": info.get("earningsGrowth"),
        "div_yield": info.get("dividendYield"),
        "wk52_high": info.get("fiftyTwoWeekHigh"), "wk52_low": info.get("fiftyTwoWeekLow"),
        "target": tgt,
        "target_upside": ((tgt / px - 1) if (tgt and px) else None),
        "recommendation": info.get("recommendationKey"),
        "n_analysts": info.get("numberOfAnalystOpinions"),
        "earnings_ts": info.get("earningsTimestamp"),
        "summary": (info.get("longBusinessSummary") or "")[:600],
    }
    _detail_cache[symbol] = (time.time(), data)
    return jsonify(data)


@app.route("/api/hunt", methods=["POST"])
def api_hunt():
    if _hunt["running"]:
        return jsonify(_hunt)

    def _work():
        _hunt.update(running=True, msg="Scanning ~800 liquid names…")
        try:
            subprocess.run([sys.executable, "hunt.py", "--max", "800", "--top", "30",
                            "--json", "picks.json"], cwd=HERE, check=True,
                           env={**os.environ, "PYTHONUTF8": "1"},
                           capture_output=True, timeout=900)
            _hunt.update(msg="Done.", ts=int(time.time()))
        except Exception as exc:
            _hunt.update(msg=f"Hunt failed: {exc}")
        finally:
            _hunt["running"] = False

    threading.Thread(target=_work, daemon=True).start()
    return jsonify(_hunt)


@app.route("/")
def index():
    return DASHBOARD_HTML


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Stock Hunter — Research</title>
<style>
  :root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--txt:#c9d1d9;--muted:#8b949e;
        --green:#3fb950;--red:#f85149;--amber:#d29922;--accent:#58a6ff;}
  *{box-sizing:border-box;} body{margin:0;background:var(--bg);color:var(--txt);
    font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
  header{display:flex;align-items:center;gap:16px;padding:12px 20px;
    border-bottom:1px solid var(--border);background:var(--panel);}
  header h1{font-size:16px;margin:0;letter-spacing:.5px;}
  .muted{color:var(--muted);font-size:12px;} .controls{margin-left:auto;}
  button{background:var(--accent);color:#06121f;border:none;border-radius:6px;
    padding:7px 12px;font-size:13px;font-weight:600;cursor:pointer;} button:disabled{opacity:.5;}
  .wrap{display:flex;height:calc(100vh - 54px);}
  .list{width:430px;min-width:380px;overflow-y:auto;border-right:1px solid var(--border);}
  .detail{flex:1;min-width:0;overflow-y:auto;padding:16px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th{position:sticky;top:0;background:var(--panel);color:var(--muted);text-align:right;
    padding:8px 10px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border);}
  th:nth-child(2){text-align:left;}
  td{padding:8px 10px;text-align:right;border-bottom:1px solid rgba(255,255,255,.04);}
  td:nth-child(2){text-align:left;font-weight:600;}
  tr.row{cursor:pointer;} tr.row:hover{background:#1c2330;} tr.sel{background:#22304a;}
  .scorebar{display:inline-block;height:7px;border-radius:4px;background:var(--accent);vertical-align:middle;}
  .up{color:var(--green);} .down{color:var(--red);}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:14px;}
  .card h2{margin:0 0 10px;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);}
  #tv{height:420px;} .grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;font-size:13px;}
  .grid .k{color:var(--muted);} .row2{display:flex;justify-content:space-between;padding:4px 0;
    border-bottom:1px solid rgba(255,255,255,.04);font-size:13px;}
  .factor{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12.5px;}
  .factor .bar{flex:1;height:8px;background:#21262d;border-radius:4px;overflow:hidden;}
  .factor .fill{height:100%;background:linear-gradient(90deg,#d29922,#3fb950);}
  .factor .lbl{width:140px;color:var(--muted);} .factor .val{width:36px;text-align:right;}
  a.research{color:var(--accent);text-decoration:none;margin-right:14px;font-size:13px;}
  .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;}
  .buy{background:rgba(63,185,80,.15);color:var(--green);} .hold{background:rgba(210,153,34,.15);color:var(--amber);}
  .sell{background:rgba(248,81,73,.15);color:var(--red);}
</style></head><body>
<header>
  <h1>🎯 STOCK HUNTER</h1><span class="muted" id="meta">research dashboard · not auto-trading</span>
  <div class="controls"><button id="refresh">↻ Re-run hunt</button></div>
</header>
<div class="wrap">
  <div class="list"><table id="tbl"><thead><tr>
    <th>#</th><th>Ticker</th><th>Score</th><th>Mom</th><th>52w</th><th>Trend</th><th>P/E</th>
  </tr></thead><tbody id="rows"><tr><td colspan="7" class="muted" style="padding:16px">Loading picks…</td></tr></tbody></table></div>
  <div class="detail" id="detail"><p class="muted">Select a stock on the left to research it.</p></div>
</div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>
function money(x){return x==null?'—':'$'+Number(x).toLocaleString(undefined,{maximumFractionDigits:2});}
function pct(x){return x==null?'—':(x>=0?'+':'')+(x*100).toFixed(1)+'%';}
function big(x){if(x==null)return '—';const b=x/1e9;return b>=1?'$'+b.toFixed(1)+'B':'$'+(x/1e6).toFixed(0)+'M';}
let PICKS=[];

async function loadPicks(){
  const d=await (await fetch('/api/picks')).json();
  PICKS=d.picks||[];
  const when=d.generated?new Date(d.generated*1000).toLocaleString():'—';
  document.getElementById('meta').textContent='research dashboard · '+PICKS.length+' picks · scanned '+when;
  const rows=PICKS.map((p,i)=>{
    const trend=p.above_200?'<span class="up">↑200</span>':'<span class="down">&lt;200</span>';
    const w=Math.max(4,Math.round((p.score||0)*0.7));
    return '<tr class="row" data-sym="'+p.symbol+'" onclick="pick(this,\''+p.symbol+'\')">'
      +'<td class="muted">'+(i+1)+'</td><td>'+p.symbol+'</td>'
      +'<td>'+Math.round(p.score)+' <span class="scorebar" style="width:'+w+'px"></span></td>'
      +'<td>'+pct(p.mom)+'</td><td>'+Math.round((p.rs_52w||0)*100)+'%</td>'
      +'<td>'+trend+'</td><td>'+(p.pe?Math.round(p.pe):'—')+'</td></tr>';
  }).join('');
  document.getElementById('rows').innerHTML=rows||'<tr><td colspan="7" class="muted" style="padding:16px">No picks yet — click “Re-run hunt”.</td></tr>';
}

function factorRow(label,val){
  val=Math.max(0,Math.min(100,val||0));
  return '<div class="factor"><span class="lbl">'+label+'</span><span class="bar"><span class="fill" style="width:'+val+'%"></span></span><span class="val">'+Math.round(val)+'</span></div>';
}

async function pick(el,sym){
  document.querySelectorAll('tr.row').forEach(r=>r.classList.remove('sel'));
  if(el)el.classList.add('sel');
  const p=PICKS.find(x=>x.symbol===sym)||{};
  const det=document.getElementById('detail');
  det.innerHTML='<p class="muted">Loading '+sym+'…</p>';
  const d=await (await fetch('/api/stock/'+sym)).json();
  if(d.error){det.innerHTML='<div class="card"><h2>'+sym+'</h2><p class="muted">'+d.error+'</p></div>';return;}
  const rec=(d.recommendation||'').toLowerCase();
  const recCls=rec.includes('buy')?'buy':rec.includes('sell')||rec.includes('underperform')?'sell':'hold';
  det.innerHTML=
    '<div class="card"><h2>'+d.symbol+' — '+(d.name||'')+'</h2>'
    +'<div class="muted" style="margin-bottom:8px">'+(d.sector||'')+(d.industry?' · '+d.industry:'')+' · '+big(d.market_cap)+'</div>'
    +'<div id="tv"></div></div>'
    +'<div class="card"><h2>Why it ranked (hunter score '+Math.round(p.score||0)+')</h2>'
      +factorRow('Momentum',p.mom!=null?Math.min(100,50+p.mom*100):50)
      +factorRow('52-week strength',(p.rs_52w||0)*100)
      +factorRow('Quality',p.quality)
      +factorRow('Value',p.value)
      +'<div class="muted" style="margin-top:6px">Trend: '+(p.above_200?'above':'below')+' 200-day MA · momentum '+pct(p.mom)+'</div>'
    +'</div>'
    +'<div class="card"><h2>Fundamentals</h2><div class="grid">'
      +'<div class="row2"><span class="k">Price</span><span>'+money(d.price)+'</span></div>'
      +'<div class="row2"><span class="k">P/E (fwd)</span><span>'+(d.pe?d.pe.toFixed(1):'—')+(d.forward_pe?' ('+d.forward_pe.toFixed(1)+')':'')+'</span></div>'
      +'<div class="row2"><span class="k">Profit margin</span><span>'+pct(d.margin)+'</span></div>'
      +'<div class="row2"><span class="k">ROE</span><span>'+pct(d.roe)+'</span></div>'
      +'<div class="row2"><span class="k">Rev growth</span><span>'+pct(d.rev_growth)+'</span></div>'
      +'<div class="row2"><span class="k">Earnings growth</span><span>'+pct(d.earn_growth)+'</span></div>'
      +'<div class="row2"><span class="k">52w range</span><span>'+money(d.wk52_low)+' – '+money(d.wk52_high)+'</span></div>'
      +'<div class="row2"><span class="k">Div yield</span><span>'+pct(d.div_yield)+'</span></div>'
    +'</div></div>'
    +'<div class="card"><h2>Analyst view</h2><div class="grid">'
      +'<div class="row2"><span class="k">Rating</span><span class="pill '+recCls+'">'+(d.recommendation||'—')+'</span></div>'
      +'<div class="row2"><span class="k"># analysts</span><span>'+(d.n_analysts||'—')+'</span></div>'
      +'<div class="row2"><span class="k">Target</span><span>'+money(d.target)+'</span></div>'
      +'<div class="row2"><span class="k">Upside</span><span class="'+((d.target_upside||0)>=0?'up':'down')+'">'+pct(d.target_upside)+'</span></div>'
      +'<div class="row2"><span class="k">Next earnings</span><span>'+(d.earnings_ts?new Date(d.earnings_ts*1000).toLocaleDateString():'—')+'</span></div>'
    +'</div></div>'
    +'<div class="card"><h2>About</h2><p style="font-size:13px;line-height:1.5;color:var(--txt)">'+(d.summary||'—')+'…</p>'
      +'<div style="margin-top:10px">'
      +'<a class="research" target="_blank" href="https://finance.yahoo.com/quote/'+sym+'">Yahoo</a>'
      +'<a class="research" target="_blank" href="https://finviz.com/quote.ashx?t='+sym+'">Finviz</a>'
      +'<a class="research" target="_blank" href="https://stocktwits.com/symbol/'+sym+'">StockTwits</a>'
      +'<a class="research" target="_blank" href="https://www.tradingview.com/symbols/'+sym+'/news/">News</a>'
      +'</div></div>';
  new TradingView.widget({container_id:'tv',autosize:true,symbol:sym,interval:'D',
    timezone:'Etc/UTC',theme:'dark',style:'1',locale:'en',hide_side_toolbar:true,
    studies:['MASimple@tv-basicstudies']});
}

async function doHunt(){
  const b=document.getElementById('refresh');b.disabled=true;b.textContent='Scanning…';
  await fetch('/api/hunt',{method:'POST'});
  const poll=setInterval(async()=>{
    const d=await (await fetch('/api/picks')).json();
    if(!d.hunt||!d.hunt.running){clearInterval(poll);b.disabled=false;b.textContent='↻ Re-run hunt';loadPicks();}
  },4000);
}
document.getElementById('refresh').onclick=doHunt;
loadPicks();
</script></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Stock Hunter research dashboard")
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    print(f"\n  Stock Hunter research dashboard → http://{args.host}:{args.port}\n"
          f"  (Ctrl+C to stop)\n")
    app.run(host=args.host, port=args.port, debug=False)
