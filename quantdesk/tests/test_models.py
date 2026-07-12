"""Tests for domain models: mid/spread/DTE helpers, chain lookups."""

from __future__ import annotations

import datetime as dt

import pytest

from quantdesk.data.models import Bar, OptionChain, OptionContract, PriceHistory, Quote


def make_contract(**overrides: object) -> OptionContract:
    base: dict[str, object] = dict(
        contract_symbol="AAPL260117P00200000",
        underlying="AAPL",
        option_type="put",
        strike=200.0,
        expiry=dt.date(2026, 1, 17),
        bid=4.90,
        ask=5.10,
        last=5.05,
        volume=1200,
        open_interest=8000,
        implied_volatility=0.28,
    )
    base.update(overrides)
    return OptionContract.model_validate(base)


class TestOptionContract:
    def test_mid_from_bid_ask(self) -> None:
        assert make_contract().mid == pytest.approx(5.00)

    def test_mid_falls_back_to_last(self) -> None:
        assert make_contract(bid=None).mid == 5.05

    def test_spread_pct(self) -> None:
        assert make_contract().spread_pct == pytest.approx(0.20 / 5.00)

    def test_spread_pct_none_when_unquoted(self) -> None:
        assert make_contract(ask=None).spread_pct is None

    def test_dte(self) -> None:
        c = make_contract()
        as_of = dt.date(2026, 1, 2)
        assert c.dte(as_of) == 15


class TestOptionChain:
    def make_chain(self) -> OptionChain:
        strikes = [190.0, 195.0, 200.0, 205.0]
        return OptionChain(
            underlying="AAPL",
            spot=198.40,
            expiry=dt.date(2026, 1, 17),
            calls=[make_contract(option_type="call", strike=k) for k in strikes],
            puts=[make_contract(strike=k) for k in strikes],
            fetched_at=dt.datetime.now(dt.timezone.utc),
        )

    def test_atm_strike(self) -> None:
        assert self.make_chain().atm_strike() == 200.0

    def test_contract_at(self) -> None:
        chain = self.make_chain()
        c = chain.contract_at("put", 195.0)
        assert c is not None and c.strike == 195.0
        assert chain.contract_at("put", 197.5) is None

    def test_empty_chain_raises(self) -> None:
        chain = self.make_chain().model_copy(update={"calls": [], "puts": []})
        with pytest.raises(ValueError, match="empty chain"):
            chain.atm_strike()


class TestQuoteAndHistory:
    def test_quote_symbol_normalized(self) -> None:
        q = Quote(symbol=" aapl ", price=198.4, timestamp=dt.datetime.now())
        assert q.symbol == "AAPL"

    def test_quote_rejects_nonpositive_price(self) -> None:
        with pytest.raises(ValueError):
            Quote(symbol="AAPL", price=0.0, timestamp=dt.datetime.now())

    def test_history_accessors(self) -> None:
        bars = [
            Bar(date=dt.date(2026, 1, d), open=10, high=11, low=9, close=10.5, volume=100)
            for d in (2, 3)
        ]
        h = PriceHistory(symbol="X", bars=bars)
        assert h.closes == [10.5, 10.5]
        assert h.highs == [11, 11]
        assert h.dates[0] < h.dates[1]
