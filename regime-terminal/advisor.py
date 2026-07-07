"""
advisor.py — tells YOU what to do; you place the trade yourself.

This is the manual-trading mode: NO broker, NO API keys, NO exchange permissions.
It just reads the market and prints a clear, glanceable call — GO LONG / GO SHORT /
CLOSE / WAIT — with a suggested size and stop. Because *you* click buy/sell, it
works with ANY platform (KuCoin, Kraken, Coinbase, ...) and sidesteps every
Canada/API-access problem entirely. A human in the loop is the safest guardrail there is.

Examples
  # one read, right now, off live KuCoin BTC (allow short calls):
  python advisor.py --data-source kucoin --data-ticker BTC-USDT --notional 1000 --short

  # sit here and let it re-check every 5 min, beeping only when the call CHANGES:
  python advisor.py --data-source kucoin --data-ticker BTC-USDT --notional 1000 --short --loop 300

Advisory only — every order is your decision and your risk. Leverage cuts both ways.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time

import config
from live import load_recent
from strategy import Indicators
from terminal import current_read

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".advisor_state.json")
W = 60


def _load_last():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_last(action, price):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"action": action, "price": price, "ts": time.time()}, f)
    except Exception:
        pass


JOURNAL_COLS = ["time_utc", "ts", "action", "price", "regime", "confidence",
                "signal", "notional", "leverage", "stop"]


def _append_journal(path, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=JOURNAL_COLS)
        if new:
            w.writeheader()
        w.writerow(row)


def _ascii_curve(pct, height=9, width=60):
    """Tiny ASCII equity curve from a list of cumulative % returns. Pure ASCII so it
    renders in any terminal (incl. Windows cmd). Marks the 0% breakeven line."""
    if len(pct) < 2:
        return "  (need >=2 points to draw a curve)"
    if len(pct) > width:                                   # downsample to fit
        idx = [round(i * (len(pct) - 1) / (width - 1)) for i in range(width)]
        pts = [pct[i] for i in idx]
    else:
        pts = pct
    lo, hi = min(pts + [0.0]), max(pts + [0.0])            # always include breakeven
    rng = (hi - lo) or 1.0
    grid = [[" "] * len(pts) for _ in range(height)]
    zero_row = height - 1 - round((0.0 - lo) / rng * (height - 1))
    for c, v in enumerate(pts):
        grid[height - 1 - round((v - lo) / rng * (height - 1))][c] = "*"
    lines = []
    for r in range(height):
        row = "".join(grid[r])
        if r == zero_row:
            row = "".join(ch if ch != " " else "-" for ch in row)   # breakeven baseline
            label = "  +0.0%"
        elif r == 0:
            label = f"{hi:+6.1f}%"
        elif r == height - 1:
            label = f"{lo:+6.1f}%"
        else:
            label = " " * 7
        lines.append("  " + label + " |" + row)
    lines.append("  " + " " * 7 + " +" + "-" * len(pts))
    lines.append("  " + " " * 9 + "oldest -> newest")
    return "\n".join(lines)


def review_journal(path, show_equity=False):
    """Score how the logged calls would have done: hold each call's position until
    the next call, at that call's leverage. Compounded, directional, leverage-applied."""
    if not os.path.exists(path):
        print(f"no journal at {path} yet — run with --journal {path} first.")
        return
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2:
        print(f"{len(rows)} call(s) logged — need at least 2 to score a closed leg.")
        return
    eq, legs, curve = 1.0, [], [1.0]
    for a, b in zip(rows, rows[1:]):
        p0, p1 = float(a["price"]), float(b["price"])
        lev = float(a.get("leverage") or 1)
        d = {"GO LONG": 1, "GO SHORT": -1}.get(a["action"], 0)   # CLOSE/WAIT = flat
        r = d * (p1 - p0) / p0 * lev if p0 else 0.0
        eq *= 1 + r
        curve.append(eq)
        if d:
            legs.append(r)
    wins = sum(1 for r in legs if r > 0)
    bar = "=" * W
    print("\n".join([
        "", bar, f"  JOURNAL REVIEW  ({path})", bar,
        f"  calls logged     : {len(rows)}   (oldest {rows[0]['time_utc']} UTC)",
        f"  positions taken  : {len(legs)} long/short legs (CLOSE/WAIT = flat, skipped)",
        f"  win rate         : {wins}/{len(legs)} = {(100*wins/len(legs)) if legs else 0:.0f}%",
        f"  best / worst leg : {max(legs)*100:+.1f}% / {min(legs)*100:+.1f}%" if legs else "  best / worst leg : n/a",
        f"  TOTAL (compounded, {('%g' % float(rows[0].get('leverage') or 1))}x-ish): {(eq-1)*100:+.1f}%",
        "  (hypothetical — ignores fees, funding, slippage, and intra-leg stops;",
        "   the most recent call is still open and not scored)", bar])
    )
    if show_equity:
        print(_ascii_curve([(v - 1) * 100 for v in curve]))
        print(bar)


def advise(args):
    bars = load_recent(args.data_source, args.data_ticker, args.days)
    cur = current_read(bars, config, allow_short=args.short)
    price = cur["price"]
    head = cur["signal"].split(" ")[0]                    # LONG / SHORT / FLAT / NEUTRAL

    # volatility-based suggested stop (range_med ~ typical bar range, in % of price)
    ind = Indicators(bars, config)
    vol = (ind.range_med[-1] or ind.range[-1] or 0.0)     # fractional, e.g. 0.022 = 2.2%
    stop_dist = max(vol, 0.005) * 1.8 * price             # ~1.8x typical range, floor 0.5%

    units = (args.notional / price) if price > 0 else 0.0
    lev = max(args.leverage, 1.0)
    margin = args.notional / lev

    action, do, stop = {
        "LONG":    ("GO LONG",  "buy / open long",                 price - stop_dist),
        "SHORT":   ("GO SHORT", "sell / open short",               price + stop_dist),
        "FLAT":    ("CLOSE",    "exit any BTC position, sit in cash", None),
        "NEUTRAL": ("WAIT",     "no new entry; hold existing only",   None),
    }.get(head, ("WAIT", "no clear edge — wait", None))

    passes = [n for n, ok in cur["checks"] if ok]
    fails = [n for n, ok in cur["checks"] if not ok]

    last = _load_last()
    changed = bool(last) and last.get("action") != action
    first = not last
    _save_last(action, price)

    logged = bool(args.journal) and (first or changed)        # journal flips only, not every tick
    if logged:
        _append_journal(args.journal, {
            "time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "ts": f"{time.time():.0f}",
            "action": action, "price": f"{price:.2f}", "regime": cur["name"],
            "confidence": f"{cur['confidence']:.3f}", "signal": cur["signal"],
            "notional": f"{args.notional:.0f}", "leverage": f"{lev:g}",
            "stop": (f"{stop:.2f}" if stop is not None else "")})

    bar = "=" * W
    out = ["", bar,
           f"  BTC ADVISOR   {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC",
           bar,
           f"  PRICE   : ${price:,.2f}",
           f"  REGIME  : {cur['name']} ({cur['confidence']*100:.0f}% confidence)",
           f"  SIGNAL  : {cur['signal']}",
           "",
           f"  >>> DO THIS NOW (manual, on your exchange):",
           f"      ACTION : {action}  ({do})"]
    if stop is not None:
        out += [f"      SIZE   : ~${args.notional:,.0f} exposure  (~{units:.5f} BTC)",
                f"               margin ~${margin:,.0f} at {lev:g}x leverage",
                f"      STOP   : ${stop:,.2f}  ({(stop-price)/price*100:+.1f}% from here)"]
    out += ["",
            f"  WHY pass: {', '.join(passes) or '(none)'}",
            f"      fail: {', '.join(fails) or '(none)'}"]
    if stop is not None and lev > 1:
        out.append(f"  RISK: at {lev:g}x, ~{100/lev:.0f}% against you ~= liquidation; your "
                   f"stop is ~{abs(stop-price)/price*100:.1f}% out, well inside.")
    out.append("  (advisory only — your decision, your risk)")
    if logged:
        out.append(f"  logged this flip -> {args.journal}")
    out.append("-" * W)
    if first:
        out.append("  (first run — baseline saved; future runs flag changes)")
    elif changed:
        out.append(f"  *** CALL CHANGED:  was {last.get('action')}  ->  now {action}  ***")
    else:
        out.append(f"  no change since last check (still {action})")
    out.append(bar)

    text = "\n".join(out)
    if changed and args.loop:                             # ring the terminal bell on a change
        text = "\a" + text
    print(text)


def main():
    ap = argparse.ArgumentParser(description="Manual-trading advisor — it tells you, you trade.")
    ap.add_argument("--data-source", choices=["synthetic", "kucoin", "coinbase", "yfinance", "github"], default="kucoin")
    ap.add_argument("--data-ticker", default="BTC-USDT", help="data feed ticker (e.g. BTC-USDT)")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--states", type=int, default=7)
    ap.add_argument("--notional", type=float, default=1000.0, help="$ position size to suggest")
    ap.add_argument("--leverage", type=float, default=config.LEVERAGE, help="leverage you'd use (for margin/risk note)")
    ap.add_argument("--short", action="store_true", help="allow SHORT calls in bear/crash regimes")
    ap.add_argument("--loop", type=int, default=0, help="seconds between checks (0 = run once); beeps on change")
    ap.add_argument("--journal", metavar="CSV", help="append each call (on a flip) to this CSV file")
    ap.add_argument("--review", metavar="CSV", help="score a journal CSV's hypothetical P&L and exit")
    ap.add_argument("--equity", action="store_true", help="with --review, draw an ASCII equity curve")
    args = ap.parse_args()
    if args.review:
        review_journal(args.review, show_equity=args.equity)
        return
    config.N_STATES = max(2, min(args.states, 12))
    config.HMM_N_INIT = 3

    if args.loop > 0:
        print(f"Advising every {args.loop}s (Ctrl-C to stop). You place the trades.")
        try:
            while True:
                advise(args)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            print("stopped.")
    else:
        advise(args)


if __name__ == "__main__":
    main()
