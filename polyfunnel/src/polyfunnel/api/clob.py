"""Thin CLOB API client for PUBLIC endpoints (no auth needed).

Order placement lives in Phase 7 behind py-clob-client with L1/L2 auth;
research code uses only these read paths. Endpoint paths cross-checked
against py-clob-client v0.34.6 source (see docs/GROUND_TRUTH.md).
"""
from __future__ import annotations

from typing import Any

try:
    import httpx
    _Client = httpx.Client
except ModuleNotFoundError:  # containers with Polymarket egress but no PyPI
    from ._compat import StdlibClient as _Client

BASE = "https://clob.polymarket.com"


class ClobPublic:
    def __init__(self, timeout: float = 30.0):
        self._http = _Client(base_url=BASE, timeout=timeout)

    def get(self, path: str, **params: Any) -> Any:
        r = self._http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def server_time(self) -> Any:
        return self.get("/time")

    def book(self, token_id: str) -> dict:
        return self.get("/book", token_id=token_id)

    def spreads(self, token_ids: list[str]) -> Any:
        # POST /spreads accepts a body of {token_id} params objects
        r = self._http.post("/spreads", json=[{"token_id": t} for t in token_ids])
        r.raise_for_status()
        return r.json()

    def fee_rate(self, token_id: str) -> Any:
        """Per-market dynamic fee in bps — the execution-authoritative value."""
        return self.get("/fee-rate", token_id=token_id)

    def prices_history(self, token_id: str, *, interval: str | None = None,
                       start_ts: int | None = None, end_ts: int | None = None,
                       fidelity: int | None = None) -> Any:
        """GET /prices-history. fidelity = bucket minutes (advisory; sub-12h
        granularity is often unavailable for older/resolved markets — verify
        per market and record actual granularity obtained)."""
        params: dict[str, Any] = {"market": token_id}
        if interval is not None:
            params["interval"] = interval
        if start_ts is not None:
            params["startTs"] = start_ts
        if end_ts is not None:
            params["endTs"] = end_ts
        if fidelity is not None:
            params["fidelity"] = fidelity
        return self.get("/prices-history", **params)
