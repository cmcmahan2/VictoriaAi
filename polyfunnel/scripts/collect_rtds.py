#!/usr/bin/env python3
"""Phase 1 collector #2: the referee's price feed (RTDS).

Run:  python3 scripts/collect_rtds.py            # record until stopped
      python3 scripts/collect_rtds.py --probe    # connect, print 5 msgs, exit

Why: 5-minute up/down markets settle on the Chainlink BTC/USD data stream
(confirmed verbatim in the market rules), and Polymarket relays that exact
feed — plus a Binance-sourced leading feed — on a free unauthenticated
WebSocket: wss://ws-live-data.polymarket.com. Recording both tick-by-tick
gives us (a) each window's exact strike ("price to beat"), (b) settlement
direction ground truth, and (c) the Binance-vs-Chainlink basis that decides
15-20% of windows in the final seconds (community estimate — measure it!).

Subscribe format (docs + official TS client; filters is a JSON *string*):
  {"action":"subscribe","subscriptions":[
    {"topic":"crypto_prices_chainlink","type":"*","filters":"{\\"symbol\\":\\"btc/usd\\"}"}]}
Messages: {"topic","type":"update","timestamp",payload:{symbol,timestamp,value}}

Stdlib-only, including a minimal RFC-6455 WebSocket client (this repo's
containers can't pip-install; the client covers exactly what RTDS needs:
TLS, text frames, ping/pong). NOTE: the Claude-web sandbox blocks this host
— run on a normal machine. Fails loudly, reconnects with backoff, writes
hour-partitioned NDJSON under data/collect/rtds/, gzips closed hours.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import hashlib
import json
import os
import signal
import socket
import ssl
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOST = "ws-live-data.polymarket.com"
WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
PING_EVERY_S = 5.0          # per RTDS docs
STATUS_EVERY_S = 60
MAX_CONSEC_RECONNECTS = 20  # then die loudly

SUBSCRIPTIONS = [
    {"topic": "crypto_prices_chainlink", "type": "*",
     "filters": json.dumps({"symbol": "btc/usd"})},   # the resolution feed
    {"topic": "crypto_prices", "type": "*",
     "filters": json.dumps({"symbol": "btcusdt"})},   # Binance leading feed
]


class MiniWebSocket:
    """Just enough RFC 6455 for RTDS: client handshake, masked sends,
    text/ping/pong/close frames, fragment reassembly."""

    def __init__(self, host: str, timeout: float = 10.0):
        raw = socket.create_connection((host, 443), timeout=timeout)
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(raw, server_hostname=host)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET / HTTP/1.1\r\nHost: {host}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("handshake: connection closed")
            resp += chunk
        head, _, rest = resp.partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"handshake refused: {head[:200]!r}")
        want = base64.b64encode(hashlib.sha1(
            (key + WS_MAGIC).encode()).digest()).decode()
        if want.encode() not in head:
            raise ConnectionError("handshake: bad Sec-WebSocket-Accept")
        self._buf = rest
        self._frag: list[bytes] = []

    def _read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("socket closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def send_frame(self, payload: bytes, opcode: int) -> None:
        mask = os.urandom(4)
        header = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def send_text(self, text: str) -> None:
        self.send_frame(text.encode(), 0x1)

    def ping(self) -> None:
        self.send_frame(b"", 0x9)

    def recv_message(self) -> str | None:
        """Next text message (None on pong/timeout-less control traffic)."""
        b0, b1 = self._read_exact(2)
        opcode, fin = b0 & 0x0F, b0 & 0x80
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._read_exact(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._read_exact(8))[0]
        if b1 & 0x80:  # masked server frame (nonstandard but tolerate)
            mask = self._read_exact(4)
            data = bytes(b ^ mask[i % 4]
                         for i, b in enumerate(self._read_exact(n)))
        else:
            data = self._read_exact(n)
        if opcode == 0x9:               # ping -> pong
            self.send_frame(data, 0xA)
            return None
        if opcode == 0xA:               # pong
            return None
        if opcode == 0x8:               # close
            raise ConnectionError(f"server close: {data[:120]!r}")
        if opcode in (0x1, 0x2, 0x0):
            self._frag.append(data)
            if not fin:
                return None
            msg = b"".join(self._frag)
            self._frag = []
            return msg.decode("utf-8", "replace")
        return None

    def close(self) -> None:
        try:
            self.send_frame(b"", 0x8)
            self.sock.close()
        except OSError:
            pass


class Writer:
    def __init__(self, base: Path):
        self.base = base
        self._path: Path | None = None
        self._fh = None

    def write(self, row: dict) -> None:
        t = dt.datetime.now(dt.UTC)
        d = self.base / t.strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"prices-{t:%H}.ndjson"
        if path != self._path:
            if self._fh:
                self._fh.close()
                gz = self._path.with_suffix(".ndjson.gz")
                with self._path.open("rb") as src, gzip.open(gz, "wb") as dst:
                    dst.write(src.read())
                self._path.unlink()
            self._path, self._fh = path, path.open("a", encoding="utf-8")
        self._fh.write(json.dumps(row, separators=(",", ":")) + "\n")

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
    writer = Writer(data_dir / "rtds")
    deadline = time.time() + minutes * 60 if minutes else None
    counts: dict[str, int] = {}
    reconnects = 0
    probe_left = 5
    probe_deadline = time.time() + 15 if probe else float("inf")
    while not stop["flag"] and (deadline is None or time.time() < deadline):
        try:
            ws = MiniWebSocket(HOST)
            ws.send_text(json.dumps(
                {"action": "subscribe", "subscriptions": SUBSCRIPTIONS}))
            print(f"connected + subscribed ({HOST})")
            reconnects = 0
            if probe:
                probe_deadline = time.time() + 15
            ws.sock.settimeout(PING_EVERY_S)
            next_ping = time.time() + PING_EVERY_S
            next_status = time.time() + STATUS_EVERY_S
            while not stop["flag"] and (deadline is None or time.time() < deadline):
                if time.time() >= next_ping:
                    ws.ping()
                    next_ping = time.time() + PING_EVERY_S
                try:
                    msg = ws.recv_message()
                except TimeoutError:
                    continue
                except ssl.SSLWantReadError:
                    continue
                if msg is None:
                    continue
                now = time.time()
                try:
                    parsed = json.loads(msg)
                except ValueError:
                    parsed = {"raw": msg[:2000]}
                topic = parsed.get("topic") or ("server_hello" if
                        parsed.get("raw") == "" else "unknown")
                counts[topic] = counts.get(topic, 0) + 1
                writer.write({"recv_ts": round(now, 4), **parsed})
                if probe:
                    if probe_left > 0:
                        print(json.dumps(parsed)[:240])
                        probe_left -= 1
                    if now >= probe_deadline:
                        chain = counts.get("crypto_prices_chainlink", 0)
                        binance = counts.get("crypto_prices", 0)
                        print(f"\nprobe census (15s): {counts}")
                        print(f"  Chainlink (referee) feed: "
                              f"{'OK, ~%.1f/s' % (chain/15) if chain else 'MISSING'}")
                        print(f"  Binance (leading) feed:   "
                              f"{'OK, ~%.1f/s' % (binance/15) if binance else 'MISSING'}")
                        print("PROBE PASS — run without --probe to record"
                              if chain and binance else
                              "PROBE PARTIAL — send this output to Claude")
                        ws.close()
                        writer.close()
                        return 0
                if time.time() >= next_status:
                    writer.flush()
                    print(f"[{dt.datetime.now(dt.UTC):%Y-%m-%dT%H:%M:%SZ}] "
                          f"ticks: {counts}")
                    next_status = time.time() + STATUS_EVERY_S
        except (ConnectionError, OSError, ssl.SSLError) as e:
            reconnects += 1
            throttled = "429" in str(e)
            print(f"WARN connection lost ({reconnects}/"
                  f"{MAX_CONSEC_RECONNECTS}): {str(e)[:160]}", file=sys.stderr)
            if reconnects >= MAX_CONSEC_RECONNECTS:
                print("FATAL: cannot hold RTDS connection — stopping loudly. "
                      "(This host is blocked in the Claude-web sandbox; run "
                      "on a normal machine.)", file=sys.stderr)
                writer.close()
                return 2
            if throttled:
                # server-side rate limit on connects: back way off, quietly
                print("  (rate-limited: waiting 90s before reconnecting — "
                      "this is normal after several quick restarts)")
                time.sleep(90)
            else:
                time.sleep(min(60, 2 ** reconnects))
    writer.close()
    print("done:", counts)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--minutes", type=float, default=0,
                    help="stop after N minutes (0 = run until stopped)")
    ap.add_argument("--probe", action="store_true",
                    help="connect, print first 5 messages, exit")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data" / "collect")
    a = ap.parse_args()
    return run(a.minutes, a.probe, a.data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
