#!/usr/bin/env python3
"""Trade-tape maker study — answers vault/STRATEGY.md Gate #1: "who fills the maker?"

The 5m longshot-fade thesis = own the heavy favorite as a MAKER (post a resting
BUY, pay zero fee). Our earlier sim showed the edge collapsing under *modeled*
adverse selection. This measures it on the real tape.

Mechanics (verified via collect_trades.py):
  a CLOB `last_trade_price` event's `side` is the TAKER aggressor.
    taker_side = SELL  -> a taker sold into a resting bid -> a maker BUY filled
    taker_side = BUY   -> a taker lifted an ask           -> a maker SELL filled
So every taker=SELL trade is a realized maker-BUY fill at `price` on `outcome`.
A maker who bought `outcome` at price p, held to settlement (0 fee), earns
  pnl_per_share = (1 if outcome==winner else 0) - p.
If fill-conditional win rate < p, adverse selection eats the zero-fee advantage.

Join: trade.slug -> settled winner (btc-updown-5m outcomes.ndjson).
Size-weighted (a maker's PnL scales with filled size). Stdlib-only.

Run:  python scripts/analyze_trades.py
"""
from __future__ import annotations

import glob
import gzip
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECT = os.path.join(ROOT, "data", "collect")
FAV = 0.80          # "heavy favorite" threshold (the longshot-fade zone)


def _open(f):
    return gzip.open(f, "rt", encoding="utf-8") if f.endswith(".gz") else open(f, encoding="utf-8")


def load_winners() -> dict:
    win = {}
    for f in glob.glob(os.path.join(COLLECT, "btc-up-or-down-5m", "*", "outcomes.ndjson")):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("settled") and r.get("winner") in ("Up", "Down"):
                win[r["slug"]] = r["winner"]
    return win


class Bucket:
    __slots__ = ("n", "size", "size_win", "px_size")

    def __init__(self):
        self.n = 0            # trade count
        self.size = 0.0       # total shares
        self.size_win = 0.0   # shares whose side won
        self.px_size = 0.0    # sum(price * size) for size-weighted mean price

    def add(self, price, size, won):
        self.n += 1
        self.size += size
        self.px_size += price * size
        if won:
            self.size_win += size

    def stats(self):
        if self.size == 0:
            return None
        mp = self.px_size / self.size
        wr = self.size_win / self.size
        return {"n": self.n, "shares": round(self.size), "mean_price": round(mp, 4),
                "win_rate": round(wr, 4), "edge": round(wr - mp, 4)}


def analyze():
    win = load_winners()
    # maker-BUY (taker SELL) and maker-SELL (taker BUY), each bucketed by price/10
    mbuy = {i: Bucket() for i in range(10)}
    msell = {i: Bucket() for i in range(10)}
    mbuy_fav, msell_fav = Bucket(), Bucket()
    joined = 0

    for f in glob.glob(os.path.join(COLLECT, "trades", "*", "trades-*.ndjson*")):
        for line in _open(f):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            w = win.get(r.get("slug"))
            if w is None:
                continue
            try:
                price = float(r["price"]); size = float(r["size"])
            except (KeyError, ValueError, TypeError):
                continue
            won = (r.get("outcome") == w)
            joined += 1
            b = min(int(price * 10), 9)
            if r.get("taker_side") == "SELL":       # maker BUY filled at price
                mbuy[b].add(price, size, won)
                if price >= FAV:
                    mbuy_fav.add(price, size, won)
            elif r.get("taker_side") == "BUY":       # maker SELL filled at price
                msell[b].add(price, size, won)
                if price >= FAV:
                    msell_fav.add(price, size, won)

    return {
        "winners": len(win), "joined_trades": joined,
        "maker_buy_by_price": {f"{i/10:.1f}-{(i+1)/10:.1f}": mbuy[i].stats() for i in range(10)},
        "maker_sell_by_price": {f"{i/10:.1f}-{(i+1)/10:.1f}": msell[i].stats() for i in range(10)},
        "maker_buy_favorite": mbuy_fav.stats(),
        "maker_sell_favorite": msell_fav.stats(),
    }


def fmt(res):
    out = ["TRADE-TAPE MAKER STUDY — who fills the maker? (btc-updown-5m)",
           "=" * 64,
           f"settled markets: {res['winners']}   joined trades: {res['joined_trades']:,}",
           "",
           "MAKER BUY fills (taker SELL into a resting bid) — 'own the favorite':",
           "  price bin    n       shares    mean_px  win_rate   edge(=maker PnL/sh, 0 fee)"]
    for k, s in res["maker_buy_by_price"].items():
        if s:
            out.append(f"  {k}   {s['n']:>7} {s['shares']:>10,}   {s['mean_price']:.3f}   "
                       f"{s['win_rate']:.3f}   {s['edge']:+.4f}")
    fav = res["maker_buy_favorite"]
    if fav:
        out += ["",
                f"  >> FAVORITES (price >= {FAV}): mean_px {fav['mean_price']:.3f}, "
                f"win_rate {fav['win_rate']:.3f}  ({fav['n']:,} fills, {fav['shares']:,} sh)",
                f"     maker edge after 0 fee: {fav['edge']*100:+.2f}c / share  "
                f"({'ADVERSE SELECTION' if fav['edge'] < 0 else 'positive'})"]
    out += ["",
            "MAKER SELL fills (taker BUY lifts a resting ask):",
            "  price bin    n       shares    mean_px  win_rate   edge(=maker PnL/sh, 0 fee)"]
    for k, s in res["maker_sell_by_price"].items():
        if s:
            # maker sold at price -> pnl/share = price - win  -> edge = mean_px - win_rate
            e = round(s["mean_price"] - s["win_rate"], 4)
            out.append(f"  {k}   {s['n']:>7} {s['shares']:>10,}   {s['mean_price']:.3f}   "
                       f"{s['win_rate']:.3f}   {e:+.4f}")
    out += ["", "READ: edge = fill-conditional win rate - price. A calibrated market has",
            "edge≈0 for random fills; systematically NEGATIVE maker-BUY edge = you are",
            "filled preferentially when the side is about to lose (adverse selection),",
            "which the zero maker fee cannot rescue."]
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows console is cp1252
    except (AttributeError, ValueError):
        pass
    res = analyze()
    print(fmt(res))
    outp = os.path.join(ROOT, "data", "trade_maker_study.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\nwrote {outp}")
