"""build_pnl_page.py — render sim_pnl.json into a self-contained HTML artifact.
Pure stdlib. Draws equity curves as inline SVG polylines (no runtime JS needed
for the chart), theme-aware via CSS custom properties.
"""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(ROOT, "data", "sim_pnl.json")
OUT = os.environ.get("OUT_HTML", os.path.join(ROOT, "docs", "pnl_sim.html"))

SERIES = {
    "naive_taker":   ("Taker · buy favorite",     "var(--s-teal)"),
    "maker_fav":     ("Maker · post favorite bid", "var(--s-violet)"),
    "longshot_fade": ("Taker · longshot fade",     "var(--s-amber)"),
    "coinflip_up":   ("Taker · coinflip (Up)",     "var(--s-rose)"),
}


def nice_ticks(lo, hi, n=5):
    span = hi - lo
    if span == 0:
        return [lo]
    raw = span / n
    mag = 10 ** (len(str(int(abs(raw)))) - 1) if raw >= 1 else 1
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if span / step <= n + 1:
            break
    start = (lo // step) * step
    ticks, v = [], start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 6))
        v += step
    return ticks


def polyline(eq, x0, y0, w, h, ymin, ymax, color, width=2.2):
    n = len(eq)
    if n < 2:
        return ""
    xr = w / (n - 1)
    yr = h / (ymax - ymin) if ymax != ymin else 0
    pts = []
    for i, p in enumerate(eq):
        x = x0 + i * xr
        y = y0 + h - (p["eq"] - ymin) * yr
        pts.append(f"{x:.1f},{y:.1f}")
    return (f'<polyline fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round" stroke-linecap="round" '
            f'points="{" ".join(pts)}"/>')


def endpoint_dot(eq, x0, y0, w, h, ymin, ymax, color):
    n = len(eq)
    if n < 1:
        return ""
    xr = w / (n - 1) if n > 1 else 0
    yr = h / (ymax - ymin) if ymax != ymin else 0
    x = x0 + (n - 1) * xr
    y = y0 + h - (eq[-1]["eq"] - ymin) * yr
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{color}"/>'


def chart(curves, names, width=760, height=340, pad_l=64, pad_r=18,
          pad_t=18, pad_b=34):
    w = width - pad_l - pad_r
    h = height - pad_t - pad_b
    allpts = [p["eq"] for nm in names for p in curves[nm]["equity"]]
    ymin, ymax = min(allpts + [0]), max(allpts + [0])
    pad = (ymax - ymin) * 0.08 or 1
    ymin, ymax = ymin - pad, ymax + pad
    maxn = max(len(curves[nm]["equity"]) for nm in names)

    svg = [f'<svg viewBox="0 0 {width} {height}" role="img" '
           f'preserveAspectRatio="xMidYMid meet" class="chart">']
    # y grid + labels
    for t in nice_ticks(ymin, ymax, 5):
        y = pad_t + h - (t - ymin) * (h / (ymax - ymin))
        zero = abs(t) < 1e-9
        svg.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + w}" '
                   f'y2="{y:.1f}" class="{"axis0" if zero else "grid"}"/>')
        svg.append(f'<text x="{pad_l - 8}" y="{y + 3.5:.1f}" '
                   f'class="ylab">{"$" + format(int(round(t)), ",")}</text>')
    # x ticks (trade index)
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        xi = int(round(frac * (maxn - 1)))
        x = pad_l + (xi / (maxn - 1)) * w if maxn > 1 else pad_l
        svg.append(f'<text x="{x:.1f}" y="{pad_t + h + 22:.1f}" '
                   f'class="xlab" text-anchor="middle">{xi}</text>')
    svg.append(f'<text x="{pad_l + w / 2:.1f}" y="{height - 2}" '
               f'class="xtitle" text-anchor="middle">trade number</text>')
    # series
    for nm in names:
        _, color = SERIES[nm]
        eq = curves[nm]["equity"]
        svg.append(polyline(eq, pad_l, pad_t, w, h, ymin, ymax, color))
        svg.append(endpoint_dot(eq, pad_l, pad_t, w, h, ymin, ymax, color))
    svg.append("</svg>")
    return "\n".join(svg)


def stat_tile(nm, c):
    label, color = SERIES[nm]
    final = c["final"]
    sign = "+" if final >= 0 else "−"
    cls = "pos" if final >= 0 else "neg"
    is_maker = nm == "maker_fav"
    third = (f"<div><dt>fill rate</dt><dd class='flag'>{c['fill_rate']*100:.0f}%</dd></div>"
             if is_maker else
             f"<div><dt>avg / trade</dt><dd>{'+' if c['avg_pnl']>=0 else '−'}${abs(c['avg_pnl']):.2f}</dd></div>")
    hit_lab = "hit · if filled" if is_maker else "hit rate"
    note = ('<p class="tile-note">modeled fill (no trade tape) · fills only when price ticks to you</p>'
            if is_maker else "")
    return f"""<div class="tile{' tile-maker' if is_maker else ''}">
  <div class="tile-head"><span class="swatch" style="background:{color}"></span>{label}</div>
  <div class="tile-final {cls}">{sign}${abs(final):,.0f}</div>
  <dl class="tile-stats">
    <div><dt>trades</dt><dd>{c['n']}</dd></div>
    <div><dt>{hit_lab}</dt><dd>{c['hit_rate']*100:.1f}%</dd></div>
    {third}
  </dl>{note}
</div>"""


def decay_section():
    """Render the edge-vs-sample-size trend from data/sim_history.ndjson."""
    hist_path = os.path.join(ROOT, "data", "sim_history.ndjson")
    if not os.path.exists(hist_path):
        return ""
    hist = [json.loads(l) for l in open(hist_path, encoding="utf-8") if l.strip()]
    if len(hist) < 2:
        return ""
    first, last = hist[0], hist[-1]
    rows = []
    for nm in ("naive_taker", "maker_fav", "longshot_fade", "coinflip_up"):
        label, color = SERIES[nm]
        a = first["avg_pnl"].get(nm)
        b = last["avg_pnl"].get(nm)
        if a is None or b is None:
            continue
        toward0 = abs(b) < abs(a)
        arrow = "↓" if toward0 else "↑"
        cls = "decay-toward" if toward0 else "decay-away"
        rows.append(f"""<tr>
      <td><span class="swatch" style="background:{color}"></span>{label}</td>
      <td class="num">{'+' if a>=0 else '−'}${abs(a):.2f}</td>
      <td class="num">{'+' if b>=0 else '−'}${abs(b):.2f}</td>
      <td class="num {cls}">{arrow}</td>
    </tr>""")
    return f"""
<section class="panel decay">
  <div class="panel-head"><h2>Did the edge survive more data?</h2></div>
  <p class="cap">Per-trade PnL of each strategy the first time this was run
  (<strong>{first['matched']} trades</strong>) versus the latest run
  (<strong>{last['matched']} trades</strong>, {last['settled']} settled markets). As the sample
  roughly doubled, every apparent taker/maker edge compressed toward zero &mdash; the maker
  variant most of all. This is the tell that the early numbers were sample/regime noise, not signal.</p>
  <div class="tbl-wrap"><table class="decay-tbl">
    <thead><tr><th>strategy</th><th class="num">avg/trade @ {first['matched']}</th>
      <th class="num">avg/trade @ {last['matched']}</th><th class="num">→0</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
</section>"""


def build():
    d = json.load(open(SIM, encoding="utf-8"))
    curves = d["curves"]
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    decay = decay_section()

    main_chart = chart(curves, ["naive_taker", "maker_fav", "longshot_fade", "coinflip_up"])
    zoom_chart = chart(curves, ["naive_taker", "maker_fav", "longshot_fade"], height=300)
    order = ("naive_taker", "maker_fav", "longshot_fade", "coinflip_up")
    tiles = "\n".join(stat_tile(nm, curves[nm]) for nm in order)
    legend = "".join(
        f'<span class="lg"><span class="swatch" style="background:{c}"></span>{lab}</span>'
        for nm, (lab, c) in SERIES.items())

    html = f"""<article>
<header class="hero">
  <div class="eyebrow">POLYFUNNEL · btc-up-or-down-5m · simulated</div>
  <h1>Hypothetical PnL &mdash; taker vs. maker toy strategies</h1>
  <p class="dek">Replayed against <strong>{d['matched_markets']} real settled markets</strong>
  (of {d['settled_total']} collected, 2026-07-07 &rarr; 07-08), using the real order books,
  the real Chainlink settlement outcomes, and the live-verified 0.07 crypto taker fee.
  Entry is ~60&nbsp;s before each close; each trade stakes a fixed $100 of cost. The
  <span class="ink-violet">maker</span> variant posts at the favorite's bid and pays zero fees &mdash;
  the execution mode the project's research says actually has a shot.</p>
</header>

<aside class="warn" role="note">
  <div class="warn-title">This is not realized PnL. Nothing traded.</div>
  <p>No money has ever been at risk &mdash; the live module is disabled (Phase&nbsp;7, ungated).
  This is a counterfactual replay. Several curves look profitable, but that is the trap this chart exists
  to show: <strong>n&nbsp;=&nbsp;{curves['naive_taker']['n']} trades over ~2 days</strong>, and it
  contradicts the project's own n=200 calibration study that found <em>no</em> naive taker edge.
  The taker edge is best explained by a short trending sample plus an idealized fill
  (top-of-book ask, any size, no slippage &mdash; unrealistic in the final minute). The
  <strong>maker curve is the least-grounded of all</strong>: we collect order books, not the trade tape,
  so its fills are <em>modeled</em>, not observed. Treat the shapes, not the dollars, as the takeaway.</p>
</aside>

<section class="tiles">{tiles}</section>
{decay}
<section class="panel">
  <div class="panel-head">
    <h2>Equity curves &mdash; full scale</h2>
    <div class="legend">{legend}</div>
  </div>
  <p class="cap">The coinflip null (no skill + equal-dollar stakes + a Down-heavy sample) nose-dives,
  which flattens the three favorite-buying curves near zero. That contrast is the point.</p>
  {main_chart}
</section>

<section class="panel">
  <div class="panel-head"><h2>Zoom &mdash; the favorite-buying curves</h2></div>
  <p class="cap">Same data, rescaled. All three drift up, but the paths are jagged and thin.
  The maker curve (violet) has only <strong>{curves['maker_fav']['fills']} fills out of
  {curves['maker_fav']['attempts']} attempts</strong> ({curves['maker_fav']['fill_rate']*100:.0f}%),
  and its win rate <em>conditional on filling</em> is {curves['maker_fav']['hit_rate']*100:.1f}%
  &mdash; below the taker's {curves['naive_taker']['hit_rate']*100:.1f}% on the same favorite.
  That gap is adverse selection: as a maker you fill precisely when the favorite is ticking down.</p>
  {zoom_chart}
</section>

<section class="methods">
  <h2>Assumptions &amp; provenance</h2>
  <ul>
    <li><strong>Data:</strong> live-collected order books (1&nbsp;Hz over each market's final 60&nbsp;s)
      and Chainlink-settled outcomes, <code>data/collect/btc-up-or-down-5m/</code>.</li>
    <li><strong>Taker entry:</strong> best ask of the chosen side from the snapshot nearest
      T&minus;60&nbsp;s (&plusmn;45&nbsp;s tolerance); fill assumed at that price, full size.</li>
    <li><strong>Maker entry &amp; fill proxy:</strong> post a buy at the favorite's best bid at
      T&minus;60&nbsp;s. With no trade tape collected, the fill is <em>modeled</em>: it counts as
      filled iff a later in-window snapshot shows the favorite's best bid trading <em>below</em> the
      posted price (our level got cleared). Unfilled attempts take no position. This is conservative
      and, being a downward-trade-through, it is exactly where adverse selection bites.</li>
    <li><strong>Fee:</strong> taker <code>shares &times; 0.07 &times; p &times; (1&minus;p)</code>,
      crypto_fees_v2, live-verified 2026-07-06 (<code>config/costs.yaml</code>). Maker fee = 0;
      maker rebates would only help and are deliberately <em>not</em> credited (conservative).</li>
    <li><strong>Not modeled:</strong> slippage, partial fills, queue position, latency, capital
      constraints; for the maker, whether a real resting order at that price would truly have filled.
      All of these push the curves down, not up.</li>
    <li><strong>Sample:</strong> {d['matched_markets']} markets, ~2 days &mdash; far below any
      threshold for a deflated-Sharpe survivorship claim (Phase&nbsp;4).</li>
  </ul>
  <p class="gen">Generated {gen} &middot; <code>scripts/sim_pnl.py</code> &rarr; <code>scripts/build_pnl_page.py</code></p>
</section>
</article>"""

    css = open(os.path.join(os.path.dirname(__file__), "_pnl_style.css"),
               encoding="utf-8").read() if os.path.exists(
        os.path.join(os.path.dirname(__file__), "_pnl_style.css")) else ""
    page = f"<style>{css}</style>\n{html}"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote", OUT, f"({len(page)} bytes)")


if __name__ == "__main__":
    build()
