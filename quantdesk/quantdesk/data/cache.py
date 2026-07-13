"""SQLite-backed cache with TTL, plus the IV-history store.

Two concerns live here because both are "things we persist locally":

* ``Cache`` — generic string key/value cache with per-entry TTL. The
  provider layer uses it so repeated scans don't hammer yfinance
  (chains 15 min, history 24 h).
* ``IVHistoryStore`` — yfinance has no historical implied volatility,
  so QuantDesk records the 30d ATM IV it computes each day and builds
  its own history. IV rank/percentile become more trustworthy as this
  matures; callers must surface the maturity label.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

from sqlalchemy import (
    Column,
    Date,
    Float,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    select,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

_metadata = MetaData()

_cache_table = Table(
    "cache",
    _metadata,
    Column("key", String, primary_key=True),
    Column("value", String, nullable=False),
    Column("expires_at", Float, nullable=False),
)

_iv_history_table = Table(
    "iv_history",
    _metadata,
    Column("symbol", String, primary_key=True),
    Column("obs_date", Date, primary_key=True),
    Column("atm_iv", Float, nullable=False),
)


def _engine_for(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # timeout: parallel screener workers write through one SQLite file;
    # wait for locks instead of raising "database is locked".
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"timeout": 30}
    )
    _metadata.create_all(engine)
    return engine


class Cache:
    """Generic TTL cache over SQLite. Values are opaque strings (JSON)."""

    def __init__(self, db_path: Path) -> None:
        self._engine = _engine_for(db_path)

    def get(self, key: str) -> str | None:
        """Return the cached value, or None if absent or expired."""
        with self._engine.begin() as conn:
            row = conn.execute(
                select(_cache_table.c.value, _cache_table.c.expires_at).where(
                    _cache_table.c.key == key
                )
            ).first()
            if row is None:
                return None
            value, expires_at = row
            if time.time() >= float(expires_at):
                conn.execute(delete(_cache_table).where(_cache_table.c.key == key))
                return None
            return str(value)

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        stmt = sqlite_insert(_cache_table).values(
            key=key, value=value, expires_at=time.time() + ttl_seconds
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"value": stmt.excluded.value, "expires_at": stmt.excluded.expires_at},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def purge_expired(self) -> int:
        """Delete all expired rows; returns number removed."""
        with self._engine.begin() as conn:
            result = conn.execute(
                delete(_cache_table).where(_cache_table.c.expires_at <= time.time())
            )
            return int(result.rowcount or 0)


class IVHistoryStore:
    """Persists one ATM-IV observation per symbol per day.

    This is QuantDesk's home-grown IV history (yfinance provides none).
    Rank/percentile stats computed from it are only as good as the number
    of days collected — always report maturity alongside them.
    """

    def __init__(self, db_path: Path) -> None:
        self._engine = _engine_for(db_path)

    def record(self, symbol: str, obs_date: dt.date, atm_iv: float) -> None:
        """Upsert today's observation (idempotent per symbol/day)."""
        stmt = sqlite_insert(_iv_history_table).values(
            symbol=symbol.upper(), obs_date=obs_date, atm_iv=atm_iv
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "obs_date"],
            set_={"atm_iv": stmt.excluded.atm_iv},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def history(
        self, symbol: str, lookback_days: int = 365
    ) -> list[tuple[dt.date, float]]:
        """Observations within the lookback window, oldest first."""
        cutoff = dt.date.today() - dt.timedelta(days=lookback_days)
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(_iv_history_table.c.obs_date, _iv_history_table.c.atm_iv)
                .where(
                    _iv_history_table.c.symbol == symbol.upper(),
                    _iv_history_table.c.obs_date >= cutoff,
                )
                .order_by(_iv_history_table.c.obs_date)
            ).all()
        return [(r[0], float(r[1])) for r in rows]
