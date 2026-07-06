"""Thin Gamma API client (market/event metadata catalog). Public, no auth.

Rate limits are Cloudflare-throttled; docs suggest staying well under
~30 req/s. We default to one request every 0.5s for bulk pagination —
recon is not latency-sensitive.

Live pagination constraints (verified 2026-07-06):
- `limit` is silently capped at 100 (requesting 500 returns 100).
- offsets beyond 2000 return 422 pointing at /markets/keyset, but that
  endpoint's cursor parameter is ignored on the public API. Full
  enumeration therefore pages ordered by endDate ascending and advances
  an inclusive `end_date_min` window whenever the offset cap is hit,
  deduplicating on market id.
"""
from __future__ import annotations

import time
from typing import Any, Iterator

try:
    import httpx
    _Client = httpx.Client
except ModuleNotFoundError:  # containers with Polymarket egress but no PyPI
    from ._compat import StdlibClient as _Client

BASE = "https://gamma-api.polymarket.com"
PAGE_LIMIT = 100   # server-side cap; larger values are silently truncated
MAX_OFFSET = 2000  # server 422s beyond this ("use /markets/keyset")
POLITE_DELAY_S = 0.5


class GammaClient:
    def __init__(self, timeout: float = 30.0):
        self._http = _Client(base_url=BASE, timeout=timeout)

    def get(self, path: str, **params: Any) -> Any:
        r = self._http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def iter_markets(self, *, closed: bool | None = None, active: bool | None = None,
                     max_pages: int = 2000, **extra: Any) -> Iterator[dict]:
        """Enumerate ALL matching markets despite the offset cap.

        Pages `GET /markets` ordered by endDate ascending; when the offset
        cap forces a restart, resumes from `end_date_min = last seen
        endDate` (inclusive — duplicates at the boundary are dropped via
        the id set). Raises if a single endDate value spans more than the
        cap, rather than silently under-counting.
        """
        params: dict[str, Any] = dict(extra)
        if closed is not None:
            params["closed"] = str(closed).lower()
        if active is not None:
            params["active"] = str(active).lower()
        seen: set[str] = set()
        end_min: str | None = params.pop("end_date_min", None)
        pages = 0
        while pages < max_pages:
            offset = 0
            last_end: str | None = None
            while pages < max_pages:
                q = dict(params, limit=PAGE_LIMIT, offset=offset,
                         order="endDate", ascending="true")
                if end_min:
                    q["end_date_min"] = end_min
                page = self.get("/markets", **q)
                pages += 1
                if not page:
                    return
                for m in page:
                    mid = str(m.get("id"))
                    if mid in seen:
                        continue
                    seen.add(mid)
                    yield m
                last_end = page[-1].get("endDate") or last_end
                if len(page) < PAGE_LIMIT:
                    return
                offset += len(page)
                time.sleep(POLITE_DELAY_S)
                if offset > MAX_OFFSET:
                    break
            if not last_end or last_end == end_min:
                raise RuntimeError(
                    f"pagination stalled: >{MAX_OFFSET} markets share "
                    f"endDate window starting at {end_min!r}")
            end_min = last_end

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
            offset += len(page)
            time.sleep(POLITE_DELAY_S)
