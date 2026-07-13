"""Deterministic offline DataProvider for tests.

Chains are priced with the Black-Scholes engine at a known sigma, so
tests can assert exact solver round-trips. Per-symbol behavior (spot,
trend, liquidity, earnings) is controlled via ``FakeSymbolSpec`` so the
screener's filters can each be triggered on purpose.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from quantdesk.analytics.black_scholes import bs_price
from quantdesk.data.models import (
    Bar,
    OptionChain,
    OptionContract,
    OptionType,
    PriceHistory,
    Quote,
)
from quantdesk.data.provider import DataProvider

TRUE_SIGMA = 0.25
SPOT = 100.0
RATE = 0.04
N_BARS = 130


@dataclass
class FakeSymbolSpec:
    spot: float = SPOT
    sigma: float = TRUE_SIGMA
    cc_vol: float = 0.20            # alternating-return realized vol (annualized)
    decline_from: float | None = None  # e.g. 4.0 -> price fell 4x over history
    oi: int = 5000
    volume: int = 1000
    half_spread: float = 0.01       # absolute half bid-ask spread
    strike_grid: tuple[float, ...] = (0.90, 0.95, 1.00, 1.05, 1.10)
    earnings_in_days: int | None = 50
    dividend_yield: float = 0.0


class FakeProvider(DataProvider):
    """Offline provider; unknown symbols get the default spec."""

    SPECIAL_QUOTES = {"^VIX": 20.0, "^VIX3M": 20.0, "CADUSD=X": 0.73}

    def __init__(self, specs: dict[str, FakeSymbolSpec] | None = None) -> None:
        self.specs = specs or {}

    def _spec(self, symbol: str) -> FakeSymbolSpec:
        return self.specs.get(symbol, FakeSymbolSpec())

    def get_quote(self, symbol: str) -> Quote:
        price = self.SPECIAL_QUOTES.get(symbol, self._spec(symbol).spot)
        return Quote(symbol=symbol, price=price, timestamp=dt.datetime.now())

    def get_price_history(self, symbol: str, years: int = 5) -> PriceHistory:
        spec = self._spec(symbol)
        start = dt.date.today() - dt.timedelta(days=200)
        bars: list[Bar] = []
        if spec.decline_from is not None:
            # Steady exponential decline ending at spot (freefall shape).
            step = math.log(spec.decline_from) / (N_BARS - 1)
            for i in range(N_BARS):
                price = spec.spot * math.exp(step * (N_BARS - 1 - i))
                bars.append(self._bar(start, i, price))
        else:
            # Alternating +/- log returns sized for spec.cc_vol annualized.
            a = spec.cc_vol / math.sqrt(252)
            price = spec.spot
            for i in range(N_BARS):
                price *= math.exp(a if i % 2 else -a)
                bars.append(self._bar(start, i, price))
        return PriceHistory(symbol=symbol, bars=bars)

    @staticmethod
    def _bar(start: dt.date, i: int, price: float) -> Bar:
        return Bar(
            date=start + dt.timedelta(days=i),
            open=price,
            high=price * 1.005,
            low=price * 0.995,
            close=price,
            volume=1e6,
        )

    def get_expirations(self, symbol: str) -> list[dt.date]:
        return [dt.date.today() + dt.timedelta(days=d) for d in (7, 30, 60)]

    def get_option_chain(self, symbol: str, expiry: dt.date) -> OptionChain:
        spec = self._spec(symbol)
        t = (expiry - dt.date.today()).days / 365.0
        strikes = [round(m * spec.spot, 2) for m in spec.strike_grid]

        def contract(opt_type: OptionType, strike: float) -> OptionContract:
            fair = bs_price(
                opt_type, spec.spot, strike, t, RATE, spec.sigma, spec.dividend_yield
            )
            return OptionContract(
                contract_symbol=f"{symbol}-{opt_type}-{strike}",
                underlying=symbol,
                option_type=opt_type,
                strike=strike,
                expiry=expiry,
                bid=max(fair - spec.half_spread, 0.0),
                ask=fair + spec.half_spread,
                last=fair,
                volume=spec.volume,
                open_interest=spec.oi,
            )

        return OptionChain(
            underlying=symbol,
            spot=spec.spot,
            expiry=expiry,
            calls=[contract("call", k) for k in strikes],
            puts=[contract("put", k) for k in strikes],
            fetched_at=dt.datetime.now(dt.timezone.utc),
        )

    def get_dividend_yield(self, symbol: str) -> float:
        return self._spec(symbol).dividend_yield

    def get_next_earnings(self, symbol: str) -> dt.date | None:
        days = self._spec(symbol).earnings_in_days
        return dt.date.today() + dt.timedelta(days=days) if days is not None else None
