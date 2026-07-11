"""SQLite local cache. The Google Sheet is the system of record; this DB is
rebuilt from the sheet on startup and kept in lockstep on every write."""

import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent / "slipstream.db"

# Sheet column order — id first so sheet lookups by id scan column A.
BET_COLUMNS = [
    "id", "date_placed", "book", "player", "league", "match", "event_time",
    "market", "line", "side", "odds", "win_prob", "ev_pct", "stake", "status",
    "payout", "pnl", "bankroll_after", "clv", "notes", "settled_at",
]

DEFAULT_CONFIG = {
    "current_bankroll": "115.95",
    "starting_bankroll": "115.95",
    "currency": "CAD",
    "kelly_fraction": "0.25",
    "max_open_exposure_pct": "35",
    "min_ev_floor_pct": "8",
    "default_book": "",
}

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                id TEXT PRIMARY KEY,
                date_placed TEXT, book TEXT, player TEXT, league TEXT,
                match TEXT, event_time TEXT, market TEXT, line TEXT, side TEXT,
                odds REAL, win_prob REAL, ev_pct REAL, stake REAL,
                status TEXT DEFAULT 'OPEN',
                payout REAL, pnl REAL, bankroll_after REAL,
                clv TEXT DEFAULT '', notes TEXT DEFAULT '',
                settled_at TEXT,
                seq INTEGER
            )""")
        conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        for k, v in DEFAULT_CONFIG.items():
            conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))


def get_config() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({r["key"]: r["value"] for r in rows})
    return cfg


def set_config(key: str, value) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def replace_all_bets(bets: list[dict]) -> None:
    """Rebuild the cache from the sheet (sheet row order preserved via seq)."""
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM bets")
        for i, b in enumerate(bets):
            row = {c: b.get(c) for c in BET_COLUMNS}
            row["seq"] = i
            cols = ", ".join(row.keys())
            marks = ", ".join("?" for _ in row)
            conn.execute(f"INSERT OR REPLACE INTO bets ({cols}) VALUES ({marks})",
                         list(row.values()))


def bet_exists(bet_id: str) -> bool:
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM bets WHERE id = ?", (bet_id,)).fetchone() is not None


def insert_bet(bet: dict) -> None:
    with _lock, _connect() as conn:
        seq = conn.execute("SELECT COALESCE(MAX(seq), -1) + 1 FROM bets").fetchone()[0]
        row = {c: bet.get(c) for c in BET_COLUMNS}
        row["seq"] = seq
        cols = ", ".join(row.keys())
        marks = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO bets ({cols}) VALUES ({marks})", list(row.values()))


def update_bet(bet_id: str, fields: dict) -> None:
    allowed = {k: v for k, v in fields.items() if k in BET_COLUMNS and k != "id"}
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    with _lock, _connect() as conn:
        conn.execute(f"UPDATE bets SET {sets} WHERE id = ?", [*allowed.values(), bet_id])


def get_bet(bet_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM bets WHERE id = ?", (bet_id,)).fetchone()
    return dict(row) if row else None


def list_bets(status: str | None = None) -> list[dict]:
    q = "SELECT * FROM bets"
    args: list = []
    if status:
        q += " WHERE status = ?"
        args.append(status)
    q += " ORDER BY seq"
    with _connect() as conn:
        return [dict(r) for r in conn.execute(q, args).fetchall()]


def open_exposure() -> float:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(stake), 0) FROM bets WHERE status = 'OPEN'"
        ).fetchone()
    return float(row[0] or 0)
