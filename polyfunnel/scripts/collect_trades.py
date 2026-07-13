#!/usr/bin/env python3
"""Phase 1 collector #3: the TRADE TAPE for btc-updown-5m markets.

Run:  python scripts/collect_trades.py            # record until stopped
      python scripts/collect_trades.py --probe     # connect, show trades, exit
      python scripts/collect_trades.py --minutes 10

Why: the maker-side longshot-fade strategy (vault/STRATEGY.md, Gate #1) hinges
on ONE unmeasured question — "who fills the maker?" Book snapshots (collect_updown)
can't answer it; only the trade tape can. The CLOB market WebSocket emits a
`last_trade_price` event per executed trade with `side` = the TAKER aggressor:
  side=SELL  -> a taker sold into a resting bid  -> a maker BUY got filled
  side=BUY   -> a taker lifted an ask            -> a maker SELL got filled
Join maker-buy fills on the longshot/favorite side with the settled outcome and
you measure adverse selection directly (fill-conditional hit rate vs unconditional).

Verified live 2026-07-09 (do not trust docs blindly — RTDS taught us that):
  wss://ws-subscriptions-clob.polymarket.com/ws/market
  subscribe {"assets_ids":[...],"type":"market","custom_feature_enabled":true}
  trade event keys: market, asset_id, price, size, fee_rate_bps, side,
                    timestamp(ms), event_type="last_trade_price", transaction_hash

Writes data/collect/trades/<UTC-date>/trades-HH.ndjson[.gz] — one row per trade,
enriched with the resolved slug + Up/Down outcome so analysis needs no re-join.
Stdlib-only; reuses MiniWebSocket from collect_rtds. Fails loud, reconnects,
re-subscribes as new 5m windows roll in.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from polyfunnel.api.gamma import GammaClient   # noqa: E402
from collect_rtds import MiniWebSocket          # noqa: E402  (shared RFC6455 client)

WS_HOST = "ws-subscriptions-clob.polymarket.com"
WS_PATH = "/ws/market"
SERIES = "btc-up-or-down-5m"
DISCOVER_EVERY_S = 30          # re-scan for newly created 5m windows
TRACK_HORIZON_S = 15 * 60      # subscribe to windows ending within this horizon
PING_EVERY_S = 10.0            # CLOB keepalive (GROUND_TRUTH § WS)
STATUS_EVERY_S = 60
DATA_STALL_S = 20.0            # the channel floods price_change ~400/s; true
                              # silence this long => dead session, reconnect.
MAX_CONSEC_RECONNECTS = 20


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def discover_tokens(gamma: GammaClient) -> dict:
    """token_id -> {slug, outcome, market, end} for currently-active windows.
    end_date_min filters out the December-2025 zombie markets."""
    now = utcnow()
    out = {}
    try:
        events = gamma.get(
            "/events", limit=20, closed="false", series_slug=SERIES,
            end_date_min=iso(now - dt.timedelta(minutes=2)),
            order="endDate", ascending="true")
    except Exception as e:                       # discovery is best-effort
        print(f"WARN discover failed: {str(e)[:120]}", file=sys.stderr)
        return out
    for ev in events or []:
        for gm in ev.get("markets") or []:
            end_s = gm.get("endDate")
            if not end_s:
                continue
            end = dt.datetime.fromisoformat(end_s.replace("Z", "+00:00"))
            if (end - now).total_seconds() > TRACK_HORIZON_S:
                continue
            tids = json.loads(gm.get("clobTokenIds") or "[]")
            outs = json.loads(gm.get("outcomes") or "[]")
            for t, o in zip(tids, outs):
                out[t] = {"slug": gm.get("slug"), "outcome": o,
                          "market": gm.get("conditionId") or gm.get("id"),
                          "end": end.timestamp()}
    return out


class Writer:
    """Hour-partitioned NDJSON; gzips an hour file when it rolls over."""

    def __init__(self, base: Path):
        self.base = base
        self._path: Path | None = None
        self._fh = None

    def write(self, row: dict) -> None:
        t = dt.datetime.now(dt.UTC)
        d = self.base / t.strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"trades-{t:%H}.ndjson"
        if path != self._path:
            self._rotate(path)
        self._fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    def _rotate(self, path: Path) -> None:
        if self._fh:
            self._fh.close()
            gz = self._path.with_suffix(".ndjson.gz")
            with self._path.open("rb") as src, gzip.open(gz, "wb") as dst:
                dst.write(src.read())
            self._path.unlink()
        self._path, self._fh = path, path.open("a", encoding="utf-8")

    def flush(self) -> None:
        if self._fh:
            self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None


def run(minutes: float, probe: bool, data_dir: Path) -> int:
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    gamma = GammaClient()
    writer = Writer(data_dir / "trades")
    deadline = time.time() + minutes * 60 if minutes else None
    counts = {"trades": 0}
    seen: dict[str, None] = {}          # dedup keys (bounded)
    reconnects = 0
    probe_deadline = time.time() + 20 if probe else float("inf")

    while not stop["flag"] and (deadline is None or time.time() < deadline):
        tokens = discover_tokens(gamma)
        if not tokens:
            print("no active markets; retrying in 5s", file=sys.stderr)
            time.sleep(5)
            continue
        subscribed = set(tokens)
        try:
            ws = MiniWebSocket(WS_HOST, path=WS_PATH)
            ws.send_text(json.dumps({"assets_ids": list(subscribed),
                                     "type": "market",
                                     "custom_feature_enabled": True}))
            print(f"connected + subscribed ({len(subscribed)} tokens, "
                  f"{len(set(v['slug'] for v in tokens.values()))} markets)")
            reconnects = 0
            ws.sock.settimeout(2.0)
            next_ping = time.time() + PING_EVERY_S
            next_status = time.time() + STATUS_EVERY_S
            next_discover = time.time() + DISCOVER_EVERY_S
            last_data = time.time()

            while not stop["flag"] and (deadline is None or time.time() < deadline):
                if time.time() - last_data > DATA_STALL_S:
                    ws.close()
                    raise ConnectionError(f"no data for {DATA_STALL_S:.0f}s — stale session")
                if time.time() >= next_ping:
                    ws.ping()
                    next_ping = time.time() + PING_EVERY_S
                # re-discover; reconnect if the active token set changed
                if time.time() >= next_discover:
                    next_discover = time.time() + DISCOVER_EVERY_S
                    fresh = discover_tokens(gamma)
                    if fresh and set(fresh) != subscribed:
                        tokens = fresh
                        print(f"market set changed -> resubscribing "
                              f"({len(fresh)} tokens)")
                        ws.close()
                        break                      # outer loop reconnects with new set
                try:
                    msg = ws.recv_message()
                except TimeoutError:
                    continue
                if msg is None:
                    continue
                last_data = time.time()
                if "last_trade_price" not in msg:  # skip price_change/bbo flood cheaply
                    continue
                try:
                    parsed = json.loads(msg)
                except ValueError:
                    continue
                items = parsed if isinstance(parsed, list) else [parsed]
                for it in items:
                    if not isinstance(it, dict) or it.get("event_type") != "last_trade_price":
                        continue
                    key = it.get("transaction_hash", "") + ":" + it.get("asset_id", "")
                    if key in seen:
                        continue
                    seen[key] = None
                    meta = tokens.get(it.get("asset_id"), {})
                    writer.write({
                        "recv_ts": round(time.time(), 4),
                        "asset_id": it.get("asset_id"),
                        "slug": meta.get("slug"),
                        "outcome": meta.get("outcome"),   # Up / Down of this token
                        "price": it.get("price"),
                        "size": it.get("size"),
                        "taker_side": it.get("side"),      # BUY=maker-sell filled; SELL=maker-buy filled
                        "fee_rate_bps": it.get("fee_rate_bps"),
                        "ts": it.get("timestamp"),
                        "tx": it.get("transaction_hash"),
                        "market": it.get("market"),
                    })
                    counts["trades"] += 1
                    if probe and counts["trades"] <= 8:
                        print(f"  {meta.get('slug')} {meta.get('outcome')} "
                              f"price={it.get('price')} size={it.get('size')} "
                              f"taker_side={it.get('side')}")
                if len(seen) > 20000:              # bound the dedup set
                    for k in list(seen)[:10000]:
                        del seen[k]
                if probe and time.time() >= probe_deadline:
                    print(f"\nprobe: {counts['trades']} trades in "
                          f"{int(time.time() - (probe_deadline - 20))}s across "
                          f"{len(set(v['slug'] for v in tokens.values()))} markets")
                    print("PROBE PASS" if counts["trades"] else
                          "PROBE PARTIAL — no trades in window (quiet period?)")
                    ws.close(); writer.close()
                    return 0
                if time.time() >= next_status:
                    writer.flush()
                    print(f"[{iso(utcnow())}] trades: {counts['trades']}")
                    next_status = time.time() + STATUS_EVERY_S
        except (ConnectionError, OSError) as e:
            reconnects += 1
            print(f"WARN connection lost ({reconnects}/{MAX_CONSEC_RECONNECTS}): "
                  f"{str(e)[:140]}", file=sys.stderr)
            if reconnects >= MAX_CONSEC_RECONNECTS:
                print("FATAL: cannot hold CLOB trade WS — stopping loudly.", file=sys.stderr)
                writer.close()
                return 2
            if "429" in str(e):
                time.sleep(90)
            elif "stale session" in str(e):
                time.sleep(0.5)
            else:
                time.sleep(min(30, 2 ** reconnects))
    writer.close()
    print("done:", counts)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--minutes", type=float, default=0,
                    help="stop after N minutes (0 = run until stopped)")
    ap.add_argument("--probe", action="store_true",
                    help="connect, print first trades + a 20s census, exit")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data" / "collect")
    a = ap.parse_args()
    return run(a.minutes, a.probe, a.data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
