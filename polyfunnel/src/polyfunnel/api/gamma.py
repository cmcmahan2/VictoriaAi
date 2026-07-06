"""Thin Gamma API client (market/event metadata catalog). Public, no auth.

Rate limits are Cloudflare-throttled; docs suggest staying well under
~30 req/s. We default to one request every 0.5s for bulk pagination —
recon is not latency-sensitive.
"""
from __future__ import annotations

import time
from typing import Any, Iterator

import httpx

BASE = "https://gamma-api.polymarket.com"
PAGE_LIMIT = 500  # documented max per call
POLITE_DELAY_S = 0.5


class GammaClient:
    def __init__(self, timeout: float = 30.0):
        self._http = httpx.Client(base_url=BASE, timeout=timeout)

    def get(self, path: str, **params: Any) -> Any:
        r = self._http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def iter_markets(self, *, closed: bool | None = None, active: bool | None = None,
                     max_pages: int = 1000, **extra: Any) -> Iterator[dict]:
        """Paginate GET /markets. Yields raw market dicts."""
        params: dict[str, Any] = {"limit": PAGE_LIMIT, **extra}
        if closed is not None:
            params["closed"] = str(closed).lower()
        if active is not None:
            params["active"] = str(active).lower()
        offset = 0
        for _ in range(max_pages):
            page = self.get("/markets", offset=offset, **params)
            if not page:
                return
            yield from page
            if len(page) < PAGE_LIMIT:
                return
            offset += PAGE_LIMIT
            time.sleep(POLITE_DELAY_S)

    def iter_events(self, **params: Any) -> Iterator[dict]:
        params = {"limit": PAGE_LIMIT, **params}
        offset = 0
        while True:
            page = self.get("/events", offset=offset, **params)
            if not page:
                return
            yield from page
            if len(page) < PAGE_LIMIT:
                return
            offset += PAGE_LIMIT
            time.sleep(POLITE_DELAY_S)
