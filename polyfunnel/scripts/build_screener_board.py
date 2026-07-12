#!/usr/bin/env python3
"""Build docs/edge_screener.html (the Edge Board) from docs/edge_screener.json.

Run after scripts/edge_screener.py:
  python3 scripts/build_screener_board.py
Self-contained page (inline CSS, no external requests) — publishable as a
claude.ai Artifact and committable to docs/. Light/dark via token-level
theming; every row deep-links to Polymarket for manual placement.
"""
from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "edge_screener.json"
DEST = ROOT / "docs" / "edge_screener.html"


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def money(x) -> str:
    return f"${x:,.0f}"


def build() -> None:
    data = json.loads(SRC.read_text())
    gen = data.get("generated", "?")
    arbs = data.get("set_arbs", [])
    makers = data.get("maker_yield", [])
    free = data.get("fee_free", [])

    def arb_rows() -> str:
        if not arbs:
            return ('<tr><td colspan="8" class="empty">No set arbitrages at scan '
                    'time — normal; they live seconds and are eaten by fast bots. '
                    'The sweep stays in the rotation because checking is free.</td></tr>')
        out = []
        for h in arbs:
            live = h.get("live_check", "")
            cls = ("ok" if live == "CONFIRMED" else
                   "warn" if "GONE" in live or "one-sided" in live else "")
            depth = h.get("depth_usd")
            out.append(
                f'<tr class="arb" data-ret="{esc(h["ret_pct"])}"'
                f' data-depth="{esc(depth if depth is not None else "")}">'
                f'<td><a href="https://polymarket.com/event/{esc(h["slug"])}"'
                f' target="_blank" rel="noopener">{esc(h["event"])}</a></td>'
                f'<td class="num">{esc(h["side"])} ×{esc(h["n_outcomes"])}</td>'
                f'<td class="num">{h["edge_per_set"]*100:+.1f}¢</td>'
                f'<td class="num">{esc(h["ret_pct"])}%</td>'
                f'<td class="num">{money(depth) if depth is not None else "—"}</td>'
                f'<td class="num profit">—</td>'
                f'<td class="num">{money(h.get("vol24", 0))}</td>'
                f'<td><span class="pill {cls}">{esc(live)}</span></td></tr>')
        return "".join(out)

    def maker_rows() -> str:
        out = []
        for r in makers:
            rebate = r.get("rebate_rate")
            out.append(
                f'<tr><td><a href="https://polymarket.com/market/{esc(r["slug"])}"'
                f' target="_blank" rel="noopener">{esc(r["question"])}</a></td>'
                f'<td class="num">{r["bid"]:.3f} / {r["ask"]:.3f}</td>'
                f'<td class="num">{r["spread"]*100:.1f}¢</td>'
                f'<td class="num">{money(r["vol24"])}</td>'
                f'<td class="num">{money(r["score"])}</td>'
                f'<td class="num">{esc(r.get("fee_rate", 0) or "0")}'
                f'{f" / {rebate}" if rebate else ""}</td></tr>')
        return "".join(out)

    def free_rows() -> str:
        out = []
        for r in free:
            out.append(
                f'<tr><td><a href="https://polymarket.com/market/{esc(r["slug"])}"'
                f' target="_blank" rel="noopener">{esc(r["question"])}</a></td>'
                f'<td class="num">{r["bid"]:.3f} / {r["ask"]:.3f}</td>'
                f'<td class="num">{money(r["vol24"])}</td>'
                f'<td class="num">{money(r["liq"])}</td></tr>')
        return "".join(out)

    built = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    page = f"""<title>Polyfunnel Edge Board</title>
<style>
:root {{
  --bg:#F5F7F6; --surface:#FFFFFF; --ink:#1A2422; --muted:#5A6A66;
  --line:#DDE5E2; --accent:#0E7C66; --good:#1E7B34; --warn:#B0730E;
  --pillbg:#EDF3F1;
}}
@media (prefers-color-scheme: dark) {{ :root {{
  --bg:#10161A; --surface:#182126; --ink:#E4ECE9; --muted:#8DA19B;
  --line:#26333A; --accent:#34C6A4; --good:#4EC46A; --warn:#D89A3C;
  --pillbg:#1F2B31;
}} }}
:root[data-theme="dark"] {{
  --bg:#10161A; --surface:#182126; --ink:#E4ECE9; --muted:#8DA19B;
  --line:#26333A; --accent:#34C6A4; --good:#4EC46A; --warn:#D89A3C;
  --pillbg:#1F2B31;
}}
:root[data-theme="light"] {{
  --bg:#F5F7F6; --surface:#FFFFFF; --ink:#1A2422; --muted:#5A6A66;
  --line:#DDE5E2; --accent:#0E7C66; --good:#1E7B34; --warn:#B0730E;
  --pillbg:#EDF3F1;
}}
body {{ background:var(--bg); color:var(--ink);
  font:15px/1.55 system-ui,'Segoe UI',sans-serif; margin:0; padding:32px 20px; }}
.wrap {{ max-width:1000px; margin:0 auto; }}
header h1 {{ font-size:26px; letter-spacing:-0.02em; margin:0 0 4px; }}
.meta {{ color:var(--muted); font-size:13px; margin-bottom:28px; }}
.meta b {{ color:var(--ink); font-weight:600; }}
section {{ background:var(--surface); border:1px solid var(--line);
  border-radius:6px; padding:20px 22px; margin-bottom:22px; }}
.eyebrow {{ text-transform:uppercase; letter-spacing:0.09em; font-size:11px;
  color:var(--accent); font-weight:700; margin:0 0 2px; }}
h2 {{ font-size:18px; margin:0 0 4px; letter-spacing:-0.01em; }}
.note {{ color:var(--muted); font-size:12.5px; margin:10px 0 0; }}
.tblwrap {{ overflow-x:auto; margin-top:12px; }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
th {{ text-align:left; color:var(--muted); font-weight:600; font-size:11.5px;
  text-transform:uppercase; letter-spacing:0.06em; padding:6px 10px;
  border-bottom:1px solid var(--line); white-space:nowrap; }}
td {{ padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
tr:last-child td {{ border-bottom:none; }}
td.num {{ font-family:ui-monospace,'Cascadia Mono',Consolas,monospace;
  font-variant-numeric:tabular-nums; white-space:nowrap; text-align:right; }}
th.num {{ text-align:right; }}
a {{ color:var(--accent); text-decoration:none; }}
a:hover, a:focus-visible {{ text-decoration:underline; outline:none; }}
.pill {{ background:var(--pillbg); border-radius:999px; padding:2px 9px;
  font-size:11.5px; white-space:nowrap; }}
.pill.ok {{ color:var(--good); font-weight:600; }}
.pill.warn {{ color:var(--warn); }}
.empty {{ color:var(--muted); font-style:italic; }}
footer {{ color:var(--muted); font-size:12px; margin-top:26px; }}
.sizerow {{ display:flex; flex-wrap:wrap; gap:18px; align-items:center; margin-top:10px; }}
.sizerow label {{ font-size:13px; color:var(--muted); display:flex;
  align-items:center; gap:8px; }}
.sizerow input {{ width:90px; font:inherit; font-variant-numeric:tabular-nums;
  color:var(--ink); background:var(--bg); border:1px solid var(--line);
  border-radius:4px; padding:5px 8px; }}
.sizerow input:focus-visible {{ outline:2px solid var(--accent); outline-offset:1px; }}
.sizeout {{ font-size:13.5px; }}
.sizeout b {{ font-family:ui-monospace,Consolas,monospace;
  font-variant-numeric:tabular-nums; color:var(--accent); }}
td.profit {{ color:var(--good); font-weight:600; }}
</style>
<div class="wrap">
<header>
  <h1>Polyfunnel Edge Board</h1>
  <p class="meta">Scan <b>{esc(gen)}</b> · {esc(data.get("n_events"))} top events swept ·
  page built {built} · quotes are cached ~30–60s — <b>always verify the live book
  before placing anything</b>. Manual execution only; nothing here is advice.</p>
</header>

<section class="sizing">
  <p class="eyebrow">Sizing</p>
  <h2>Your numbers</h2>
  <div class="sizerow">
    <label>Bankroll $ <input id="bankroll" type="number" min="0" value="500" inputmode="decimal"></label>
    <label>Max risk per market % <input id="riskpct" type="number" min="0" max="100" value="2" inputmode="decimal"></label>
    <div class="sizeout">Max single-market position: <b id="maxpos">$10</b></div>
  </div>
  <p class="note">The per-market cap exists because of UMA resolution risk — even a
  "sure thing" here can resolve against you. Arb profit below is capped at the
  book's real depth AND your bankroll. Nothing is stored or sent anywhere.</p>
</section>

<section>
  <p class="eyebrow">A · Provable</p>
  <h2>Set arbitrage (negRisk events)</h2>
  <div class="tblwrap"><table>
    <tr><th>Event</th><th class="num">Trade</th><th class="num">Edge/set</th>
        <th class="num">Return</th><th class="num">Depth</th>
        <th class="num">Profit @ your size</th><th class="num">Vol 24h</th><th>Live check</th></tr>
    {arb_rows()}
  </table></div>
  <p class="note">Buy every outcome of a mutually-exclusive event for less than $1
  total (fees included) → locked profit at resolution. Depth = what the thinnest
  leg's top-of-book actually holds. Size to that; never leave a set half-filled —
  a half-filled "arb" is a naked bet.</p>
</section>

<section>
  <p class="eyebrow">B · Structural</p>
  <h2>Maker yield — widest paid spreads</h2>
  <div class="tblwrap"><table>
    <tr><th>Market</th><th class="num">Bid / Ask</th><th class="num">Spread</th>
        <th class="num">Vol 24h</th><th class="num">Score</th><th class="num">Fee / rebate</th></tr>
    {maker_rows()}
  </table></div>
  <p class="note">Score = spread × 24h volume (quoting-revenue proxy, not PnL).
  Risk is adverse selection on news — know why the spread is wide before quoting
  into it. Untested as a strategy (candidate F3).</p>
</section>

<section>
  <p class="eyebrow">C · Hunting ground</p>
  <h2>Fee-free board — no taker fee at all</h2>
  <div class="tblwrap"><table>
    <tr><th>Market</th><th class="num">Bid / Ask</th><th class="num">Vol 24h</th>
        <th class="num">Liquidity</th></tr>
    {free_rows()}
  </table></div>
  <p class="note">The segment the pivot targets: real volume, zero fee wall, UMA
  resolution risk applies (size accordingly). Collector #3 records these books.</p>
</section>

<footer>Generated by <span class="num">scripts/edge_screener.py</span> →
<span class="num">build_screener_board.py</span> · polyfunnel · refresh = re-run the
scan and rebuild; ask Claude or run it locally.</footer>
</div>
<script>
(function () {{
  var bank = document.getElementById('bankroll');
  var pct = document.getElementById('riskpct');
  var out = document.getElementById('maxpos');
  function usd(x) {{
    return '$' + x.toLocaleString(undefined, {{maximumFractionDigits: 2}});
  }}
  function update() {{
    var b = Math.max(0, parseFloat(bank.value) || 0);
    var p = Math.min(100, Math.max(0, parseFloat(pct.value) || 0));
    out.textContent = usd(b * p / 100);
    document.querySelectorAll('tr.arb').forEach(function (tr) {{
      var ret = parseFloat(tr.dataset.ret);
      var depth = parseFloat(tr.dataset.depth);
      var cell = tr.querySelector('.profit');
      if (!cell || isNaN(ret)) return;
      var cap = isNaN(depth) ? b : Math.min(b, depth);
      cell.textContent = cap > 0
        ? usd(cap * ret / 100) + ' on ' + usd(cap)
        : '—';
    }});
  }}
  bank.addEventListener('input', update);
  pct.addEventListener('input', update);
  update();
}})();
</script>
"""
    DEST.write_text(page)
    print(f"wrote {DEST} ({len(page):,} bytes; {len(arbs)} arbs, "
          f"{len(makers)} maker rows, {len(free)} fee-free rows)")


if __name__ == "__main__":
    build()
