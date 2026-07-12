"""DataProvider abstraction + yfinance implementation.

Strategy/screener code depends only on ``DataProvider``; swapping in a
paid provider (Polygon, Tradier, FMP) later means writing one new class
here and nothing else.

yfinance realities handled here: NaN-riddled fields, missing bid/ask on
illiquid contracts, flaky earnings calendars, and rate limits (mitigated
by the SQLite TTL cache: quotes 5 min, chains 15 min, history 24 h).
"""

from __future__ import annotations

import datetime as dt
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yfinance as yf

from quantdesk.data.cache import Cache
from quantdesk.data.models import (
    Bar,
    OptionChain,
    OptionContract,
    OptionType,
    PriceHistory,
    Quote,
)


class DataProvider(ABC):
    """Everything QuantDesk needs from a market-data source."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def get_price_history(self, symbol: str, years: int = 5) -> PriceHistory: ...

    @abstractmethod
    def get_expirations(self, symbol: str) -> list[dt.date]: ...

    @abstractmethod
    def get_option_chain(self, symbol: str, expiry: dt.date) -> OptionChain: ...

    @abstractmethod
    def get_dividend_yield(self, symbol: str) -> float: ...

    @abstractmethod
    def get_next_earnings(self, symbol: str) -> dt.date | None: ...


def _clean_float(value: Any) -> float | None:
    """yfinance loves NaN and None interchangeably; normalize to None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _clean_int(value: Any) -> int | None:
    f = _clean_float(value)
    return None if f is None else int(f)


class YFinanceProvider(DataProvider):
    """Free-data implementation over yfinance, cached in SQLite."""

    def __init__(
        self,
        db_path: Path,
        quote_ttl: float = 5 * 60,
        chain_ttl: float = 15 * 60,
        history_ttl: float = 24 * 60 * 60,
    ) -> None:
        self._cache = Cache(db_path)
        self._quote_ttl = quote_ttl
        self._chain_ttl = chain_ttl
        self._history_ttl = history_ttl

    # -- quotes ----------------------------------------------------------

    def get_quote(self, symbol: str) -> Quote:
        symbol = symbol.upper()
        key = f"quote:{symbol}"
        cached = self._cache.get(key)
        if cached is not None:
            return Quote.model_validate_json(cached)

        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = _clean_float(getattr(info, "last_price", None))
        if price is None or price <= 0:
            raise RuntimeError(f"no usable price for {symbol} from yfinance")
        quote = Quote(
            symbol=symbol,
            price=price,
            previous_close=_clean_float(getattr(info, "previous_close", None)),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )
        self._cache.set(key, quote.model_dump_json(), self._quote_ttl)
        return quote

    # -- history ---------------------------------------------------------

    def get_price_history(self, symbol: str, years: int = 5) -> PriceHistory:
        symbol = symbol.upper()
        key = f"history:{symbol}:{years}y"
        cached = self._cache.get(key)
        if cached is not None:
            return PriceHistory.model_validate_json(cached)

        df = yf.Ticker(symbol).history(period=f"{years}y", auto_adjust=True)
        if df is None or df.empty:
            raise RuntimeError(f"no price history for {symbol} from yfinance")
        bars: list[Bar] = []
        for idx, row in df.iterrows():
            o = _clean_float(row.get("Open"))
            h = _clean_float(row.get("High"))
            lo = _clean_float(row.get("Low"))
            c = _clean_float(row.get("Close"))
            v = _clean_float(row.get("Volume")) or 0.0
            if not all(x is not None and x > 0 for x in (o, h, lo, c)):
                continue  # yfinance ships occasional zero/NaN bars; drop them
            assert o is not None and h is not None and lo is not None and c is not None
            bars.append(
                Bar(date=idx.date(), open=o, high=h, low=lo, close=c, volume=v)
            )
        if len(bars) < 30:
            raise RuntimeError(
                f"only {len(bars)} clean bars for {symbol}; refusing to compute stats"
            )
        history = PriceHistory(symbol=symbol, bars=bars)
        self._cache.set(key, history.model_dump_json(), self._history_ttl)
        return history

    # -- options ---------------------------------------------------------

    def get_expirations(self, symbol: str) -> list[dt.date]:
        symbol = symbol.upper()
        raw = yf.Ticker(symbol).options
        return [dt.date.fromisoformat(s) for s in raw]

    def get_option_chain(self, symbol: str, expiry: dt.date) -> OptionChain:
        symbol = symbol.upper()
        key = f"chain:{symbol}:{expiry.isoformat()}"
        cached = self._cache.get(key)
        if cached is not None:
            return OptionChain.model_validate_json(cached)

        spot = self.get_quote(symbol).price
        raw = yf.Ticker(symbol).option_chain(expiry.isoformat())
        calls = self._parse_side(raw.calls, symbol, "call", expiry)
        puts = self._parse_side(raw.puts, symbol, "put", expiry)
        chain = OptionChain(
            underlying=symbol,
            spot=spot,
            expiry=expiry,
            calls=calls,
            puts=puts,
            fetched_at=dt.datetime.now(dt.timezone.utc),
        )
        self._cache.set(key, chain.model_dump_json(), self._chain_ttl)
        return chain

    @staticmethod
    def _parse_side(
        df: Any, symbol: str, option_type: OptionType, expiry: dt.date
    ) -> list[OptionContract]:
        contracts: list[OptionContract] = []
        if df is None or df.empty:
            return contracts
        for _, row in df.iterrows():
            strike = _clean_float(row.get("strike"))
            if strike is None or strike <= 0:
                continue
            contracts.append(
                OptionContract(
                    contract_symbol=str(row.get("contractSymbol", "")),
                    underlying=symbol,
                    option_type=option_type,
                    strike=strike,
                    expiry=expiry,
                    bid=_clean_float(row.get("bid")),
                    ask=_clean_float(row.get("ask")),
                    last=_clean_float(row.get("lastPrice")),
                    volume=_clean_int(row.get("volume")),
                    open_interest=_clean_int(row.get("openInterest")),
                    implied_volatility=_clean_float(row.get("impliedVolatility")),
                )
            )
        contracts.sort(key=lambda c: c.strike)
        return contracts

    # -- fundamentals ----------------------------------------------------

    def get_dividend_yield(self, symbol: str) -> float:
        """Trailing dividend yield as a decimal; 0.0 when unknown.

        yfinance has reported this field as both decimal (0.0044) and
        percent (0.44) across versions; anything > 0.25 is assumed to be
        percent and divided by 100 (no S&P name yields 25%+).
        """
        symbol = symbol.upper()
        key = f"divyield:{symbol}"
        cached = self._cache.get(key)
        if cached is not None:
            return float(cached)
        try:
            info = yf.Ticker(symbol).info
            y = _clean_float(info.get("dividendYield")) or 0.0
        except Exception:
            y = 0.0
        if y > 0.25:
            y = y / 100.0
        self._cache.set(key, str(y), self._history_ttl)
        return y

    def get_next_earnings(self, symbol: str) -> dt.date | None:
        """Next scheduled earnings date, or None if unknown.

        yfinance's calendar is flaky; treat None as 'unknown', and note
        the earnings-blackout filter treats unknown conservatively.
        """
        symbol = symbol.upper()
        key = f"earnings:{symbol}"
        cached = self._cache.get(key)
        if cached is not None:
            return None if cached == "none" else dt.date.fromisoformat(cached)
        result: dt.date | None = None
        try:
            cal = yf.Ticker(symbol).calendar
            dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if dates:
                today = dt.date.today()
                future = sorted(d for d in dates if isinstance(d, dt.date) and d >= today)
                result = future[0] if future else None
        except Exception:
            result = None
        self._cache.set(
            key, result.isoformat() if result else "none", self._history_ttl
        )
        return result
