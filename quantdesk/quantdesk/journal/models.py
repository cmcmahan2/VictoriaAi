"""Trade journal: full lifecycle persistence in SQLite.

The journal is the system's memory and its conscience: it records what
you actually did (including rule overrides, permanently) so the monthly
review can compare behavior against the plan. P&L is always computed,
never hand-entered.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Table, select, update

from quantdesk.data.cache import _metadata, _engine_for
from quantdesk.data.models import OptionType

_journal_table = Table(
    "journal_trades",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String, nullable=False),
    Column("status", String, nullable=False),
    Column("opened_at", String, nullable=False),
    Column("data", String, nullable=False),  # full JournalTrade as JSON
)


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class JournalLeg(BaseModel):
    action: str  # sell | buy
    option_type: OptionType
    strike: float
    expiry: dt.date
    contracts: int = 1
    entry_price: float          # per share


class Adjustment(BaseModel):
    date: dt.date
    description: str
    cash_flow: float            # $ received (+) or paid (-), e.g. a roll


class Note(BaseModel):
    date: dt.date
    text: str


class JournalTrade(BaseModel):
    id: int | None = None
    symbol: str
    strategy: str
    status: TradeStatus = TradeStatus.OPEN
    opened_at: dt.date
    closed_at: dt.date | None = None
    legs: list[JournalLeg]
    credit_total: float          # $ net received at open (all legs, all contracts)
    fees_total: float = 0.0
    adjustments: list[Adjustment] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)
    close_cost: float | None = None   # $ paid to close (0 = expired/assigned)
    exit_reason: str | None = None
    realized_pnl: float | None = None  # auto-computed on close
    override_used: bool = False
    override_justification: str | None = None
    iv_at_entry: float | None = None   # for the IV-sold vs RV-realized report
    rv_at_close: float | None = None


class Journal:
    """SQLite-backed journal. One row per trade; JSON document payload."""

    def __init__(self, db_path: Path) -> None:
        self._engine = _engine_for(db_path)

    # -- lifecycle ---------------------------------------------------------

    def open_trade(self, trade: JournalTrade) -> int:
        """Insert a new OPEN trade; returns its id. Overrides are permanent:
        an override without a justification is rejected."""
        if trade.override_used and not trade.override_justification:
            raise ValueError(
                "override_used requires a justification — the journal exists "
                "to record why rules were broken"
            )
        trade.status = TradeStatus.OPEN
        with self._engine.begin() as conn:
            result = conn.execute(
                _journal_table.insert().values(
                    symbol=trade.symbol.upper(),
                    status=trade.status.value,
                    opened_at=trade.opened_at.isoformat(),
                    data=trade.model_dump_json(),
                )
            )
            pk = result.inserted_primary_key
            assert pk is not None
            trade_id = int(pk[0])
        trade.id = trade_id
        self._save(trade)  # persist the id inside the document too
        return trade_id

    def adjust(
        self, trade_id: int, date: dt.date, description: str, cash_flow: float = 0.0
    ) -> JournalTrade:
        trade = self.get(trade_id)
        if trade.status != TradeStatus.OPEN:
            raise ValueError(f"trade {trade_id} is not open")
        trade.adjustments.append(
            Adjustment(date=date, description=description, cash_flow=cash_flow)
        )
        self._save(trade)
        return trade

    def add_note(self, trade_id: int, date: dt.date, text: str) -> JournalTrade:
        trade = self.get(trade_id)
        trade.notes.append(Note(date=date, text=text))
        self._save(trade)
        return trade

    def close_trade(
        self,
        trade_id: int,
        date: dt.date,
        close_cost: float,
        exit_reason: str,
        rv_at_close: float | None = None,
    ) -> JournalTrade:
        """Close and auto-compute P&L:
        pnl = credit_total + adjustments cash - close_cost - fees."""
        trade = self.get(trade_id)
        if trade.status != TradeStatus.OPEN:
            raise ValueError(f"trade {trade_id} is not open")
        trade.status = TradeStatus.CLOSED
        trade.closed_at = date
        trade.close_cost = close_cost
        trade.exit_reason = exit_reason
        trade.rv_at_close = rv_at_close
        adj_cash = sum(a.cash_flow for a in trade.adjustments)
        trade.realized_pnl = (
            trade.credit_total + adj_cash - close_cost - trade.fees_total
        )
        self._save(trade)
        return trade

    def assign(self, trade_id: int, date: dt.date) -> JournalTrade:
        """Assignment: the option leg closes at zero cost (credit kept);
        the resulting share position is a new chapter (wheel/covered call)."""
        return self.close_trade(trade_id, date, close_cost=0.0, exit_reason="assigned")

    # -- queries -----------------------------------------------------------

    def get(self, trade_id: int) -> JournalTrade:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(_journal_table.c.data).where(_journal_table.c.id == trade_id)
            ).first()
        if row is None:
            raise KeyError(f"no trade with id {trade_id}")
        trade = JournalTrade.model_validate_json(row[0])
        trade.id = trade_id
        return trade

    def list_trades(self, status: TradeStatus | None = None) -> list[JournalTrade]:
        stmt = select(_journal_table.c.id, _journal_table.c.data).order_by(
            _journal_table.c.id
        )
        if status is not None:
            stmt = stmt.where(_journal_table.c.status == status.value)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).all()
        out: list[JournalTrade] = []
        for trade_id, data in rows:
            t = JournalTrade.model_validate_json(data)
            t.id = int(trade_id)
            out.append(t)
        return out

    # -- internal ----------------------------------------------------------

    def _save(self, trade: JournalTrade) -> None:
        assert trade.id is not None
        with self._engine.begin() as conn:
            conn.execute(
                update(_journal_table)
                .where(_journal_table.c.id == trade.id)
                .values(status=trade.status.value, data=trade.model_dump_json())
            )
