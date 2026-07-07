"""
paper.py — a tiny persisted PAPER-trading book for the dashboard.

No real money, no exchange, no API keys. It simulates fills so you can practice
the full place-order → manage → close loop against live prices.

  • market orders fill immediately at the current price
  • limit orders rest until price reaches them, then fill at the limit
  • tracks a single net BTC position, realized + unrealized P&L

State persists to paper_state.json (gitignored). Bankroll resets if you delete
that file. This is a simplified margin-style book: cash is your bankroll, it
moves only by realized P&L (it does not model spot cash outlay or fees).
"""
from __future__ import annotations

import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "paper_state.json")
START_CASH = 10_000.0


def _load() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"cash": START_CASH, "realized": 0.0, "position": None,
                "pending": [], "fills": []}


def _save(s: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


def _fill(s: dict, side: str, qty: float, price: float) -> float:
    """Apply a fill to the net position; return realized P&L from the fill."""
    signed = qty if side == "buy" else -qty
    pos = s.get("position")
    realized = 0.0
    if not pos or pos.get("qty", 0) == 0:
        s["position"] = {"qty": signed, "avg": price}
    else:
        pq, pa = pos["qty"], pos["avg"]
        if (pq > 0) == (signed > 0):                      # same side → average in
            new_qty = pq + signed
            pos["avg"] = (pa * abs(pq) + price * abs(signed)) / abs(new_qty)
            pos["qty"] = new_qty
        else:                                             # opposite → close/flip
            closing = min(abs(signed), abs(pq))
            realized = closing * (price - pa) * (1 if pq > 0 else -1)
            new_qty = pq + signed
            if abs(signed) <= abs(pq):
                pos["qty"] = new_qty
                if new_qty == 0:
                    s["position"] = None
            else:                                         # flipped past flat
                pos["qty"] = new_qty
                pos["avg"] = price
    s["cash"] = s.get("cash", START_CASH) + realized
    s["realized"] = s.get("realized", 0.0) + realized
    s["fills"].append({"side": side, "qty": qty, "price": round(price, 2),
                       "realized": round(realized, 2), "ts": int(time.time())})
    return realized


def process_pending(s: dict, price: float | None) -> None:
    """Fill any resting limit orders that the price has reached."""
    if not price:
        return
    still = []
    for o in s.get("pending", []):
        hit = ((o["side"] == "buy" and price <= o["limit"]) or
               (o["side"] == "sell" and price >= o["limit"]))
        if hit:
            _fill(s, o["side"], o["qty"], o["limit"])
        else:
            still.append(o)
    s["pending"] = still


def place_order(side: str, qty: float, otype: str, price: float,
                limit_price: float | None = None) -> dict:
    s = _load()
    if otype == "market":
        _fill(s, side, qty, price)
        result = {"status": "filled", "at": round(price, 2)}
    else:
        oid = int(time.time() * 1000)
        s.setdefault("pending", []).append(
            {"id": oid, "side": side, "qty": qty, "limit": limit_price, "ts": int(time.time())})
        process_pending(s, price)                         # fill now if already marketable
        resting = any(o["id"] == oid for o in s["pending"])
        result = {"status": "resting" if resting else "filled", "limit": limit_price}
    _save(s)
    return result


def close_position(price: float) -> dict:
    s = _load()
    pos = s.get("position")
    if pos and pos.get("qty", 0) != 0:
        _fill(s, "sell" if pos["qty"] > 0 else "buy", abs(pos["qty"]), price)
    _save(s)
    return {"status": "closed"}


def cancel_pending() -> dict:
    s = _load()
    n = len(s.get("pending", []))
    s["pending"] = []
    _save(s)
    return {"status": "cancelled", "count": n}


def reset() -> dict:
    _save({"cash": START_CASH, "realized": 0.0, "position": None, "pending": [], "fills": []})
    return {"status": "reset"}


def state(price: float | None = None) -> dict:
    """Current book, marking the open position to `price`. Also fills resting limits."""
    s = _load()
    if price:
        process_pending(s, price)
        _save(s)
    pos = s.get("position")
    unreal = (price - pos["avg"]) * pos["qty"] if (pos and price) else 0.0
    cash = s.get("cash", START_CASH)
    return {
        "cash": round(cash, 2),
        "realized": round(s.get("realized", 0.0), 2),
        "position": pos,
        "unrealized": round(unreal, 2),
        "equity": round(cash + unreal, 2),
        "pending": s.get("pending", []),
        "fills": s.get("fills", [])[-8:],
        "price": price,
    }
