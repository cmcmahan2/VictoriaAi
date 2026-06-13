"""
Lightweight SQLite-backed cache for the discovery engine.

Stores expensive results - Google Places / OpenStreetMap lookups and
website-health checks - keyed by a namespace + key, with a TTL so repeated
discovery runs (especially province- and country-wide sweeps) don't re-hit
external APIs. Pure stdlib (sqlite3 + json), no extra dependencies.

The DB lives at output/cache.db alongside leads.json / clients.json, so it is
covered by the existing output/ gitignore - nothing here is ever committed.

Thread-safe by design: every call opens its own short-lived connection, which
matters because the website-health checks run across a ThreadPoolExecutor.
SQLite WAL mode lets those concurrent readers/writers coexist without errors.

Env vars:
  CACHE_DB         path to the sqlite file (default ./output/cache.db)
  CACHE_DISABLED   set to 1/true/yes to bypass the cache entirely
  CACHE_TTL_DAYS   default TTL in days for cached entries (default 7)
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

_INIT_LOCK = threading.Lock()
_initialized = False


def _disabled() -> bool:
    return os.getenv("CACHE_DISABLED", "").lower() in ("1", "true", "yes")


def _db_path() -> Path:
    return Path(os.getenv("CACHE_DB", "./output/cache.db"))


def _default_ttl() -> float:
    try:
        days = float(os.getenv("CACHE_TTL_DAYS", "7"))
    except ValueError:
        days = 7.0
    return days * 24 * 3600


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path), timeout=30)
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def _ensure_init() -> None:
    global _initialized
    if _initialized:
        return
    with _INIT_LOCK:
        if _initialized:
            return
        with _conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS kv_cache ("
                "  namespace  TEXT NOT NULL,"
                "  key        TEXT NOT NULL,"
                "  value      TEXT NOT NULL,"
                "  created_at REAL NOT NULL,"
                "  PRIMARY KEY (namespace, key)"
                ")"
            )
        _initialized = True


def get(namespace: str, key: str, ttl: float | None = None):
    """Return the cached value (JSON-decoded) for namespace+key, or None if it
    is absent, expired, or the cache is disabled. A failure to read never
    raises - a cache miss is always safe."""
    if _disabled():
        return None
    _ensure_init()
    ttl = _default_ttl() if ttl is None else ttl
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT value, created_at FROM kv_cache WHERE namespace=? AND key=?",
                (namespace, key),
            ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    value, created_at = row
    if ttl is not None and (time.time() - created_at) > ttl:
        return None
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return None


def set(namespace: str, key: str, value) -> None:  # noqa: A001 - module-qualified
    """Store value (JSON-encoded) under namespace+key, stamped with the current
    time. Unserialisable values or write errors are swallowed so caching can
    never break a discovery run."""
    if _disabled():
        return
    _ensure_init()
    try:
        payload = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO kv_cache (namespace, key, value, created_at) "
                "VALUES (?,?,?,?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET "
                "  value=excluded.value, created_at=excluded.created_at",
                (namespace, key, payload, time.time()),
            )
    except sqlite3.Error:
        pass


def stats() -> dict:
    """Return {namespace: row_count} for visibility/debugging."""
    _ensure_init()
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT namespace, COUNT(*) FROM kv_cache GROUP BY namespace"
            ).fetchall()
        return {ns: n for ns, n in rows}
    except sqlite3.Error:
        return {}


def clear(namespace: str | None = None) -> None:
    """Clear one namespace, or the entire cache when namespace is None."""
    _ensure_init()
    try:
        with _conn() as c:
            if namespace is None:
                c.execute("DELETE FROM kv_cache")
            else:
                c.execute("DELETE FROM kv_cache WHERE namespace=?", (namespace,))
    except sqlite3.Error:
        pass
