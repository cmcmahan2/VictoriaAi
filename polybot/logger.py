"""
logger.py — SQLite trade log.

ONE schema, used by both the live/paper bot and the backtester. Because the
backtest writes rows in this exact shape, `analyze.py` runs unchanged on either
database (`trades.db` or `backtest_trades.db`). The `source` column distinguishes
live / paper / backtest rows so they can never be silently conflated.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              INTEGER NOT NULL,   -- decision time, unix seconds (UTC)
    window_start    INTEGER NOT NULL,   -- 5m window open
    window_end      INTEGER NOT NULL,   -- 5m window close / resolution
    hour            INTEGER NOT NULL,   -- UTC hour of decision (0-23)
    source          TEXT    NOT NULL,   -- 'live' | 'paper' | 'backtest'

    fav_side        TEXT    NOT NULL,   -- 'UP' | 'DOWN'
    signal_score    REAL    NOT NULL,   -- composite, [-1, 1]
    confidence      REAL    NOT NULL,   -- |signal_score|
    components      TEXT,               -- JSON of per-indicator sub-signals
    win_prob_est    REAL,               -- p used by Kelly
    kelly_used      REAL,               -- bankroll fraction deployed (FAV)

    fav_token       TEXT,
    hedge_token     TEXT,
    fav_price       REAL    NOT NULL,
    hedge_price     REAL,
    fav_stake       REAL    NOT NULL,
    hedge_stake     REAL,
    fav_shares      REAL,
    hedge_shares    REAL,

    outcome         TEXT    NOT NULL,   -- realized 'UP' | 'DOWN'
    fav_won         INTEGER NOT NULL,   -- 1 if fav_side == outcome
    costs           REAL    NOT NULL,   -- gas + fees
    pnl             REAL    NOT NULL,   -- net dollars
    bankroll_before REAL,
    bankroll_after  REAL,
    drawdown        REAL                -- drawdown at decision time
);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);
"""


@dataclass
class TradeRow:
    ts: int
    window_start: int
    window_end: int
    hour: int
    source: str
    fav_side: str
    signal_score: float
    confidence: float
    fav_price: float
    fav_stake: float
    outcome: str
    fav_won: int
    costs: float
    pnl: float
    components: dict = field(default_factory=dict)
    win_prob_est: float | None = None
    kelly_used: float | None = None
    fav_token: str | None = None
    hedge_token: str | None = None
    hedge_price: float | None = None
    hedge_stake: float | None = None
    fav_shares: float | None = None
    hedge_shares: float | None = None
    bankroll_before: float | None = None
    bankroll_after: float | None = None
    drawdown: float | None = None


class TradeLogger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def log(self, row: TradeRow) -> None:
        d = asdict(row)
        d["components"] = json.dumps(d.get("components") or {})
        cols = ", ".join(d.keys())
        ph = ", ".join("?" for _ in d)
        self.conn.execute(f"INSERT INTO trades ({cols}) VALUES ({ph})", list(d.values()))
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
