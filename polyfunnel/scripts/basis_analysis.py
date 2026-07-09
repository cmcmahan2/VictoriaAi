#!/usr/bin/env python3
"""Basis-alignment analysis: does the Binance-vs-Chainlink basis in the final
seconds predict the Chainlink settlement BEYOND what the order book already prices?

Economic hypothesis (from vault research): 5m up/down markets settle on the
Chainlink BTC/USD stream, which lags/smooths spot. Binance leads it. So in the
final seconds the Binance price may already "know" where Chainlink will land —
an edge iff the book hasn't priced it. This script measures exactly that, and
states a KILL CRITERION so we bank a null instead of tuning (operating principle #1).

Inputs (all live-collected, stdlib-only):
  data/collect/rtds/*/prices-*.ndjson[.gz]   Chainlink btc/usd + Binance btcusdt ticks
  data/collect/btc-up-or-down-5m/*/outcomes.ndjson   settled winners (+ slug = window start)
  data/collect/btc-up-or-down-5m/*/books-*.ndjson[.gz]   Up/Down books (implied prob)

A 5m window: start_unix = int(slug after last '-'); end_unix = start+300.
Strike = Chainlink at start; settles Up iff Chainlink(end) >= strike (ties Up).

Run:  python scripts/basis_analysis.py [--offsets 1,3,5,10] [--min-n 30]
Outputs a coverage report, a referee sanity check, the basis-lead test, and the
marginal-edge-over-book test; writes data/basis_analysis.json.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECT = os.path.join(ROOT, "data", "collect")
TAKER_RATE = 0.07                 # crypto_fees_v2, live-verified
WINDOW_S = 300                    # 5-minute markets
NEAR_TOL = 2                      # accept a tick within +/- this many seconds
CONTESTED = (0.40, 0.60)          # book-implied Up prob band where an edge matters


def _open(fp):
    return gzip.open(fp, "rt", encoding="utf-8") if fp.endswith(".gz") else open(fp, encoding="utf-8")


def load_rtds():
    """-> (chainlink_by_sec, binance_by_sec): unix_second -> price (last wins)."""
    cl, bn = {}, {}
    for fp in glob.glob(os.path.join(COLLECT, "rtds", "*", "prices-*.ndjson*")):
        with _open(fp) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                p = r.get("payload")
                if not isinstance(p, dict):
                    continue
                sym = p.get("symbol")
                tgt = cl if sym == "btc/usd" else bn if sym == "btcusdt" else None
                if tgt is None:
                    continue
                if "data" in p:                       # snapshot backfill array
                    for d in p["data"]:
                        tgt[d["timestamp"] // 1000] = float(d["value"])
                elif "timestamp" in p and "value" in p:  # live update tick
                    tgt[p["timestamp"] // 1000] = float(p["value"])
    return cl, bn


def near(series: dict, t: int, tol: int = NEAR_TOL):
    """Value at the second closest to t within tol, else None."""
    for d in range(tol + 1):
        for s in ((t + d, t - d) if d else (t,)):
            if s in series:
                return series[s]
    return None


def load_windows():
    """-> list of {start, end, winner} from settled outcomes."""
    wins = []
    for fp in glob.glob(os.path.join(COLLECT, "btc-up-or-down-5m", "*", "outcomes.ndjson")):
        for line in _open(fp):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("settled") and r.get("winner") in ("Up", "Down"):
                try:
                    start = int(r["slug"].rsplit("-", 1)[1])
                except (KeyError, ValueError):
                    continue
                wins.append({"start": start, "end": start + WINDOW_S,
                             "winner": r["winner"], "slug": r["slug"]})
    # de-dup by slug (provisional + settled may both appear), keep settled
    by_slug = {w["slug"]: w for w in wins}
    return sorted(by_slug.values(), key=lambda w: w["start"])


def load_book_up_mid():
    """-> slug -> sorted list of (ts, up_mid_prob). up_mid = mid of the Up token."""
    series = defaultdict(list)
    files = glob.glob(os.path.join(COLLECT, "btc-up-or-down-5m", "*", "books-*.ndjson*"))
    for fp in files:
        with _open(fp) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    b = json.loads(line)
                except ValueError:
                    continue
                if b.get("outcome") != "Up":
                    continue
                bids = [float(x["price"]) for x in b.get("bids", [])]
                asks = [float(x["price"]) for x in b.get("asks", [])]
                if not bids or not asks:
                    continue
                mid = (max(bids) + min(asks)) / 2
                series[b["slug"]].append((b["ts"], mid, max(bids), min(asks)))
    for s in series.values():
        s.sort(key=lambda r: r[0])
    return series


def book_at(rows, t):
    """Nearest book row (ts, mid, best_bid, best_ask) to time t; None if empty."""
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r[0] - t))


def sign(x):
    return 1 if x > 0 else -1 if x < 0 else 0


def analyze(offsets, min_n):
    cl, bn = load_rtds()
    windows = load_windows()
    books = load_book_up_mid()

    # ---- Coverage ----
    strike_ok = []      # windows with chainlink at start AND end
    for w in windows:
        strike = near(cl, w["start"])
        close = near(cl, w["end"])
        if strike is not None and close is not None:
            w["strike"], w["close"] = strike, close
            strike_ok.append(w)

    cov = {
        "rtds_chainlink_secs": len(cl), "rtds_binance_secs": len(bn),
        "settled_windows": len(windows),
        "strike_computable_windows": len(strike_ok),
    }

    result = {"coverage": cov, "offsets": offsets, "min_n": min_n}

    if not strike_ok:
        result["status"] = "INSUFFICIENT_DATA"
        result["note"] = ("No window has Chainlink ticks at both its start and end. "
                          "Run collect_rtds.py alongside collect_updown.py for a few "
                          "days, then re-run. The harness is correct and waiting on tape.")
        return result

    # ---- Referee sanity: does Chainlink(end)>=strike match the official winner? ----
    agree = sum(1 for w in strike_ok
                if ("Up" if w["close"] >= w["strike"] else "Down") == w["winner"])
    result["referee_check"] = {
        "n": len(strike_ok),
        "match_rate": round(agree / len(strike_ok), 4),
        "note": "should be ~1.0; confirms strike logic + feed align with settlement",
    }

    # ---- Per-offset: basis-lead + marginal-edge-over-book ----
    per_offset = {}
    for N in offsets:
        lead_n = lead_hit = 0                 # sign(basis) predicts residual Chainlink move
        contested = []                        # (basis_side, winner, ask, book_fav_side)
        for w in strike_ok:
            t0 = w["end"] - N
            c_now = near(cl, t0)
            b_now = near(bn, t0)
            if c_now is None or b_now is None:
                continue
            basis = b_now - c_now
            move = w["close"] - c_now         # residual Chainlink move to settlement
            if sign(basis) != 0 and sign(move) != 0:
                lead_n += 1
                lead_hit += (sign(basis) == sign(move))
            # marginal edge vs book, on contested windows only
            brow = book_at(books.get(w["slug"], []), t0)
            if brow is None:
                continue
            _, up_mid, bbid, bask = brow
            if not (CONTESTED[0] <= up_mid <= CONTESTED[1]):
                continue
            basis_side = "Up" if basis > 0 else "Down"
            book_fav = "Up" if up_mid >= 0.5 else "Down"
            contested.append((basis_side, w["winner"], up_mid, bbid, bask, book_fav))

        entry = {"basis_lead": None, "edge_vs_book": None}
        if lead_n >= min_n:
            entry["basis_lead"] = {
                "n": lead_n, "hit_rate": round(lead_hit / lead_n, 4),
                "reading": "share of windows where basis sign matched the final Chainlink move",
            }
        elif lead_n:
            entry["basis_lead"] = {"n": lead_n, "hit_rate": None,
                                   "reading": f"n<{min_n}; not enough to read"}

        if len(contested) >= min_n:
            basis_hit = sum(1 for bs, wn, *_ in contested if bs == wn) / len(contested)
            book_hit = sum(1 for bs, wn, um, bb, ba, bf in contested if bf == wn) / len(contested)
            # naive taker PnL: buy basis-favored side at its ask ($100 stake), hold to settle
            pnl = 0.0
            for bs, wn, um, bb, ba, bf in contested:
                # ask of the basis side: Up ask = min Up asks (~1-? ); we only stored Up book.
                # Up side price ~ up_mid; approx side ask by up_mid for Up, (1-up_mid) for Down.
                px = ba if bs == "Up" else (1 - bb)  # crude: Down ask ~ 1 - Up bid
                px = min(max(px, 0.01), 0.99)
                shares = 100.0 / px
                payoff = shares if bs == wn else 0.0
                fee = shares * TAKER_RATE * px * (1 - px)
                pnl += payoff - 100.0 - fee
            # Rough noise band: SE of a proportion at p~0.5 on n windows. The
            # paired diff's true SE is smaller, so 2*SE is a conservative bar.
            se = 0.5 / math.sqrt(len(contested))
            diff = basis_hit - book_hit
            entry["edge_vs_book"] = {
                "n_contested": len(contested),
                "basis_side_hit_rate": round(basis_hit, 4),
                "book_favorite_hit_rate": round(book_hit, 4),
                "basis_minus_book": round(diff, 4),
                "se_pp": round(se * 100, 2),
                "significant": diff > 2 * se,   # edge exceeds the noise band
                "naive_taker_pnl_usd": round(pnl, 2),
                "reading": "edge is real only if significant across offsets AND pnl>0",
            }
        elif contested:
            entry["edge_vs_book"] = {"n_contested": len(contested),
                                     "reading": f"n<{min_n}; not enough contested windows"}
        per_offset[f"T-{N}s"] = entry
    result["per_offset"] = per_offset

    # ---- Verdict (guard against cherry-picking across offsets) ----
    # Selecting the best offset from several noisy ones manufactures false
    # positives (principle #1: don't tune until something "works"). Require the
    # edge to hold CONSISTENTLY — a majority of offsets individually significant
    # and positive, a mean edge past a real threshold, and mean PnL > 0.
    edges = [o["edge_vs_book"] for o in per_offset.values()
             if o.get("edge_vs_book") and "basis_minus_book" in o["edge_vs_book"]]
    if not edges:
        result["verdict"] = ("INCONCLUSIVE — not enough contested windows at any offset. "
                             "Collect more aligned tape and re-run.")
    else:
        diffs = [e["basis_minus_book"] for e in edges]
        pnls = [e["naive_taker_pnl_usd"] for e in edges]
        pos_sig = [e for e in edges if e["significant"] and e["basis_minus_book"] > 0]
        mean_diff = sum(diffs) / len(diffs)
        mean_pnl = sum(pnls) / len(pnls)
        result["verdict_stats"] = {
            "offsets_readable": len(edges),
            "offsets_significant_positive": len(pos_sig),
            "mean_basis_minus_book_pp": round(mean_diff * 100, 2),
            "mean_naive_taker_pnl_usd": round(mean_pnl, 2),
        }
        if len(pos_sig) >= math.ceil(len(edges) / 2) and mean_diff > 0.03 and mean_pnl > 0:
            result["verdict"] = ("SIGNAL CANDIDATE — basis beats the book consistently "
                                 f"(mean {mean_diff*100:+.1f}pp across {len(edges)} offsets, "
                                 f"{len(pos_sig)} individually significant) with positive PnL. "
                                 "Confirm on held-out days before believing it.")
        elif mean_diff <= 0.02 and not pos_sig:
            result["verdict"] = ("NULL (kill criterion met) — basis adds <=2pp over the book "
                                 "and no offset clears the noise band. The book already prices "
                                 "the basis. Bank the null; do not tune.")
        else:
            result["verdict"] = ("INCONCLUSIVE — an offset or two looks positive but the edge "
                                 "isn't consistent or significant across offsets (likely noise). "
                                 "Do NOT trade it; collect more tape and re-run.")
    return result


def fmt(result):
    out = []
    c = result["coverage"]
    out.append("BASIS-ALIGNMENT ANALYSIS  (Binance vs Chainlink, final seconds)")
    out.append("-" * 62)
    out.append(f"RTDS coverage:  chainlink {c['rtds_chainlink_secs']}s  "
               f"binance {c['rtds_binance_secs']}s")
    out.append(f"settled windows: {c['settled_windows']}  |  "
               f"strike-computable (RTDS@start+end): {c['strike_computable_windows']}")
    if result.get("status") == "INSUFFICIENT_DATA":
        out.append("")
        out.append("STATUS: INSUFFICIENT DATA")
        out.append("  " + result["note"])
        return "\n".join(out)
    r = result["referee_check"]
    out.append("")
    out.append(f"Referee check: computed==official on {r['match_rate']*100:.1f}% "
               f"of {r['n']} windows  (want ~100%)")
    for label, e in result["per_offset"].items():
        out.append("")
        out.append(f"[{label}]")
        bl = e["basis_lead"]
        if bl and bl.get("hit_rate") is not None:
            out.append(f"  basis leads Chainlink: {bl['hit_rate']*100:.1f}% "
                       f"(n={bl['n']})  [50% = no lead]")
        elif bl:
            out.append(f"  basis leads Chainlink: {bl['reading']}")
        ev = e["edge_vs_book"]
        if ev and "basis_minus_book" in ev:
            out.append(f"  contested windows (book Up-prob in {CONTESTED}): n={ev['n_contested']}")
            out.append(f"    basis-side wins:     {ev['basis_side_hit_rate']*100:.1f}%")
            out.append(f"    book-favorite wins:  {ev['book_favorite_hit_rate']*100:.1f}%")
            out.append(f"    basis - book:        {ev['basis_minus_book']*100:+.1f}pp "
                       f"(±{ev['se_pp']:.1f}pp noise; "
                       f"{'SIGNIFICANT' if ev['significant'] else 'within noise'})")
            out.append(f"    naive taker PnL:     ${ev['naive_taker_pnl_usd']:+,.2f}")
        elif ev:
            out.append(f"  edge vs book: {ev['reading']}")
    out.append("")
    out.append("VERDICT: " + result["verdict"])
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offsets", default="1,3,5,10",
                    help="seconds-before-close to test (comma-separated)")
    ap.add_argument("--min-n", type=int, default=30,
                    help="minimum windows before a statistic is reported")
    a = ap.parse_args()
    offsets = [int(x) for x in a.offsets.split(",") if x.strip()]
    result = analyze(offsets, a.min_n)
    print(fmt(result))
    outp = os.path.join(ROOT, "data", "basis_analysis.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nwrote {outp}")


if __name__ == "__main__":
    main()
