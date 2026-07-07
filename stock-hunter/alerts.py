"""
alerts.py — Telegram alerts for the Stock Hunter.

Re-runs the multi-factor hunt on a schedule and pings you when a NEW name breaks
into the top ranks (debounced via a state file, so no repeat spam). Stock ranks
move on daily bars, so this is meant to run daily, not every few minutes.

Reuses the same Telegram bot as the BTC tool: it reads TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID from this folder's .env, falling back to ../regime-terminal/.env.

  python alerts.py --test                 # send a test ping
  python alerts.py --once --use-existing   # diff against current picks.json now
  python alerts.py --once                  # re-scan, then diff + alert
  python alerts.py --loop 24               # scan + alert every 24 hours
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PICKS = os.path.join(HERE, "picks.json")
STATE = os.path.join(HERE, "stock_alerts_state.json")

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL = ssl.create_default_context()


def _load_dotenv() -> None:
    for path in (os.path.join(HERE, ".env"),
                 os.path.join(HERE, "..", "regime-terminal", ".env")):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise SystemExit("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15, context=_SSL) as r:
        return bool(json.loads(r.read()).get("ok"))


def run_hunt(max_n: int, top: int) -> None:
    print(f"  scanning (max {max_n})…", flush=True)
    subprocess.run([sys.executable, "hunt.py", "--max", str(max_n), "--top", str(top),
                    "--json", "picks.json"], cwd=HERE, check=True,
                   env={**os.environ, "PYTHONUTF8": "1"}, timeout=1800)


def load_picks() -> list[dict]:
    try:
        with open(PICKS, encoding="utf-8") as f:
            return json.load(f).get("picks", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _state() -> dict:
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _fmt(p: dict, rank: int) -> str:
    pe = f"P/E {p['pe']:.0f}" if p.get("pe") else "P/E —"
    trend = "↑200d" if p.get("above_200") else "&lt;200d"
    mom = p.get("mom")
    mom_s = f"{mom*100:+.0f}%" if mom is not None else "—"
    return f"  <b>#{rank} {p['symbol']}</b> (score {round(p.get('score',0))}) — mom {mom_s} · {trend} · {pe}"


def check(top: int) -> None:
    picks = load_picks()[:top]
    if not picks:
        print("  no picks to compare."); return
    current = [p["symbol"] for p in picks]
    prev = set(_state().get("top", []))

    if not prev:                                    # first run → baseline, alert once
        body = "\n".join(_fmt(p, i + 1) for i, p in enumerate(picks))
        msg = f"🎯 <b>Stock Hunter — top {top} (baseline)</b>\n{body}\n\n<i>You'll be pinged when new names break in.</i>"
        print("  baseline set; sending starting list.")
        send_telegram(msg)
    else:
        newcomers = [(i + 1, p) for i, p in enumerate(picks) if p["symbol"] not in prev]
        dropped = prev - set(current)
        if newcomers:
            body = "\n".join(_fmt(p, rank) for rank, p in newcomers)
            extra = f"\n<i>dropped out: {', '.join(sorted(dropped))}</i>" if dropped else ""
            msg = f"🎯 <b>Stock Hunter — {len(newcomers)} new in top {top}</b>\n{body}{extra}"
            print(f"  {len(newcomers)} new entrant(s); alerting.")
            send_telegram(msg)
        else:
            print(f"  [{time.strftime('%Y-%m-%d %H:%M')}] no new top-{top} names.")

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"top": current, "ts": int(time.time())}, f)


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Telegram alerts for the Stock Hunter")
    ap.add_argument("--top", type=int, default=15, help="size of the 'top ranks' watched")
    ap.add_argument("--max", type=int, default=1500, help="universe cap for the scan")
    ap.add_argument("--loop", type=int, default=0, help="hours between scans (0 = run once)")
    ap.add_argument("--once", action="store_true", help="run a single cycle (default when --loop=0)")
    ap.add_argument("--use-existing", action="store_true", help="skip the scan, diff current picks.json")
    ap.add_argument("--test", action="store_true", help="send a test message and exit")
    args = ap.parse_args()

    if args.test:
        ok = send_telegram("✅ Stock Hunter alerts are wired up — you'll get pinged when new names break into the top ranks.")
        print("sent." if ok else "failed."); return

    def cycle():
        if not args.use_existing:
            run_hunt(args.max, max(args.top, 25))
        check(args.top)

    if args.loop > 0:
        print(f"Watching top {args.top}, scanning every {args.loop}h (Ctrl-C to stop)…", flush=True)
        while True:
            try:
                cycle()
            except Exception as exc:
                print("cycle failed:", type(exc).__name__, exc)
            time.sleep(args.loop * 3600)
    else:
        cycle()


if __name__ == "__main__":
    main()
