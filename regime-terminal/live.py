"""
live.py — one live decision cycle for the Regime Terminal (paper-first).

Detects the CURRENT regime from the latest data, turns it into a target position
(long in a bull regime, short in bear/crash if --short, otherwise flat), and
reconciles your broker to that target. Built to be run on a schedule (Windows
Task Scheduler / cron) or with --loop for a self-running bot.

SAFE BY DEFAULT: paper broker, NOT armed -> it only prints the trades it WOULD
make. Real orders need --broker alpaca --arm AND ALPACA keys in your env, and are
still capped by --max-notional / --max-exposure.

Examples
  # dry test of the whole cycle on fake data + fake broker:
  python live.py --broker mock --data-source synthetic --symbol BTC/USD --short

  # paper-trade live KuCoin BTC against an Alpaca PAPER account (logs only until --arm):
  python live.py --broker alpaca --mode paper --data-source kucoin \
                 --data-ticker BTC-USDT --symbol BTC/USD --notional 5000 --short
  # ...add --arm once you've watched it behave and trust it.
"""
from __future__ import annotations

import argparse
import time

import config
from execution import AlpacaBroker, Guardrails, MockBroker, reconcile
from terminal import current_read


def load_recent(source, ticker, days):
    if source == "synthetic":
        from data import synthetic_ohlcv
        return synthetic_ohlcv(days=days, drift_scale=0.3)[0]
    from data import get_bars
    return get_bars(ticker, days, source=source)


def decide_target(cur, price, notional, allow_short, cfg):
    """Map the current regime/signal to a signed target quantity."""
    stance, conf, n = cur["stance"], cur["confidence"], cur["n_pass"]
    direction = 0
    if stance == "long" and conf >= cfg.MIN_REGIME_CONFIDENCE and n >= cfg.CONFIRMATIONS_REQUIRED:
        direction = +1
    elif allow_short and stance == "avoid" and conf >= cfg.MIN_REGIME_CONFIDENCE:
        direction = -1
    units = (notional / price) if price > 0 else 0.0
    return direction * units


def cycle(args, broker, guardrails):
    bars = load_recent(args.data_source, args.data_ticker, args.days)
    cur = current_read(bars, config)
    price = cur["price"]
    target = decide_target(cur, price, args.notional, args.short, config)
    if "/" not in args.symbol:                  # equities trade in whole shares
        target = float(int(target))
    log = []
    log.append(f"regime={cur['name']} ({cur['confidence']*100:.0f}%)  "
               f"signal={cur['signal'].split(' ')[0]}  confirms={cur['n_pass']}/8  px={price:,.2f}")
    log.append(f"target {args.symbol}: {target:+.4f} units (${abs(target)*price:,.0f} notional)")
    reconcile(broker, args.symbol, target, price, guardrails, log)
    try:
        acct = broker.get_account()
        log.append(f"account: cash ${acct.cash:,.0f}  equity ${acct.equity:,.0f}")
    except Exception as e:
        log.append(f"account: (unavailable: {e})")
    print(time.strftime("[%Y-%m-%d %H:%M:%S] ") + "  |  ".join(log))


def main():
    ap = argparse.ArgumentParser(description="Regime Terminal live cycle (paper-first)")
    ap.add_argument("--symbol", default="BTC/USD", help="broker symbol (e.g. BTC/USD, AAPL)")
    ap.add_argument("--data-source", choices=["synthetic", "kucoin", "yfinance"], default="synthetic")
    ap.add_argument("--data-ticker", default="BTC-USDT", help="data feed ticker (e.g. BTC-USDT)")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--states", type=int, default=7)
    ap.add_argument("--notional", type=float, default=5000.0, help="$ exposure when in a position")
    ap.add_argument("--short", action="store_true", help="allow shorting bear/crash regimes")
    ap.add_argument("--broker", choices=["mock", "alpaca"], default="mock")
    ap.add_argument("--mode", choices=["paper", "live"], default="paper")
    ap.add_argument("--arm", action="store_true", help="ACTUALLY send orders (default: log only)")
    ap.add_argument("--max-notional", type=float, default=5000.0)
    ap.add_argument("--max-exposure", type=float, default=20000.0)
    ap.add_argument("--loop", type=int, default=0, help="seconds between cycles (0 = run once)")
    args = ap.parse_args()
    config.N_STATES = max(2, min(args.states, 12))
    config.HMM_N_INIT = 3

    if args.broker == "alpaca":
        broker = AlpacaBroker(mode=args.mode, dry_run=not args.arm)
        if args.mode == "live" and args.arm:
            print("!! LIVE + ARMED: real orders will be sent. Ctrl-C now if unintended. !!")
    else:
        broker = MockBroker()                   # local play-money broker

    guardrails = Guardrails(max_notional_per_order=args.max_notional,
                            max_total_exposure=args.max_exposure,
                            symbol_allowlist=(args.symbol,), armed=args.arm)

    if args.loop > 0:
        print(f"Looping every {args.loop}s (Ctrl-C to stop). armed={args.arm} mode={args.mode}")
        try:
            while True:
                cycle(args, broker, guardrails)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            print("stopped.")
    else:
        cycle(args, broker, guardrails)


if __name__ == "__main__":
    main()
