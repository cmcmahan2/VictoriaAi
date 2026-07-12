"""Pydantic domain models for market data.

All downstream analytics consume these models, never raw provider
payloads, so swapping yfinance for a paid provider only touches
``quantdesk.data.provider``.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OptionType = Literal["call", "put"]


class Quote(BaseModel):
    """Spot quote for an underlying."""

    symbol: str
    price: float = Field(gt=0)
    bid: float | None = None
    ask: float | None = None
    previous_close: float | None = None
    timestamp: dt.datetime

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class Bar(BaseModel):
    """One daily OHLCV bar."""

    date: dt.date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)


class PriceHistory(BaseModel):
    """Daily bar history, oldest first."""

    symbol: str
    bars: list[Bar]

    @property
    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    @property
    def opens(self) -> list[float]:
        return [b.open for b in self.bars]

    @property
    def highs(self) -> list[float]:
        return [b.high for b in self.bars]

    @property
    def lows(self) -> list[float]:
        return [b.low for b in self.bars]

    @property
    def dates(self) -> list[dt.date]:
        return [b.date for b in self.bars]


class OptionContract(BaseModel):
    """A single listed option contract as quoted by the provider.

    ``implied_volatility`` is the provider's own IV figure when present;
    QuantDesk recomputes IV from mid price via its own solver for
    anything that matters (yfinance IVs are frequently stale or junk).
    """

    contract_symbol: str
    underlying: str
    option_type: OptionType
    strike: float = Field(gt=0)
    expiry: dt.date
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None

    @property
    def mid(self) -> float | None:
        """Bid/ask midpoint; falls back to last if either side missing."""
        if self.bid is not None and self.ask is not None and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last

    @property
    def spread_pct(self) -> float | None:
        """Bid-ask spread as a fraction of mid. None if unquotable."""
        if self.bid is None or self.ask is None:
            return None
        mid = (self.bid + self.ask) / 2.0
        if mid <= 0:
            return None
        return (self.ask - self.bid) / mid

    def dte(self, as_of: dt.date | None = None) -> int:
        """Calendar days to expiry from ``as_of`` (default: today)."""
        ref = as_of or dt.date.today()
        return (self.expiry - ref).days


class OptionChain(BaseModel):
    """All calls and puts for one underlying and one expiry."""

    underlying: str
    spot: float = Field(gt=0)
    expiry: dt.date
    calls: list[OptionContract]
    puts: list[OptionContract]
    fetched_at: dt.datetime

    def atm_strike(self) -> float:
        """Strike closest to spot across the chain."""
        strikes = {c.strike for c in self.calls} | {p.strike for p in self.puts}
        if not strikes:
            raise ValueError(f"empty chain for {self.underlying} {self.expiry}")
        return min(strikes, key=lambda k: abs(k - self.spot))

    def contract_at(
        self, option_type: OptionType, strike: float
    ) -> OptionContract | None:
        side = self.calls if option_type == "call" else self.puts
        for c in side:
            if abs(c.strike - strike) < 1e-9:
                return c
        return None
