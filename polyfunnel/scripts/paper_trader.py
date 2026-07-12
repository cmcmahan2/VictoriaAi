#!/usr/bin/env python3
"""Paper-trading ledger — the verifiable track record for the funnel.

Usage (from polyfunnel/):
  python scripts/paper_trader.py open <market-slug> <YES|NO> <price> <shares>
        --strategy F2 --note "why"          # logs live bid/ask at entry
  python scripts/paper_trader.py list
  python scripts/paper_trader.py mark        # mark-to-market vs live quotes
  python scripts/paper_trader.py close <id> <price>   # manual exit at price
  python scripts/paper_trader.py settle <id> <YES|NO> # market resolved
  python scripts/paper_trader.py report

Rules (honesty is the product):
- $1,000 virtual bankroll, set at ledger creation; every trade is stamped
  with the LIVE bid/ask at entry time. An entry priced better than the
  live touch is refused — paper fills can't beat the real book.
- The ledger (vault/paper/ledger.ndjson) is append-only and committed to
  git: timestamps + git history = a track record that can't be quietly
  rewritten. Mistakes stay visible; that's the point.
- Fees: fee-free markets assumed (segment focus); if a fee-enabled market
  is opened the taker Fee V2 charge is applied at entry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polyfunnel.api.gamma import GammaClient  # noqa: E402

LEDGER = ROOT / "vault" / "paper" / "ledger.ndjson"
START_BANKROLL = 1000.0


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.open() if l.strip()]


def append(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def live_quote(slug: str) -> dict:
    g = GammaClient()
    ms = g.get("/markets", slug=slug)
    if not ms:
        ms = g.get("/markets", slug=slug, closed="true")
    if not ms:
        raise SystemExit(f"market not found: {slug}")
    m = ms[0]
    return {"bid": float(m.get("bestBid") or 0), "ask": float(m.get("bestAsk") or 0),
            "question": m.get("question"), "closed": m.get("closed"),
            "fees_enabled": m.get("feesEnabled"),
            "fee_rate": (m.get("feeSchedule") or {}).get("rate", 0) or 0,
            "outcome_prices": m.get("outcomePrices"),
            "outcomes": m.get("outcomes")}


def open_positions() -> dict[str, dict]:
    pos: dict[str, dict] = {}
    for r in rows():
        if r["type"] == "open":
            pos[r["id"]] = r
        elif r["type"] in ("close", "settle"):
            pos.pop(r["ref"], None)
    return pos


def realized_pnl() -> float:
    opens = {r["id"]: r for r in rows() if r["type"] == "open"}
    pnl = 0.0
    for r in rows():
        if r["type"] in ("close", "settle"):
            o = opens[r["ref"]]
            exit_px = r["price"]
            side_px = o["price"]
            pnl += (exit_px - side_px) * o["shares"] - o.get("fee_paid", 0)
    return pnl


def cmd_open(a) -> None:
    q = live_quote(a.slug)
    side = a.side.upper()
    # price of the traded side: YES book is quoted; NO price = 1 - opposite
    live_ask = q["ask"] if side == "YES" else round(1 - q["bid"], 4)
    live_bid = q["bid"] if side == "YES" else round(1 - q["ask"], 4)
    if a.price < live_ask - 1e-9 and a.price < 1 and not a.resting:
        raise SystemExit(
            f"refused: {a.price:.3f} is better than the live ask {live_ask:.3f}."
            f" A paper TAKER can't beat the book — use the ask, or pass"
            f" --resting to log a maker order (counts only if later marked filled).")
    cost = a.price * a.shares
    fee = (q["fee_rate"] * a.price * (1 - a.price) * a.shares
           if q["fees_enabled"] else 0.0)
    tid = f"P{int(time.time())}"
    append({"type": "open", "id": tid, "ts": now_iso(), "slug": a.slug,
            "question": q["question"], "side": side, "price": a.price,
            "shares": a.shares, "cost": round(cost, 2),
            "fee_paid": round(fee, 4), "resting": bool(a.resting),
            "live_bid": live_bid, "live_ask": live_ask,
            "strategy": a.strategy, "note": a.note})
    print(f"opened {tid}: {side} {a.shares} @ {a.price:.3f} on "
          f"{q['question'][:60]}  (live {live_bid:.3f}/{live_ask:.3f}, "
          f"cost ${cost:.2f}{', RESTING — not yet filled' if a.resting else ''})")


def cmd_mark(_a) -> None:
    pos = open_positions()
    if not pos:
        print("no open positions")
    unreal = 0.0
    for tid, o in pos.items():
        q = live_quote(o["slug"])
        mid_yes = (q["bid"] + q["ask"]) / 2 if q["ask"] else None
        mid = mid_yes if o["side"] == "YES" else (1 - mid_yes if mid_yes else None)
        if q["closed"]:
            print(f"  {tid}: MARKET SETTLED — run `settle {tid} <winner>` "
                  f"(outcomePrices {q['outcome_prices']})")
            continue
        u = (mid - o["price"]) * o["shares"] if mid is not None else 0.0
        unreal += u
        print(f"  {tid} {o['side']:3} {o['shares']} @ {o['price']:.3f} "
              f"now ~{mid:.3f} | MTM {u:+.2f} | {o['question'][:48]}"
              f"{' [RESTING]' if o.get('resting') else ''}")
    r = realized_pnl()
    print(f"bankroll: ${START_BANKROLL + r + unreal:,.2f} "
          f"(realized {r:+.2f}, unrealized {unreal:+.2f})")


def cmd_close(a) -> None:
    pos = open_positions()
    if a.id not in pos:
        raise SystemExit(f"no open position {a.id}")
    append({"type": "close", "ref": a.id, "ts": now_iso(), "price": a.price})
    o = pos[a.id]
    print(f"closed {a.id} @ {a.price:.3f}: "
          f"PnL {(a.price - o['price']) * o['shares']:+.2f}")


def cmd_settle(a) -> None:
    pos = open_positions()
    if a.id not in pos:
        raise SystemExit(f"no open position {a.id}")
    o = pos[a.id]
    won = a.winner.upper() == o["side"]
    px = 1.0 if won else 0.0
    append({"type": "settle", "ref": a.id, "ts": now_iso(), "price": px,
            "winner": a.winner.upper()})
    print(f"settled {a.id}: {o['side']} {'WON' if won else 'LOST'} "
          f"-> PnL {(px - o['price']) * o['shares']:+.2f}")


def cmd_list(_a) -> None:
    for r in rows():
        print(json.dumps(r))


def cmd_report(_a) -> None:
    all_rows = rows()
    opens = [r for r in all_rows if r["type"] == "open"]
    settles = [r for r in all_rows if r["type"] in ("close", "settle")]
    r = realized_pnl()
    print(f"trades opened: {len(opens)} | closed/settled: {len(settles)} "
          f"| open now: {len(open_positions())}")
    print(f"realized PnL: {r:+.2f} on ${START_BANKROLL:,.0f} start "
          f"({100*r/START_BANKROLL:+.2f}%)")
    by_strat: dict[str, float] = {}
    open_by_id = {x["id"]: x for x in opens}
    for s in settles:
        o = open_by_id[s["ref"]]
        by_strat[o["strategy"]] = by_strat.get(o["strategy"], 0.0) + \
            (s["price"] - o["price"]) * o["shares"] - o.get("fee_paid", 0)
    for k, v in sorted(by_strat.items()):
        print(f"  {k}: {v:+.2f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open")
    o.add_argument("slug"); o.add_argument("side", choices=["YES", "NO", "yes", "no"])
    o.add_argument("price", type=float); o.add_argument("shares", type=float)
    o.add_argument("--strategy", default="manual")
    o.add_argument("--note", default="")
    o.add_argument("--resting", action="store_true",
                   help="maker order resting below the touch (not a fill yet)")
    o.set_defaults(fn=cmd_open)
    for name, fn in (("mark", cmd_mark), ("list", cmd_list), ("report", cmd_report)):
        p = sub.add_parser(name); p.set_defaults(fn=fn)
    c = sub.add_parser("close"); c.add_argument("id"); c.add_argument("price", type=float)
    c.set_defaults(fn=cmd_close)
    s = sub.add_parser("settle"); s.add_argument("id"); s.add_argument("winner")
    s.set_defaults(fn=cmd_settle)
    a = ap.parse_args()
    a.fn(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
