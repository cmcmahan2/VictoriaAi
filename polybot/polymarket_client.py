"""
polymarket_client.py — market discovery, order placement, and P&L.

Two-leg structure: for each 5m window we buy the FAV token (favored side) plus a
smaller HEDGE token (opposite side). `calculate_pnl()` is the single source of
truth for trade economics and is reused verbatim by the backtester.

Live order placement and on-chain market discovery require network + CLOB creds
(py-clob-client, a funded Polygon wallet, API key). Those paths are guarded and
default to dry-run, because:
  * this build targets paper/backtest first;
  * the execution environment may block Polymarket hosts entirely.
Everything the backtester needs (Fill construction, calculate_pnl) is network-free.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import config


@dataclass(frozen=True)
class Market:
    """A single Polymarket BTC 5m up/down market."""
    condition_id: str
    up_token: str          # ERC1155 token id for the UP outcome
    down_token: str        # ERC1155 token id for the DOWN outcome
    window_start: int      # unix seconds (price reference open)
    window_end: int        # unix seconds (resolution time)
    question: str = ""


@dataclass(frozen=True)
class Fill:
    """A simulated/real fill on one token."""
    side: str              # "UP" | "DOWN"
    token: str             # token id
    price: float           # fill price in [0, 1] (already incl. spread/slippage)
    stake: float           # $ spent

    @property
    def shares(self) -> float:
        return self.stake / self.price if self.price > 0 else 0.0


def calculate_pnl(
    fav: Fill | None,
    hedge: Fill | None,
    outcome: str,
    gas_cost: float = config.GAS_COST,
    fee_rate: float = config.POLYMARKET_FEE,
) -> float:
    """
    Net P&L (dollars) of a FAV (+ optional HEDGE) position given the realized
    `outcome` ("UP" or "DOWN"). A token pays $1 if its side wins, else $0.

      leg_pnl = shares * (1 if side == outcome else 0) - stake
      total   = fav_pnl + hedge_pnl - fees - gas
    """
    def leg_pnl(f: Fill | None) -> tuple[float, float]:
        if f is None or f.stake <= 0:
            return 0.0, 0.0
        payout = f.shares if f.side == outcome else 0.0
        return payout - f.stake, f.stake

    fav_pnl, fav_stake = leg_pnl(fav)
    hedge_pnl, hedge_stake = leg_pnl(hedge)
    fees = (fav_stake + hedge_stake) * fee_rate
    gas = gas_cost if (fav_stake + hedge_stake) > 0 else 0.0
    return fav_pnl + hedge_pnl - fees - gas


class PolymarketClient:
    """Thin client. dry_run=True (default) never touches the network."""

    GAMMA = "https://gamma-api.polymarket.com"
    CLOB = "https://clob.polymarket.com"

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    # -- discovery ---------------------------------------------------------- #
    def current_btc_market(self, now: int | None = None) -> Market | None:
        """
        Find the live BTC 5m market. Real path queries Gamma:
            GET {GAMMA}/markets?closed=false&tag=... (filter for the BTC 5m series)
        then resolves the two CLOB token ids. Network-guarded; returns None in
        dry-run so callers fall back to paper/backtest construction.
        """
        if self.dry_run:
            return None
        try:                              # pragma: no cover - needs network + creds
            import requests
            r = requests.get(
                f"{self.GAMMA}/markets",
                params={"closed": "false", "limit": 50},
                timeout=10,
            )
            r.raise_for_status()
            # NOTE: real selection logic (match the BTC 5m series + parse token ids)
            # goes here. Left explicit rather than faked.
            raise NotImplementedError("wire BTC-5m market selection to live Gamma data")
        except Exception:
            return None

    # -- execution ---------------------------------------------------------- #
    def place_order(self, token: str, side: str, price: float, stake: float) -> Fill:
        """Place (or simulate) a buy. dry_run logs intent and returns the Fill."""
        fill = Fill(side=side, token=token, price=price, stake=stake)
        if self.dry_run:
            return fill
        raise NotImplementedError(  # pragma: no cover - needs CLOB creds
            "live placement requires py-clob-client + signer; not enabled"
        )


def floor_window(ts: int, window: int = config.WINDOW_SECONDS) -> int:
    """Start of the 5m window containing ts (aligned to floor(ts/300)*300)."""
    return (ts // window) * window
