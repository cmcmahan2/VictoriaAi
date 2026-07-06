"""Stdlib fallback HTTP client exposing the slice of httpx.Client we use.

Some managed containers (Claude Code on the web with a host allowlist) can
reach *.polymarket.com but cannot reach PyPI, so httpx may be uninstallable.
This shim covers exactly the surface gamma.py/clob.py use:
Client(base_url=..., timeout=...), .get(path, params=...) and
.post(path, json=...) returning a response with .raise_for_status() and
.json(). TLS uses the system trust store (which carries the container's
egress-proxy CA when one is injected); proxies come from the environment.
"""
from __future__ import annotations

import json as _json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_UA = "polyfunnel/0.1 (+research; public reads only)"
_RETRIES = 4          # transient connection-level failures only, never HTTP 4xx/5xx
_BACKOFF_BASE_S = 1.0


class HTTPStatusError(Exception):
    def __init__(self, status_code: int, url: str, body: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code} for {url}: {body[:200]!r}")


class _Response:
    def __init__(self, status_code: int, body: str, url: str):
        self.status_code = status_code
        self.url = url
        self._body = body

    def raise_for_status(self) -> "_Response":
        if self.status_code >= 400:
            raise HTTPStatusError(self.status_code, self.url, self._body)
        return self

    def json(self) -> Any:
        return _json.loads(self._body)


class StdlibClient:
    def __init__(self, base_url: str = "", timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._ctx = ssl.create_default_context()

    def _url(self, path: str, params: dict | None) -> str:
        url = path if path.startswith("http") else self._base + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        return url

    def _request(self, url: str, data: bytes | None = None,
                 headers: dict | None = None) -> _Response:
        req = urllib.request.Request(
            url, data=data, headers={"User-Agent": _UA, **(headers or {})})
        for attempt in range(_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout,
                                            context=self._ctx) as r:
                    return _Response(r.status, r.read().decode("utf-8", "replace"), url)
            except urllib.error.HTTPError as e:
                return _Response(e.code, e.read().decode("utf-8", "replace"), url)
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
                if attempt == _RETRIES:
                    raise
                time.sleep(_BACKOFF_BASE_S * 2 ** attempt)
        raise AssertionError("unreachable")

    def get(self, path: str, params: dict | None = None) -> _Response:
        return self._request(self._url(path, params))

    def post(self, path: str, json: Any = None) -> _Response:
        body = _json.dumps(json).encode() if json is not None else None
        return self._request(self._url(path, None), data=body,
                             headers={"Content-Type": "application/json"})
