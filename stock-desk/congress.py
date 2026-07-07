"""
congress.py — track + copy congressional (and whale) trades.

WHAT'S ACTUALLY OBTAINABLE (investigated)
-----------------------------------------
US lawmakers must disclose trades under the STOCK Act, but:
  * There is NO official real-time API. Capitol Trades (capitoltrades.com) is a
    nice FREE viewer but has no public API and scraping it is fragile / against ToS.
  * The standard FREE programmatic sources are the community datasets:
      - House: https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json
      - Senate: https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json
    (Paid alternatives: Quiver Quantitative, Unusual Whales, FMP.)
  * Disclosures are LATE — often 30-45 days after the trade, sometimes more, and
    amounts are RANGES (e.g. $1k-$15k), not exact. So any copy is delayed and fuzzy.
This module fetches the stock-watcher data (network-guarded; blocked in this
sandbox) and falls back to a small SAMPLE so the logic is demonstrable.

HONEST NOTE: the "politicians beat the market" backtests you see are usually
hindsight-picked single names. Treat this as a *signal source* to research, not a
money printer. Copies are delayed by DISCLOSURE_LAG_DAYS on purpose.
"""
from __future__ import annotations

import argparse
import math
import random
import time
from dataclasses import dataclass

import config

HOUSE_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"


@dataclass
class CongressTrade:
    date: int            # unix seconds of the transaction
    politician: str
    ticker: str
    side: str            # 'buy' | 'sell'
    amount: float        # midpoint of the disclosed range, $


# A few representative rows so the pipeline runs without network (NOT real advice).
SAMPLE_TRADES = [
    CongressTrade(int(time.time()) - 60 * 86400, "Sample McWhale", "NVDA", "buy", 50000),
    CongressTrade(int(time.time()) - 55 * 86400, "Sample McWhale", "MSFT", "buy", 15000),
    CongressTrade(int(time.time()) - 40 * 86400, "Sample McWhale", "AAPL", "buy", 8000),
    CongressTrade(int(time.time()) - 30 * 86400, "Sample McWhale", "NVDA", "sell", 50000),
    CongressTrade(int(time.time()) - 50 * 86400, "Jane Doe-Trader", "TSLA", "buy", 30000),
    CongressTrade(int(time.time()) - 20 * 86400, "Jane Doe-Trader", "TSLA", "sell", 30000),
]

_AMOUNT_MID = {"$1,001 - $15,000": 8000, "$15,001 - $50,000": 32500,
               "$50,001 - $100,000": 75000, "$100,001 - $250,000": 175000,
               "$250,001 - $500,000": 375000, "$1,001 - $5,000": 3000}


def fetch_congress_trades(chamber: str = "house", limit: int = 2000):
    """Fetch + normalize recent disclosures. Raises if blocked (sandbox)."""
    import requests
    url = HOUSE_URL if chamber == "house" else SENATE_URL
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    rows = r.json()
    out = []
    for d in rows[:limit]:
        try:
            tk = (d.get("ticker") or "").strip().upper()
            if not tk or tk in ("--", "N/A"):
                continue
            ts = int(time.mktime(time.strptime(d["transaction_date"][:10], "%Y-%m-%d")))
            typ = (d.get("type") or "").lower()
            side = "buy" if "purchase" in typ or typ == "buy" else "sell"
            amt = _AMOUNT_MID.get(d.get("amount", ""), 8000)
            who = d.get("representative") or d.get("senator") or "unknown"
            out.append(CongressTrade(ts, who, tk, side, amt))
        except Exception:
            continue
    return out


def top_traders(trades, days=120, min_trades=3):
    """Most active recent traders (a proxy for 'currently active', like the video)."""
    cutoff = int(time.time()) - days * 86400
    counts = {}
    for t in trades:
        if t.date >= cutoff:
            counts[t.politician] = counts.get(t.politician, 0) + 1
    return sorted([(p, n) for p, n in counts.items() if n >= min_trades],
                  key=lambda x: x[1], reverse=True)


def copy_signals(trades, politician, lag_days=config.DISCLOSURE_LAG_DAYS):
    """Dated copy signals for one politician, shifted by the disclosure lag (we can
    only act AFTER they disclose)."""
    sig = [(t.date + lag_days * 86400, t.ticker, t.side) for t in trades
           if t.politician == politician]
    return sorted(sig)


# --------------------------------------------------------------------------- #
# Copy backtest (price provider injected; synthetic for the sandbox demo)
# --------------------------------------------------------------------------- #
class SyntheticPrices:
    """Deterministic per-ticker GBM path, so the copy mechanism is demonstrable
    without real price data. SYNTHETIC — the P&L is plumbing, not an edge."""

    def __init__(self, seed=config.SEED, drift=0.0004, vol=0.02):
        self.seed, self.drift, self.vol = seed, drift, vol
        self._cache = {}

    def _path(self, ticker):
        if ticker not in self._cache:
            rng = random.Random(self.seed ^ (hash(ticker) & 0xFFFFFFFF))
            p, path = 100.0, []
            for _ in range(800):                      # ~3y of daily bars
                p *= math.exp(self.drift + self.vol * rng.gauss(0, 1))
                path.append(p)
            self._cache[ticker] = path
        return self._cache[ticker]

    def at(self, ticker, ts):
        path = self._path(ticker)
        day = (int(time.time()) - ts) // 86400          # days ago
        idx = max(0, min(len(path) - 1, len(path) - 1 - day))
        return path[idx]


def copy_backtest(signals, prices, cfg=config):
    """Follow a politician's signals: on a copy-buy, allocate COPY_NOTIONAL at that
    day's price; close on their sell (or at the end). Returns P&L summary."""
    holdings = {}       # ticker -> (shares, entry_price)
    realized = 0.0
    log = []
    for ts, ticker, side in signals:
        px = prices.at(ticker, ts)
        if px <= 0:
            continue
        if side == "buy" and ticker not in holdings:
            sh = cfg.COPY_NOTIONAL / px
            holdings[ticker] = (sh, px)
            log.append((ts, f"BUY {ticker} {sh:.1f}@{px:.2f}"))
        elif side == "sell" and ticker in holdings:
            sh, ep = holdings.pop(ticker)
            pnl = sh * (px - ep)
            realized += pnl
            log.append((ts, f"SELL {ticker} @{px:.2f}  pnl ${pnl:+,.0f}"))
    # mark remaining open positions at the latest price
    unreal = 0.0
    now = int(time.time())
    for ticker, (sh, ep) in holdings.items():
        unreal += sh * (prices.at(ticker, now) - ep)
    invested = cfg.COPY_NOTIONAL * (len([s for s in signals if s[2] == "buy"]) or 1)
    total = realized + unreal
    return {"realized": realized, "unrealized": unreal, "total_pnl": total,
            "return_on_notional": total / max(cfg.COPY_NOTIONAL, 1),
            "open_positions": len(holdings), "log": log}


def main():
    ap = argparse.ArgumentParser(description="Congressional copy-trading (data + backtest)")
    ap.add_argument("--chamber", choices=["house", "senate"], default="house")
    ap.add_argument("--politician", default=None, help="copy this name (default: most active)")
    args = ap.parse_args()

    try:
        trades = fetch_congress_trades(args.chamber)
        src = args.chamber
    except Exception as e:
        print(f"  (live fetch unavailable: {e}) — using SAMPLE data\n")
        trades = SAMPLE_TRADES
        src = "sample"

    tops = top_traders(trades)
    print(f"Most active traders ({src}):")
    for p, n in tops[:6]:
        print(f"   {p:28s} {n} recent trades")
    politician = args.politician or (tops[0][0] if tops else None)
    if not politician:
        print("no traders found."); return

    sigs = copy_signals(trades, politician)
    print(f"\nCopying: {politician}  ({len(sigs)} signals, lagged {config.DISCLOSURE_LAG_DAYS}d)")
    r = copy_backtest(sigs, SyntheticPrices(), config)
    for ts, msg in r["log"][:12]:
        print(f"   {time.strftime('%Y-%m-%d', time.gmtime(ts))}  {msg}")
    print(f"\n total P&L ${r['total_pnl']:+,.0f}  (realized ${r['realized']:+,.0f}, "
          f"open {r['open_positions']})  return-on-notional {r['return_on_notional']*100:+.1f}%")
    if src == "sample" or True:
        print(" !! Prices here are SYNTHETIC — mechanism demo, not edge. Plug in real")
        print("    price data (Alpaca/yfinance) locally for a meaningful copy backtest.")


if __name__ == "__main__":
    main()
