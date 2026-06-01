"""
macro/datafeed.py — free, no-API-key market levels for the /macro-scan command.

WHY THIS EXISTS
---------------
The connected FMP (Finance) MCP feed is on a plan tier that blocks the `quote`
family (index levels, VIX, commodities, FX, crypto) and the economics calendar.
This script fills those blind spots from Stooq's free, keyless light-quote
endpoint — no signup, no key. It complements (does NOT replace) the FMP data the
/macro-scan command still uses for the Treasury curve and sector performance/P-E.

WHAT IT PROVIDES
----------------
Current session levels (open/high/low/close + intraday % change) for a curated
cross-asset universe: equity indices, a VIX proxy, commodities, the dollar, and
crypto. Stooq's bulk *history* endpoint now requires a free key, so this script
returns levels only — trailing-return/momentum history is a future add (would
need a free Stooq or FRED key).

USAGE
-----
    python macro/datafeed.py            # pretty JSON to stdout
    python macro/datafeed.py --compact  # one-line JSON (for piping)

Pure stdlib (urllib) so it runs anywhere with zero install. Network failures are
caught per-symbol; whatever resolves is returned, the rest marked unavailable.
"""
from __future__ import annotations

import json
import sys
import urllib.request

# symbol -> (friendly label, asset class). Symbols verified against Stooq's
# keyless light-quote endpoint (some need futures/ETF proxies — noted inline).
UNIVERSE: dict[str, tuple[str, str]] = {
    "^spx":   ("S&P 500",          "equity_index"),
    "^ndx":   ("Nasdaq 100",       "equity_index"),
    "^dji":   ("Dow Jones",        "equity_index"),
    "iwm.us": ("Russell 2000 (IWM)", "equity_index"),  # ^rut returns N/D; ETF proxy
    "vi.f":   ("VIX (future)",     "volatility"),       # ^vix returns N/D; VIX future
    "gc.f":   ("Gold",             "commodity"),
    "cl.f":   ("Crude Oil (WTI)",  "commodity"),
    "hg.f":   ("Copper",           "commodity"),
    "ng.f":   ("Natural Gas",      "commodity"),
    "si.f":   ("Silver",           "commodity"),
    "dx.f":   ("US Dollar Index",  "fx"),               # ^dxy N/D; ICE USD future
    "eurusd": ("EUR/USD",          "fx"),
    "btcusd": ("Bitcoin",          "crypto"),
    "eth.v":  ("Ethereum",         "crypto"),            # ethusd N/D; eth.v works
}

_LIGHT = "https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcvn&e=csv"
_UA = {"User-Agent": "Mozilla/5.0 (macro-scan datafeed)"}


def _fetch_quote(sym: str) -> dict | None:
    """Return one parsed Stooq light quote, or None if unavailable / errored."""
    try:
        url = _LIGHT.format(sym=sym)
        line = urllib.request.urlopen(
            urllib.request.Request(url, headers=_UA), timeout=15
        ).read().decode().strip()
    except Exception as e:  # network / TLS / timeout — degrade gracefully
        return {"error": f"{type(e).__name__}: {str(e)[:60]}"}

    # Format: Symbol,Date,Time,Open,High,Low,Close,Volume,Name
    parts = line.split(",")
    if len(parts) < 7 or parts[1] == "N/D":
        return None  # Stooq served no data for this symbol right now
    try:
        o, h, l, c = (float(parts[3]), float(parts[4]), float(parts[5]), float(parts[6]))
    except ValueError:
        return None
    chg = ((c - o) / o * 100.0) if o else 0.0
    return {
        "date": parts[1], "time": parts[2],
        "open": o, "high": h, "low": l, "close": c,
        "intraday_change_pct": round(chg, 2),
    }


def collect() -> dict:
    by_class: dict[str, dict] = {}
    unavailable: list[str] = []
    for sym, (label, klass) in UNIVERSE.items():
        q = _fetch_quote(sym)
        if not q or "error" in q:
            unavailable.append(label)
            continue
        by_class.setdefault(klass, {})[label] = {"symbol": sym.upper(), **q}
    return {
        "source": "stooq.com (free, no key) — current session levels only",
        "note": "intraday_change_pct = close-vs-open for the session shown, not "
                "prior-close-to-close. History/momentum needs a free key (not used here).",
        "by_class": by_class,
        "unavailable": unavailable,
    }


def main() -> None:
    data = collect()
    compact = "--compact" in sys.argv[1:]
    print(json.dumps(data, separators=(",", ":")) if compact else json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
