"""The wheel: CSP -> assignment -> covered calls -> called away, repeat.

A strict per-ticker state machine. Every premium collected lowers the
effective cost basis; the machine tracks it exactly so the trader
always knows the true exit hurdle. Invalid transitions raise — the
journal must never record an impossible sequence.

    CASH --sell_put--> SHORT_PUT --put_assigned--> ASSIGNED
      ^                    |                          |
      |                put_expired               sell_call
      |                    v                          v
      +<-------------------+        ASSIGNED <--call_expired-- SHORT_CALL
      |                                                           |
      +------------------restart()------- CALLED_AWAY <--called_away
"""

from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, Field


class WheelState(str, Enum):
    CASH = "cash"
    SHORT_PUT = "short_put"
    ASSIGNED = "assigned"
    SHORT_CALL = "short_call"
    CALLED_AWAY = "called_away"


class WheelTransitionError(RuntimeError):
    """Raised when an action is illegal in the current state."""


class WheelEvent(BaseModel):
    date: dt.date
    action: str
    detail: str
    cash_flow_per_share: float  # premium received (+), etc.


class WheelPosition(BaseModel):
    """One ticker's wheel lifecycle with exact cost-basis accounting."""

    symbol: str
    state: WheelState = WheelState.CASH
    shares: int = 0
    put_strike: float | None = None
    call_strike: float | None = None
    assignment_strike: float | None = None
    premiums_per_share: float = 0.0  # cumulative, current cycle
    realized_pnl_per_share: float | None = None
    events: list[WheelEvent] = Field(default_factory=list)

    # -- derived ---------------------------------------------------------

    @property
    def effective_cost_basis(self) -> float | None:
        """Assignment strike minus every premium collected this cycle."""
        if self.assignment_strike is None:
            return None
        return self.assignment_strike - self.premiums_per_share

    # -- transitions -----------------------------------------------------

    def _require(self, expected: WheelState, action: str) -> None:
        if self.state != expected:
            raise WheelTransitionError(
                f"{self.symbol}: cannot {action} while {self.state.value} "
                f"(requires {expected.value})"
            )

    def _log(self, date: dt.date, action: str, detail: str, cash: float) -> None:
        self.events.append(
            WheelEvent(date=date, action=action, detail=detail, cash_flow_per_share=cash)
        )

    def sell_put(self, strike: float, credit: float, date: dt.date) -> None:
        self._require(WheelState.CASH, "sell_put")
        self.state = WheelState.SHORT_PUT
        self.put_strike = strike
        self.premiums_per_share += credit
        self._log(date, "sell_put", f"sold {strike:g} put for {credit:.2f}", credit)

    def put_expired(self, date: dt.date) -> None:
        """Put expired worthless: premium kept, back to cash."""
        self._require(WheelState.SHORT_PUT, "put_expired")
        self.state = WheelState.CASH
        self._log(date, "put_expired", f"{self.put_strike:g} put expired worthless", 0.0)
        self.put_strike = None
        # Cycle ended without shares: premiums are realized income.
        self.realized_pnl_per_share = self.premiums_per_share
        self.premiums_per_share = 0.0

    def put_assigned(self, date: dt.date) -> None:
        self._require(WheelState.SHORT_PUT, "put_assigned")
        assert self.put_strike is not None
        self.state = WheelState.ASSIGNED
        self.shares = 100
        self.assignment_strike = self.put_strike
        self._log(
            date, "put_assigned",
            f"assigned 100 shares at {self.put_strike:g}; effective basis "
            f"{self.effective_cost_basis:.2f}",
            0.0,
        )
        self.put_strike = None

    def sell_call(self, strike: float, credit: float, date: dt.date) -> None:
        self._require(WheelState.ASSIGNED, "sell_call")
        self.state = WheelState.SHORT_CALL
        self.call_strike = strike
        self.premiums_per_share += credit
        self._log(
            date, "sell_call",
            f"sold {strike:g} call for {credit:.2f}; effective basis now "
            f"{self.effective_cost_basis:.2f}",
            credit,
        )

    def call_expired(self, date: dt.date) -> None:
        self._require(WheelState.SHORT_CALL, "call_expired")
        self.state = WheelState.ASSIGNED
        self._log(
            date, "call_expired", f"{self.call_strike:g} call expired worthless", 0.0
        )
        self.call_strike = None

    def called_away(self, date: dt.date) -> None:
        """Shares called away: cycle complete, P&L realized."""
        self._require(WheelState.SHORT_CALL, "called_away")
        assert self.call_strike is not None and self.assignment_strike is not None
        pnl = self.call_strike - self.assignment_strike + self.premiums_per_share
        self.realized_pnl_per_share = pnl
        self.state = WheelState.CALLED_AWAY
        self.shares = 0
        self._log(
            date, "called_away",
            f"called away at {self.call_strike:g}; cycle P&L {pnl:+.2f}/share "
            f"(strike gain {self.call_strike - self.assignment_strike:+.2f} + "
            f"premiums {self.premiums_per_share:.2f})",
            0.0,
        )

    def restart(self, date: dt.date) -> None:
        """Begin a fresh cycle after being called away."""
        self._require(WheelState.CALLED_AWAY, "restart")
        self.state = WheelState.CASH
        self.put_strike = None
        self.call_strike = None
        self.assignment_strike = None
        self.premiums_per_share = 0.0
        self._log(date, "restart", "new wheel cycle", 0.0)
