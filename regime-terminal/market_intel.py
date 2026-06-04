"""
market_intel.py — BTC Swing Trade Intelligence Report

Three layers:
  1. Regime HMM + 8 technical confirmations (existing pipeline, causal)
  2. Sentiment: Fear & Greed Index (alternative.me) + BTC news (CryptoCompare)
  3. Claude claude-sonnet-4-6 synthesizes everything → swing trade plan

Usage:
  python market_intel.py                        # kucoin feed, 90 days of history
  python market_intel.py --source github        # offline / sandbox (uses historical data)
  python market_intel.py --days 180             # longer regime context
  python market_intel.py --no-claude            # raw data only (no API key needed)
  python market_intel.py --loop 3600            # re-run every hour

Needs: ANTHROPIC_API_KEY for the AI synthesis layer.
       Without it, prints raw data and skips the plan (--no-claude equivalent).
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

import config
from live import load_recent
from regimes import RegimeModel
from strategy import Indicators, count_passed


# ─── Sentiment feeds (free, no auth) ─────────────────────────────────────── #

def fetch_fear_greed() -> dict:
    """alternative.me Fear & Greed Index — 0 (extreme fear) to 100 (extreme greed)."""
    try:
        with urllib.request.urlopen("https://api.alternative.me/fng/?limit=3", timeout=6) as r:
            data = json.loads(r.read())["data"]
        return {
            "value":      int(data[0]["value"]),
            "label":      data[0]["value_classification"],
            "yesterday":  int(data[1]["value"]) if len(data) > 1 else None,
            "last_week":  int(data[2]["value"]) if len(data) > 2 else None,
        }
    except Exception as exc:
        return {"value": None, "label": "unavailable", "error": str(exc)}


# Free, no-key BTC news via public RSS. (CryptoCompare's JSON news endpoint now
# requires an auth key.) Tried in order; results are merged + de-duped by title.
_NEWS_FEEDS = [
    ("Google News",   "https://news.google.com/rss/search?q=bitcoin+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("CoinDesk",      "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
]


def _parse_rss(xml_bytes: bytes, source_hint: str = "") -> list[dict]:
    """Pull (title, source, ts, url) from an RSS 2.0 or Atom feed — stdlib only."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    out: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return out
    for item in root.iter():
        if item.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = link = pub = src = ""
        for ch in item:
            name = ch.tag.split("}")[-1]
            if name == "title" and ch.text:
                title = ch.text.strip()
            elif name == "link":                       # RSS: text · Atom: href attr
                link = (ch.text or ch.get("href") or "").strip()
            elif name in ("pubDate", "published", "updated") and ch.text and not pub:
                pub = ch.text.strip()
            elif name == "source" and ch.text:
                src = ch.text.strip()
        ts = 0
        if pub:
            try:
                ts = int(parsedate_to_datetime(pub).timestamp())
            except Exception:
                try:
                    from datetime import datetime
                    ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                except Exception:
                    ts = 0
        if title:
            out.append({"title": title, "source": src or source_hint, "ts": ts, "url": link})
    return out


def fetch_news(n: int = 12) -> list[dict]:
    """Latest BTC headlines from free public RSS feeds (no API key required).

    Merges multiple feeds, de-dupes by title, and returns newest-first when
    timestamps are available. Each item: {title, source, ts, url}.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for source_name, url in _NEWS_FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (regime-terminal)"})
            with urllib.request.urlopen(req, timeout=8) as r:
                items = _parse_rss(r.read(), source_name)
        except Exception:
            continue
        for it in items:
            key = it["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        if len(out) >= n * 2:        # enough to sort; don't hammer every feed
            break
    out.sort(key=lambda a: a.get("ts", 0), reverse=True)
    if out:
        return out[:n]
    return [{"title": "Headlines unavailable — no free feed responded.", "source": "", "ts": 0, "url": ""}]


# ─── Price levels ─────────────────────────────────────────────────────────── #

def price_levels(bars) -> dict:
    n14 = min(14 * 24, len(bars))
    window = bars[-n14:]
    px = bars[-1].close
    return {
        "current":    px,
        "high_14d":   max(b.high for b in window),
        "low_14d":    min(b.low  for b in window),
        "change_24h": (px / bars[-25].close - 1) * 100 if len(bars) > 25 else None,
        "change_7d":  (px / bars[-7*24].close - 1) * 100 if len(bars) > 7*24 else None,
        "change_30d": (px / bars[-30*24].close - 1) * 100 if len(bars) > 30*24 else None,
    }


# ─── Regime + indicators ─────────────────────────────────────────────────── #

def analyze_regime(bars) -> dict:
    """Train on all-but-last-3-days, read current stance causally (no lookahead)."""
    import config as _c
    model = RegimeModel(_c.N_STATES, tuple(_c.FEATURES), seed=_c.SEED)
    saved, _c.HMM_N_INIT = _c.HMM_N_INIT, 4
    try:
        model.fit(bars[:-72])
    finally:
        _c.HMM_N_INIT = saved
    stream = list(model.regime_stream(bars, smooth=False))
    if not stream:
        return {"stance": "unknown", "confidence": 0.0, "state_name": "?"}
    last = stream[-1]
    return {"stance": last[3], "confidence": last[2], "state_name": last[4]}


def analyze_indicators(bars) -> dict:
    ind = Indicators(bars, config)
    t = len(bars) - 1
    n_pass, checks = count_passed(ind, t)
    tr = ind.sma_trend[t]
    above_200 = tr is not None and bars[t].close > tr
    return {
        "n_pass":    n_pass,
        "n_total":   config.CONFIRMATIONS_TOTAL,
        "rsi":       ind.rsi[t],
        "macd_hist": ind.macd_hist[t],
        "adx":       ind.adx[t],
        "momentum":  ind.momentum[t],
        "sma_fast":  ind.sma_fast[t],
        "sma_slow":  ind.sma_slow[t],
        "sma_200":   ind.sma_trend[t],
        "above_200": above_200,
        "checks":    checks,
    }


# ─── Entry guidance (deterministic — no API call) ──────────────────────────── #

def entry_guidance(regime: dict, ind: dict, levels: dict, fg: dict) -> dict:
    """Always-on read of 'what do I watch for, and where would I actually enter?'

    Derives a directional bias, a concrete target-entry zone, a stop hint, and a
    'what to look for' checklist purely from the regime + indicators + price
    levels already computed. Never costs an API call, so it complements (not
    replaces) the Claude plan button.
    """
    px        = levels.get("current")
    rsi       = ind.get("rsi")
    above_200 = bool(ind.get("above_200"))
    n_pass    = ind.get("n_pass", 0) or 0
    n_total   = ind.get("n_total", 0) or 0
    need      = max(1, round(n_total * 0.6)) if n_total else 0
    stance    = (regime.get("stance") or "").lower()
    conf      = regime.get("confidence") or 0.0
    state     = regime.get("state_name", "?")

    bullish = "long" in stance
    bearish = "avoid" in stance or "short" in stance

    look_for: list[str] = []

    # Macro trend filter
    look_for.append(
        f"Trend filter: price {'ABOVE' if above_200 else 'BELOW'} the 200h SMA — "
        + ("macro uptrend, longs are with-trend." if above_200
           else "macro downtrend, longs are counter-trend (be cautious).")
    )
    # Momentum confirmations
    if n_total:
        look_for.append(
            f"Confirmations: {n_pass}/{n_total} passing"
            + (f" — want ≥ {need} before committing." if n_pass < need
               else " — momentum checklist is onside.")
        )
    # RSI posture
    if rsi is not None:
        if rsi >= 70:
            look_for.append(f"RSI {rsi:.0f}: overbought — let it cool toward 50–55 before adding longs.")
        elif rsi <= 30:
            look_for.append(f"RSI {rsi:.0f}: oversold — watch for a reclaim / bullish divergence as the trigger.")
        elif rsi < 45:
            look_for.append(f"RSI {rsi:.0f}: soft — a dip into the zone with RSI stabilizing is the cue.")
        else:
            look_for.append(f"RSI {rsi:.0f}: neutral — room to move either way.")
    # Sentiment extremes
    fgv = fg.get("value")
    if fgv is not None:
        if fgv >= 75:
            look_for.append(f"Fear & Greed {fgv} (extreme greed): crowded — tighten risk on new longs.")
        elif fgv <= 25:
            look_for.append(f"Fear & Greed {fgv} (extreme fear): contrarian long territory — wait for price to stabilize.")
        else:
            look_for.append(f"Fear & Greed {fgv} ({fg.get('label', '')}): no sentiment extreme.")

    # Known levels we can anchor an entry against
    level_pool = [
        ind.get("sma_fast"), ind.get("sma_slow"), ind.get("sma_200"),
        levels.get("low_14d"), levels.get("high_14d"),
    ]

    def _zone(values: list[float]) -> tuple:
        vals = sorted(v for v in values if v is not None)
        if len(vals) >= 2:
            return vals[0], vals[-1]
        if len(vals) == 1:
            return vals[0] * 0.99, vals[0] * 1.005
        return None, None

    if px is None:
        return {
            "bias": "WAIT", "target_entry": "—", "stop_hint": None,
            "headline": "No price data — cannot form a setup.", "look_for": look_for,
        }

    directional = conf >= 0.5 and (bullish != bearish)
    lo = hi = stop = None

    if directional and bullish:
        bias = "LONG"
        below = sorted(v for v in level_pool if v is not None and v < px)
        lo, hi = _zone(below[-2:]) if below else (px * 0.97, px * 0.99)
        stop = (lo or px) * 0.98
        headline = f"LONG bias — {state} regime at {conf:.0%} confidence. Buy pullbacks, don't chase."
        look_for.append("Plan: wait for a pullback into the entry zone; enter on stabilization, not a falling knife.")
    elif directional and bearish:
        bias = "SHORT"
        above = sorted(v for v in level_pool if v is not None and v > px)
        lo, hi = _zone(above[:2]) if above else (px * 1.01, px * 1.03)
        stop = (hi or px) * 1.02
        headline = f"SHORT bias — {state} regime at {conf:.0%} confidence. Sell rallies into resistance."
        look_for.append("Plan: wait for a bounce into the entry zone; enter on rejection, not breakdown chasing.")
    else:
        bias = "WAIT"
        reason = "regime confidence below 50%" if conf < 0.5 else "regime signals are mixed"
        headline = f"WAIT — no clean setup ({reason}). Let the market show its hand."
        look_for.append("Plan: stay flat until bias + confirmations align; protect capital first.")

    direction = {"LONG": "long", "SHORT": "short"}.get(bias)
    entry_mid = (lo + hi) / 2 if (lo and hi) else None

    # Suggested leverage: keep the (isolated, est.) liquidation beyond the stop,
    # with a safety buffer, and cap conservatively for swing trades.
    suggested_leverage = None
    if direction and entry_mid and stop:
        stop_dist = abs(entry_mid - stop) / entry_mid     # fraction to stop
        if stop_dist > 0:
            suggested_leverage = max(1, min(3, int(0.6 / stop_dist)))

    return {
        "bias":         bias,
        "direction":    direction,                        # 'long' | 'short' | None
        "target_entry": f"${lo:,.0f} – ${hi:,.0f}" if (lo and hi) else "—",
        "entry":        round(entry_mid) if entry_mid else None,
        "stop":         round(stop) if stop else None,
        "stop_hint":    f"${stop:,.0f}" if stop else None,
        "suggested_leverage": suggested_leverage,
        "headline":     headline,
        "look_for":     look_for,
    }


# ─── Claude synthesis ─────────────────────────────────────────────────────── #

_SYSTEM = """\
You are a professional BTC trader and technical analyst. You receive structured data:
regime state, technical indicators, Fear & Greed sentiment, and recent news headlines.
Your job: synthesize everything into a CLEAR, SPECIFIC swing trade plan for the next
3–7 days using conservative leverage (1–2x max). Assume the human places the trade
manually on their exchange.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

## CURRENT PICTURE
2–3 sentences: regime + price action + sentiment context. Be honest about uncertainty.

## BIAS: [LONG | SHORT | NEUTRAL — WAIT]
One sentence on the directional lean and the single strongest reason for it.

## TRADE PLAN
Direction : Long / Short / WAIT — no setup yet
Entry zone: $XX,XXX – $XX,XXX  (describe the level or trigger to watch)
Stop loss : $XX,XXX  (where the thesis breaks — keep it concrete)
Target 1  : $XX,XXX
Target 2  : $XX,XXX  (extension if momentum continues)
Leverage  : Xх  (1–2x; swing trades don't need more)
Hold time : X–X days
Invalidation: one sentence — what would make you skip or exit early

## KEY RISKS
- (2–3 specific bullets — macro, on-chain, sentiment, or technical)

If conditions don't warrant a trade, say WAIT with a precise description of what
setup you need to see before entering. Never force a call.
"""


def build_prompt(regime: dict, ind: dict, levels: dict, fg: dict, news: list[dict]) -> str:
    def _fmt(v, fmt=",.0f", fallback="N/A"):
        return format(v, fmt) if v is not None else fallback

    fg_str = f"{fg['value']}/100 — {fg['label']}" if fg.get("value") else "unavailable"
    fg_trend = ""
    if fg.get("value") and fg.get("yesterday"):
        d = fg["value"] - fg["yesterday"]
        fg_trend = f"  (yesterday {fg['yesterday']}, Δ {d:+d})"
    if fg.get("last_week") and fg.get("value"):
        fg_trend += f"  (last week {fg['last_week']})"

    rsi_val = _fmt(ind["rsi"], ".1f")
    macd_val = _fmt(ind["macd_hist"], "+.5f")
    macd_dir = "bullish" if ind["macd_hist"] and ind["macd_hist"] > 0 else "bearish"
    adx_val  = _fmt(ind["adx"], ".1f")
    mom_val  = _fmt(ind["momentum"] and ind["momentum"] * 100, "+.2f") + "%" if ind["momentum"] is not None else "N/A"

    checks_str = "\n".join(
        f"  {'✓' if ok else '✗'} {name}" for name, ok in ind["checks"]
    )
    headlines = "\n".join(f"  · [{a['source']}] {a['title'][:90]}" for a in news)

    return f"""\
BTC SWING TRADE DATA DUMP — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}

── PRICE ──
Current price : ${levels['current']:>12,.0f}
24h change    : {_fmt(levels['change_24h'], '+.1f')}%
7d change     : {_fmt(levels['change_7d'],  '+.1f')}%
30d change    : {_fmt(levels['change_30d'], '+.1f')}%
14d high/low  : ${levels['high_14d']:,.0f} / ${levels['low_14d']:,.0f}

── REGIME (Hidden Markov Model, causal — no lookahead) ──
Stance        : {regime['stance'].upper()}
Confidence    : {regime['confidence']:.1%}
State label   : {regime['state_name']}

── TECHNICAL INDICATORS ──
RSI(14)           : {rsi_val}
MACD histogram    : {macd_val}  ({macd_dir})
ADX(14)           : {adx_val}
24h momentum      : {mom_val}
SMA 24h           : ${_fmt(ind['sma_fast'])}
SMA 72h           : ${_fmt(ind['sma_slow'])}
SMA 200h          : ${_fmt(ind['sma_200'])}
Price vs SMA 200h : {"ABOVE (macro uptrend)" if ind['above_200'] else "BELOW (macro downtrend)"}
Confirmations     : {ind['n_pass']}/{ind['n_total']} passing
{checks_str}

── SENTIMENT ──
Fear & Greed: {fg_str}{fg_trend}
(Interpretation: <25 = extreme fear, 25–45 = fear, 45–55 = neutral, 55–75 = greed, >75 = extreme greed)

── RECENT BTC HEADLINES ──
{headlines}

Synthesize all of the above into a swing trade plan.
"""


def call_claude(prompt: str) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return "[anthropic SDK not installed: pip install anthropic]"
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ─── Display ─────────────────────────────────────────────────────────────── #

def _fg_bar(value: int, width: int = 50) -> str:
    filled = round(value / 100 * width)
    bar    = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {value}/100"


def print_report(regime, ind, levels, fg, news):
    W = 70
    sep = "═" * W
    print(f"\n{sep}")
    print(f"  BTC MARKET INTEL  ·  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print(sep)
    px = levels["current"]
    print(f"  Price    ${px:>12,.0f}", end="")
    if levels["change_24h"] is not None:
        arrow = "▲" if levels["change_24h"] > 0 else "▼"
        print(f"   24h {arrow}{abs(levels['change_24h']):.1f}%", end="")
    if levels["change_7d"] is not None:
        arrow = "▲" if levels["change_7d"] > 0 else "▼"
        print(f"   7d {arrow}{abs(levels['change_7d']):.1f}%", end="")
    print()
    print(f"  Range    ${levels['low_14d']:,.0f}  –  ${levels['high_14d']:,.0f}  (14d)")

    stance_color = {"long": "LONG ▲", "avoid": "AVOID ▼", "neutral": "NEUTRAL ─"}.get(
        regime["stance"], regime["stance"].upper()
    )
    print(f"\n  Regime   {stance_color}  ({regime['state_name']})  conf {regime['confidence']:.0%}")
    print(f"  Signals  {ind['n_pass']}/{ind['n_total']} confirming")
    if ind["rsi"] is not None:
        print(f"  RSI(14)  {ind['rsi']:.1f}", end="")
        if   ind["rsi"] > 70: print("  (overbought)", end="")
        elif ind["rsi"] < 30: print("  (oversold)", end="")
        print()
    trend_str = "above 200h SMA — macro uptrend" if ind["above_200"] else "below 200h SMA — macro downtrend"
    print(f"  Trend    {trend_str}")

    if fg.get("value") is not None:
        print(f"\n  Fear & Greed  {_fg_bar(fg['value'])}")
        print(f"                {fg['label']}", end="")
        if fg.get("yesterday"):
            d = fg["value"] - fg["yesterday"]
            print(f"  (vs yesterday {fg['yesterday']}, Δ{d:+d})", end="")
        print()

    print(f"\n  HEADLINES:")
    for a in news[:8]:
        print(f"    · {a['title'][:72]}")
    print(sep)


# ─── Main ─────────────────────────────────────────────────────────────────── #

def main():
    ap = argparse.ArgumentParser(description="BTC swing trade intelligence report")
    ap.add_argument("--source",    default="kucoin",
                    choices=["kucoin","coinbase","yfinance","github","synthetic"])
    ap.add_argument("--ticker",    default="BTC-USDT")
    ap.add_argument("--days",      type=int, default=90,
                    help="bars of history to feed the regime model (default 90)")
    ap.add_argument("--no-claude", action="store_true",
                    help="skip AI synthesis — print raw data only")
    ap.add_argument("--loop",      type=int, default=0,
                    help="re-run every N seconds (0 = run once)")
    args = ap.parse_args()

    while True:
        print(f"\nFetching {args.days}d of {args.ticker} from {args.source}…", flush=True)
        bars = load_recent(args.source, args.ticker, args.days)
        if not bars:
            print("No data returned — check source/ticker."); break

        print("Running regime model…", flush=True)
        regime = analyze_regime(bars)
        ind    = analyze_indicators(bars)
        levels = price_levels(bars)

        print("Fetching sentiment…", flush=True)
        fg   = fetch_fear_greed()
        news = fetch_news()

        print_report(regime, ind, levels, fg, news)

        use_claude = not args.no_claude and os.environ.get("ANTHROPIC_API_KEY")
        if use_claude:
            print("\nGenerating swing trade plan…\n", flush=True)
            prompt = build_prompt(regime, ind, levels, fg, news)
            plan   = call_claude(prompt)
            if plan:
                print(plan)
        elif not args.no_claude:
            print("\n  Set ANTHROPIC_API_KEY to enable the AI swing trade plan.\n")

        if args.loop <= 0:
            break
        next_run = time.strftime("%H:%M:%S", time.localtime(time.time() + args.loop))
        print(f"\n  Next update at {next_run} (Ctrl+C to stop)…", flush=True)
        try:
            time.sleep(args.loop)
        except KeyboardInterrupt:
            print("\nStopped."); break


if __name__ == "__main__":
    main()
