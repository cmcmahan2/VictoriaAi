"""SQLite-backed persistence for pipeline jobs.

Each job write is a full upsert (INSERT OR REPLACE) so the schema stays
simple and restores are a single SELECT. WAL mode keeps concurrent readers
fast while the background job thread writes.
"""

import json
import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path("./output/jobs.db")
_lock = threading.Lock()


def configure(db_path: Path) -> None:
    global _DB_PATH
    _DB_PATH = db_path


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def init() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with _connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id      TEXT PRIMARY KEY,
                    description TEXT NOT NULL DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'queued',
                    created_at  TEXT,
                    finished_at TEXT,
                    error       TEXT,
                    logs        TEXT NOT NULL DEFAULT '[]',
                    result      TEXT
                )
            """)


def upsert(job: dict) -> None:
    """Persist the current in-memory job dict to the database."""
    with _lock:
        with _connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO jobs
                    (job_id, description, status, created_at, finished_at, error, logs, result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["id"],
                    job.get("description", ""),
                    job.get("status", "queued"),
                    job.get("created_at"),
                    job.get("finished_at"),
                    job.get("error"),
                    json.dumps(job.get("logs", [])),
                    json.dumps(job["result"]) if job.get("result") is not None else None,
                ),
            )


def load_all() -> list[dict]:
    """Load all persisted jobs, newest first. Returns at most 500 entries."""
    with _connect() as con:
        rows = con.execute(
            "SELECT job_id, description, status, created_at, finished_at, error, logs, result "
            "FROM jobs ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
    out = []
    for row in rows:
        job_id, desc, status, created_at, finished_at, error, logs_json, result_json = row
        out.append(
            {
                "id":          job_id,
                "description": desc,
                "status":      status,
                "created_at":  created_at,
                "finished_at": finished_at,
                "error":       error,
                "logs":        json.loads(logs_json) if logs_json else [],
                "result":      json.loads(result_json) if result_json else None,
            }
        )
    return out
