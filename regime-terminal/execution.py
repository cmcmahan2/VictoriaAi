"""
execution.py — broker execution layer (paper-first, guarded).

Turns a strategy decision into real (or simulated) broker orders. Works for
equities and crypto via Alpaca; the wheel/options tool has its own options path.

================================  SAFETY  ===================================
Defaults to PAPER + NOT ARMED. A live REAL-MONEY order requires ALL of:
  * mode="live"      (default "paper" = fake money, real market)
  * guardrails.armed=True   (default False -> only logs what it WOULD do)
  * ALPACA_API_KEY / ALPACA_SECRET_KEY in the environment
and even then per-order notional, total exposure, and a symbol allowlist cap it.
There is no way to send a real order by accident. This sandbox cannot reach a
broker, so AlpacaBroker is UNVERIFIED here — test it locally in PAPER first, and
watch it log SAFE/dry-run lines before you ever arm it.
============================================================================
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Account:
    cash: float
    equity: float


@dataclass
class Position:
    symbol: str
    qty: float            # signed: + long, - short
    avg_price: float      # positive entry price


@dataclass
class Order:
    symbol: str
    qty: float            # absolute quantity
    side: str             # 'buy' | 'sell'
    type: str = "market"
    note: str = ""


@dataclass
class Guardrails:
    """Hard limits. Nothing real is sent unless `armed` is explicitly True."""
    max_notional_per_order: float = 5_000.0
    max_total_exposure: float = 20_000.0
    symbol_allowlist: tuple = ()          # empty = any symbol allowed
    armed: bool = False                   # MUST be True to send real orders

    def check(self, order: Order, price: float, current_exposure: float):
        if self.symbol_allowlist and order.symbol not in self.symbol_allowlist:
            return False, f"{order.symbol} not in allowlist"
        if price <= 0:
            return False, "no price"
        notional = abs(order.qty) * price
        if notional > self.max_notional_per_order:
            return False, f"order ${notional:,.0f} > per-order cap ${self.max_notional_per_order:,.0f}"
        if current_exposure + notional > self.max_total_exposure:
            return False, f"exposure ${current_exposure+notional:,.0f} > cap ${self.max_total_exposure:,.0f}"
        return True, "ok"


# --------------------------------------------------------------------------- #
# Brokers
# --------------------------------------------------------------------------- #
class Broker:
    def get_account(self) -> Account: raise NotImplementedError
    def get_position(self, symbol: str) -> Position | None: raise NotImplementedError
    def submit(self, order: Order, price: float | None = None): raise NotImplementedError
    def flatten(self, symbol: str, price: float | None = None): raise NotImplementedError


class MockBroker(Broker):
    """In-memory broker that fills instantly at the given price. For tests/dry runs."""

    def __init__(self, cash: float = 50_000.0):
        self.cash = cash
        self.positions: dict[str, Position] = {}
        self.fills: list[tuple] = []

    def get_account(self) -> Account:
        mkt = sum(p.qty * p.avg_price for p in self.positions.values())
        return Account(cash=self.cash, equity=self.cash + mkt)

    def get_position(self, symbol):
        return self.positions.get(symbol)

    def submit(self, order: Order, price: float | None = None):
        assert price is not None, "MockBroker needs a price"
        signed = order.qty if order.side == "buy" else -order.qty
        pos = self.positions.get(order.symbol)
        old = pos.qty if pos else 0.0
        new = old + signed
        if pos is None or old == 0:
            avg = price
        elif (old > 0) == (signed > 0):                      # adding same direction
            avg = (pos.avg_price * abs(old) + price * abs(signed)) / abs(new)
        elif abs(signed) < abs(old):                          # partial reduce
            avg = pos.avg_price
        else:                                                 # flip through zero
            avg = price
        if abs(new) < 1e-12:
            self.positions.pop(order.symbol, None)
        else:
            self.positions[order.symbol] = Position(order.symbol, new, avg)
        self.cash -= signed * price
        self.fills.append((order.symbol, signed, price))
        return {"status": "filled", "symbol": order.symbol, "qty": signed, "price": price}

    def flatten(self, symbol, price=None):
        pos = self.positions.get(symbol)
        if not pos or pos.qty == 0:
            return {"status": "flat"}
        side = "sell" if pos.qty > 0 else "buy"
        return self.submit(Order(symbol, abs(pos.qty), side, note="flatten"), price=price)


class AlpacaBroker(Broker):
    """Alpaca REST (equities + crypto). mode 'paper'|'live'; dry_run logs only.

    Keys from ALPACA_API_KEY / ALPACA_SECRET_KEY. UNVERIFIED in this sandbox
    (network blocked) — exercise in PAPER on your machine before arming."""

    PAPER = "https://paper-api.alpaca.markets"
    LIVE = "https://api.alpaca.markets"

    def __init__(self, mode: str = "paper", dry_run: bool = True):
        self.mode = mode
        self.dry_run = dry_run
        self.base = self.PAPER if mode == "paper" else self.LIVE
        self.key = os.environ.get("ALPACA_API_KEY")
        self.sec = os.environ.get("ALPACA_SECRET_KEY")

    def _req(self, method, path, **kw):
        import requests
        if not self.key or not self.sec:
            raise RuntimeError("set ALPACA_API_KEY and ALPACA_SECRET_KEY in your environment")
        headers = {"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.sec}
        r = requests.request(method, self.base + path, headers=headers, timeout=15, **kw)
        r.raise_for_status()
        return r.json() if r.text else {}

    def get_account(self):
        a = self._req("GET", "/v2/account")
        return Account(cash=float(a["cash"]), equity=float(a["equity"]))

    def get_position(self, symbol):
        try:
            p = self._req("GET", f"/v2/positions/{symbol}")
            return Position(symbol, float(p["qty"]), float(p["avg_entry_price"]))
        except Exception:
            return None                     # no position (404) or transient error

    def submit(self, order: Order, price=None):
        body = {"symbol": order.symbol, "qty": str(order.qty), "side": order.side,
                "type": order.type, "time_in_force": "gtc"}
        if self.dry_run:
            return {"status": "dry_run", "order": body}
        return self._req("POST", "/v2/orders", json=body)

    def flatten(self, symbol, price=None):
        if self.dry_run:
            return {"status": "dry_run", "flatten": symbol}
        return self._req("DELETE", f"/v2/positions/{symbol}")


# --------------------------------------------------------------------------- #
# Reconcile current position -> target (minimal order), guarded
# --------------------------------------------------------------------------- #
def reconcile(broker: Broker, symbol: str, target_qty: float, price: float,
              guardrails: Guardrails, log: list):
    """Move the position toward target_qty (signed). Sends nothing unless armed."""
    pos = broker.get_position(symbol)
    cur = pos.qty if pos else 0.0
    delta = target_qty - cur
    if abs(delta) < max(1e-9, 1e-6 * max(abs(target_qty), 1)):
        log.append(f"{symbol}: already at target {target_qty:+.4f}")
        return {"action": "none"}
    side = "buy" if delta > 0 else "sell"
    order = Order(symbol, abs(delta), side, note="reconcile")
    ok, why = guardrails.check(order, price, abs(cur) * price)
    if not ok:
        log.append(f"BLOCKED {side} {abs(delta):.4f} {symbol}: {why}")
        return {"action": "blocked", "reason": why}
    if not guardrails.armed:
        log.append(f"[SAFE/not-armed] would {side} {abs(delta):.4f} {symbol} @ {price:,.2f} "
                   f"(cur {cur:+.4f} -> target {target_qty:+.4f})")
        return {"action": "would", "side": side, "qty": abs(delta)}
    res = broker.submit(order, price=price)
    log.append(f"SENT {side} {abs(delta):.4f} {symbol} @ {price:,.2f} -> {res.get('status')}")
    return {"action": "sent", "side": side, "qty": abs(delta), "result": res}
