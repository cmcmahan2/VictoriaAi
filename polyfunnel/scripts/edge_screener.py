#!/usr/bin/env python3
"""Edge screener v0 — an OddsJam-style scan across all of Polymarket.

Run:  PYTHONPATH=src python3 scripts/edge_screener.py [--events 400]
Outputs: console summary + docs/edge_screener.json (raw rows for the page
builder). Stdlib-only, ~2 req/s against Gamma; top arb candidates are
re-verified against live CLOB books before being reported.

What counts as an "edge" here (honesty rules):
  A. SET ARBITRAGE (provable, model-free) — negRisk events (mutually
     exclusive outcomes, exactly one YES pays $1):
       buy-all-YES:  sum(best asks) + taker fees < $1   -> locked profit
       buy-all-NO:   sum(1 - best bids) + fees < n - 1  -> locked profit
         (equivalent condition: sum of YES bids > $1)
     Caveats flagged per hit: gamma quotes are cached (~30-60s) so hits are
     re-checked against live CLOB books; a closed constituent that already
     resolved YES poisons the set (skipped); exhaustiveness is assumed from
     negRisk=true. Depth is top-of-book only — size the smallest leg.
  B. MAKER YIELD (structural, no direction) — two-sided markets ranked by
     spread x 24h volume (quoting revenue proxy), with the market's reward
     program fields (rebateRate, rewardsMinSize/MaxSpread) shown.
  C. FEE-FREE BOARD — feesEnabled=false markets by 24h volume: the segment
     where edges skip the 3-7% taker fee wall entirely.

This screener finds *candidates*, not certainties: everything acts at
top-of-book depth and quotes move. Verify live before committing capital.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polyfunnel.api.clob import ClobPublic  # noqa: E402
from polyfunnel.api.gamma import GammaClient  # noqa: E402


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def taker_fee(rate: float, price: float) -> float:
    """Fee V2 taker fee per share bought at `price`."""
    return rate * price * (1.0 - price)


def fnum(x, default=None) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def market_row(m: dict) -> dict | None:
    bid, ask = fnum(m.get("bestBid")), fnum(m.get("bestAsk"))
    fee = (m.get("feeSchedule") or {})
    return {
        "question": m.get("question"),
        "slug": m.get("slug"),
        "bid": bid, "ask": ask,
        "two_sided": bool(bid and ask and 0 < bid < ask < 1),
        "closed": m.get("closed"),
        "active": m.get("active"),
        "accepting": m.get("acceptingOrders"),
        "outcome_prices": m.get("outcomePrices"),
        "fee_rate": fee.get("rate") or 0.0,
        "rebate_rate": fee.get("rebateRate"),
        "fees_enabled": m.get("feesEnabled"),
        "vol24": fnum(m.get("volume24hr"), 0.0),
        "liq": fnum(m.get("liquidityNum") or m.get("liquidity"), 0.0),
        "spread": fnum(m.get("spread")),
        "rewards_min_size": m.get("rewardsMinSize"),
        "rewards_max_spread": m.get("rewardsMaxSpread"),
        "tokens": json.loads(m.get("clobTokenIds") or "[]"),
        "end": m.get("endDate"),
    }


def scan_events(gamma: GammaClient, n_events: int) -> list[dict]:
    events, off = [], 0
    while len(events) < n_events:
        page = gamma.get("/events", limit=100, offset=off, closed="false",
                         order="volume24hr", ascending="false")
        if not page:
            break
        events += page
        off += 100
        time.sleep(0.4)
    return events[:n_events]


def set_arbs(events: list[dict], clob: ClobPublic) -> list[dict]:
    hits = []
    for ev in events:
        if not ev.get("negRisk"):
            continue
        markets = [m for m in ev.get("markets") or []]
        # a closed constituent that resolved YES means the set is decided
        poisoned = any(
            m.get("closed") and "1" in (m.get("outcomePrices") or "")[:6]
            for m in markets)
        rows = [r for m in markets if (r := market_row(m))
                and not r["closed"] and r["accepting"]]
        if poisoned or len(rows) < 2:
            continue
        if not all(r["two_sided"] for r in rows):
            continue
        n = len(rows)
        sum_ask = sum(r["ask"] for r in rows)
        sum_bid = sum(r["bid"] for r in rows)
        fee_yes = sum(taker_fee(r["fee_rate"], r["ask"]) for r in rows)
        fee_no = sum(taker_fee(r["fee_rate"], 1 - r["bid"]) for r in rows)
        yes_edge = 1.0 - (sum_ask + fee_yes)
        no_edge = (n - 1) - (sum(1 - r["bid"] for r in rows) + fee_no)
        best = max(yes_edge, no_edge)
        if best <= 0:
            continue
        side = "BUY-ALL-YES" if yes_edge >= no_edge else "BUY-ALL-NO"
        hits.append({
            "event": ev.get("title") or ev.get("slug"),
            "slug": ev.get("slug"), "n_outcomes": n, "side": side,
            "sum_ask": round(sum_ask, 4), "sum_bid": round(sum_bid, 4),
            "edge_per_set": round(best, 4),
            "ret_pct": round(100 * best / max(sum_ask, 1e-9), 2),
            "vol24": sum(r["vol24"] for r in rows),
            "rows": rows,
        })
    # live re-verification of top hits against CLOB books (gamma is cached)
    verified = []
    for h in sorted(hits, key=lambda x: -x["edge_per_set"])[:10]:
        toks = [r["tokens"][0] for r in h["rows"] if r["tokens"]]
        if len(toks) != h["n_outcomes"]:
            h["live_check"] = "skipped (missing tokens)"
            verified.append(h)
            continue
        try:
            books = clob.books(toks)
            by_tok = {b.get("asset_id"): b for b in books}
            la = sum(float(by_tok[t]["asks"][-1]["price"])
                     for t in toks if by_tok.get(t, {}).get("asks"))
            lb = sum(float(by_tok[t]["bids"][-1]["price"])
                     for t in toks if by_tok.get(t, {}).get("bids"))
            complete = all(by_tok.get(t, {}).get("asks") and
                           by_tok.get(t, {}).get("bids") for t in toks)
            h["live_sum_ask"] = round(la, 4) if complete else None
            h["live_sum_bid"] = round(lb, 4) if complete else None
            h["live_check"] = ("CONFIRMED" if complete and
                               (la < 1.0 or lb > 1.0) else
                               "GONE at live books" if complete else
                               "one-sided live book")
        except Exception as e:  # noqa: BLE001
            h["live_check"] = f"verify failed: {str(e)[:60]}"
        verified.append(h)
        time.sleep(0.3)
    return verified


def maker_yield(events: list[dict]) -> list[dict]:
    seen, out = set(), []
    for ev in events:
        for m in ev.get("markets") or []:
            r = market_row(m)
            if not r or r["slug"] in seen or not r["two_sided"]:
                continue
            seen.add(r["slug"])
            spr = r["ask"] - r["bid"]
            if spr < 0.02 or r["vol24"] < 10_000:
                continue
            out.append({**{k: r[k] for k in (
                "question", "slug", "bid", "ask", "vol24", "liq",
                "rebate_rate", "rewards_min_size", "rewards_max_spread",
                "fee_rate")},
                "spread": round(spr, 3),
                "score": round(spr * r["vol24"], 0)})
    out.sort(key=lambda x: -x["score"])
    return out[:20]


def fee_free_board(events: list[dict]) -> list[dict]:
    seen, out = set(), []
    for ev in events:
        for m in ev.get("markets") or []:
            r = market_row(m)
            if (not r or r["slug"] in seen or r["fees_enabled"]
                    or not r["two_sided"] or r["vol24"] < 5_000):
                continue
            seen.add(r["slug"])
            out.append({k: r[k] for k in (
                "question", "slug", "bid", "ask", "vol24", "liq", "spread")})
    out.sort(key=lambda x: -x["vol24"])
    return out[:20]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=400)
    a = ap.parse_args()
    gamma, clob = GammaClient(), ClobPublic()
    events = scan_events(gamma, a.events)
    print(f"scanned {len(events)} active events (by 24h volume) at {now_iso()}")

    arbs = set_arbs(events, clob)
    makers = maker_yield(events)
    free = fee_free_board(events)

    out = {"generated": now_iso(), "n_events": len(events),
           "set_arbs": [{k: v for k, v in h.items() if k != "rows"}
                        for h in arbs],
           "maker_yield": makers, "fee_free": free}
    dest = ROOT / "docs" / "edge_screener.json"
    dest.write_text(json.dumps(out, indent=1))
    print(f"wrote {dest}")

    print(f"\nA. SET ARBS (negRisk, fee-adjusted, live-checked): {len(arbs)}")
    for h in arbs[:5]:
        print(f"  {h['edge_per_set']*100:+.1f}c/set ({h['ret_pct']}%) "
              f"{h['side']} x{h['n_outcomes']} | {h['event'][:50]} "
              f"| live: {h.get('live_check')}")
    print(f"\nB. MAKER YIELD top5 (spread x vol24 proxy):")
    for r in makers[:5]:
        print(f"  ${r['score']:>10,.0f}  spr {r['spread']:.3f} "
              f"vol ${r['vol24']:,.0f} | {r['question'][:55]}")
    print(f"\nC. FEE-FREE BOARD top5 (no taker fee at all):")
    for r in free[:5]:
        print(f"  vol ${r['vol24']:>10,.0f}  {r['bid']:.2f}/{r['ask']:.2f} "
              f"| {r['question'][:55]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
