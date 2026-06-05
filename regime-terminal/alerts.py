"""
alerts.py — watch the regime/setup and push a Telegram alert when a BTC swing
trade signal fires.

It polls the running dashboard's /api/intel (so it reuses the warm regime
cache instead of recomputing), and notifies you when:
  • the bias turns actionable  (WAIT -> LONG/SHORT, or LONG <-> SHORT), or
  • price trades into the suggested entry zone (once per setup).

A small state file (alerts_state.json) remembers what was last sent, so you get
pinged on *changes*, not every check.

────────────────────────────────────────────────────────────────────────────
ONE-TIME SETUP
  1. In Telegram, open a chat with @BotFather, send /newbot, follow the prompts,
     and copy the bot TOKEN it gives you (looks like 123456789:AAE...).
  2. Open your new bot in Telegram and send it any message (e.g. "hi") so it's
     allowed to message you back.
  3. Put the token in regime-terminal/.env:
         TELEGRAM_BOT_TOKEN=123456789:AAE...
  4. Find your chat id:
         python alerts.py --discover
     Copy the number and add it to .env:
         TELEGRAM_CHAT_ID=987654321
  5. Test it:
         python alerts.py --test
  6. Run the watcher (needs the dashboard up: python server.py):
         python alerts.py --loop 15      # check every 15 minutes

  Preview without sending (no token needed):
         python alerts.py --dry
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "alerts_state.json")

# Some Windows setups (AV / proxy TLS inspection) have a system trust store that
# rejects api.telegram.org. certifi's bundle verifies it correctly, so prefer it.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = ssl.create_default_context()


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from the local .env without overwriting real env vars."""
    try:
        with open(os.path.join(HERE, ".env"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


# ── Telegram ────────────────────────────────────────────────────────────── #

def _tg(method: str, params: dict) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set — see the setup steps at the top of alerts.py.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15, context=_SSL_CTX) as r:
        return json.loads(r.read())


def send_telegram(text: str) -> bool:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise SystemExit("TELEGRAM_CHAT_ID not set — run: python alerts.py --discover")
    resp = _tg("sendMessage", {
        "chat_id": chat_id, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    })
    if not resp.get("ok"):
        print("Telegram error:", resp.get("description", resp))
    return bool(resp.get("ok"))


def discover_chat_ids() -> None:
    """Print chat ids the bot can see (message your bot first, then run this)."""
    resp = _tg("getUpdates", {})
    seen = {}
    for u in resp.get("result", []):
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat", {})
        if chat.get("id"):
            seen[chat["id"]] = chat.get("username") or chat.get("first_name") or chat.get("title", "")
    if not seen:
        print("No chats found. Open your bot in Telegram, send it 'hi', then run --discover again.")
        return
    print("Found chats — add the id to .env as TELEGRAM_CHAT_ID:")
    for cid, name in seen.items():
        print(f"  {cid}   {name}")


# ── Signal evaluation ───────────────────────────────────────────────────── #

def fetch_intel(base: str, source: str, days: int) -> dict:
    url = f"{base}/api/intel?source={urllib.parse.quote(source)}&days={days}"
    with urllib.request.urlopen(url, timeout=240) as r:   # first (cold) call may be slow
        return json.loads(r.read())


def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(s: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f)


def _format(data: dict, kind: str) -> str:
    g = data.get("guidance", {})
    levels = data.get("levels", {})
    ind = data.get("indicators", {})
    regime = data.get("regime", {})
    px = levels.get("current")
    rsi = ind.get("rsi")
    lev = g.get("suggested_leverage")
    head = "📈 price in entry zone" if kind == "zone" else "🔔 new setup"
    emoji = "🟢" if g.get("bias") == "LONG" else "🔴"
    lines = [
        f"{emoji} <b>BTC {g.get('bias')} — {head}</b>",
        f"Regime: {regime.get('state_name', '?')} ({(regime.get('confidence') or 0) * 100:.0f}%)",
        f"Entry: <b>{g.get('target_entry', '—')}</b>",
        f"Stop: {g.get('stop_hint', '—')}" + (f"  ·  Leverage: {lev}×" if lev else ""),
    ]
    tail = []
    if px is not None:
        tail.append(f"px ${px:,.0f}")
    if rsi is not None:
        tail.append(f"RSI {rsi:.0f}")
    if tail:
        lines.append("  ·  ".join(tail))
    if g.get("headline"):
        lines.append(f"<i>{g['headline']}</i>")
    return "\n".join(lines)


def check_once(base: str, source: str, days: int, dry: bool = False) -> None:
    data = fetch_intel(base, source, days)
    if data.get("error"):
        print("intel error:", data["error"])
        return
    g = data.get("guidance", {})
    bias = g.get("bias", "WAIT")
    px = data.get("levels", {}).get("current")
    lo, hi = g.get("entry_lo"), g.get("entry_hi")

    state = _load_state()
    prev_bias = state.get("bias")
    zone_done = state.get("zone_done", False)

    fires = []
    if bias in ("LONG", "SHORT") and bias != prev_bias:
        fires.append("signal")
        zone_done = False                       # fresh setup → re-arm the zone alert
    in_zone = None not in (lo, hi, px) and lo <= px <= hi
    if bias in ("LONG", "SHORT") and in_zone and not zone_done:
        fires.append("zone")
        zone_done = True

    for kind in fires:
        msg = _format(data, kind)
        if dry:
            print("── would send ──\n" + msg + "\n")
        else:
            print("sending alert…", "ok" if send_telegram(msg) else "FAILED")

    if not fires:
        zone_str = f"  zone={lo:,}–{hi:,}" if (lo and hi) else ""
        print(f"[{time.strftime('%H:%M:%S')}] no new signal (bias={bias}"
              f"{f', px=${px:,.0f}' if px else ''}{zone_str})")

    _save_state({"bias": bias, "zone_done": zone_done, "ts": int(time.time())})


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Telegram alerts for BTC swing setups")
    ap.add_argument("--server", default="http://127.0.0.1:5000", help="dashboard base URL")
    ap.add_argument("--source", default="kucoin", help="data source the dashboard uses")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--loop", type=int, default=0, help="minutes between checks (0 = run once)")
    ap.add_argument("--test", action="store_true", help="send a test Telegram message and exit")
    ap.add_argument("--discover", action="store_true", help="list chat ids the bot can see")
    ap.add_argument("--dry", action="store_true", help="print alerts instead of sending")
    args = ap.parse_args()

    if args.discover:
        discover_chat_ids()
        return
    if args.test:
        ok = send_telegram("✅ Test alert from your BTC swing watcher — notifications are working.")
        print("sent." if ok else "failed — check token/chat id.")
        return

    if args.loop > 0:
        print(f"Watching {args.source} every {args.loop} min via {args.server} (Ctrl-C to stop)…")
        while True:
            try:
                check_once(args.server, args.source, args.days, dry=args.dry)
            except Exception as exc:
                print("check failed:", type(exc).__name__, exc)
            time.sleep(args.loop * 60)
    else:
        check_once(args.server, args.source, args.days, dry=args.dry)


if __name__ == "__main__":
    main()
