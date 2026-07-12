"""Tests for the SQLite TTL cache and the IV-history store."""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

from quantdesk.data.cache import Cache, IVHistoryStore


class TestCache:
    def test_set_get_round_trip(self, tmp_path: Path) -> None:
        cache = Cache(tmp_path / "t.db")
        cache.set("k", '{"a": 1}', ttl_seconds=60)
        assert cache.get("k") == '{"a": 1}'

    def test_missing_key_none(self, tmp_path: Path) -> None:
        assert Cache(tmp_path / "t.db").get("nope") is None

    def test_expired_entry_none(self, tmp_path: Path) -> None:
        cache = Cache(tmp_path / "t.db")
        cache.set("k", "v", ttl_seconds=0.05)
        time.sleep(0.1)
        assert cache.get("k") is None

    def test_overwrite(self, tmp_path: Path) -> None:
        cache = Cache(tmp_path / "t.db")
        cache.set("k", "v1", 60)
        cache.set("k", "v2", 60)
        assert cache.get("k") == "v2"

    def test_purge_expired(self, tmp_path: Path) -> None:
        cache = Cache(tmp_path / "t.db")
        cache.set("dead", "v", ttl_seconds=-1)
        cache.set("alive", "v", ttl_seconds=60)
        assert cache.purge_expired() == 1
        assert cache.get("alive") == "v"

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        db = tmp_path / "t.db"
        Cache(db).set("k", "v", 60)
        assert Cache(db).get("k") == "v"


class TestIVHistoryStore:
    def test_record_and_read_ordered(self, tmp_path: Path) -> None:
        store = IVHistoryStore(tmp_path / "t.db")
        today = dt.date.today()
        store.record("aapl", today, 0.30)
        store.record("AAPL", today - dt.timedelta(days=1), 0.25)
        hist = store.history("AAPL")
        assert [iv for _, iv in hist] == [0.25, 0.30]  # oldest first
        assert hist[0][0] < hist[1][0]

    def test_same_day_upserts(self, tmp_path: Path) -> None:
        store = IVHistoryStore(tmp_path / "t.db")
        today = dt.date.today()
        store.record("SPY", today, 0.20)
        store.record("SPY", today, 0.22)
        hist = store.history("SPY")
        assert len(hist) == 1
        assert hist[0][1] == 0.22

    def test_lookback_window(self, tmp_path: Path) -> None:
        store = IVHistoryStore(tmp_path / "t.db")
        today = dt.date.today()
        store.record("SPY", today - dt.timedelta(days=400), 0.50)
        store.record("SPY", today, 0.20)
        assert len(store.history("SPY", lookback_days=365)) == 1

    def test_symbols_isolated(self, tmp_path: Path) -> None:
        store = IVHistoryStore(tmp_path / "t.db")
        store.record("SPY", dt.date.today(), 0.20)
        assert store.history("QQQ") == []
