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
    ap.add_argument("--data-source", choices=["synthetic", "kucoin", "coinbase", "yfinance"], default="kucoin")
    ap.add_argument("--data-ticker", default="BTC-USDT", help="data feed ticker (e.g. BTC-USDT)")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--states", type=int, default=7)
    ap.add_argument("--notional", type=float, default=1000.0, help="$ position size to suggest")
    ap.add_argument("--leverage", type=float, default=config.LEVERAGE, help="leverage you'd use (for margin/risk note)")
    ap.add_argument("--short", action="store_true", help="allow SHORT calls in bear/crash regimes")
    ap.add_argument("--loop", type=int, default=0, help="seconds between checks (0 = run once); beeps on change")
    args = ap.parse_args()
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
