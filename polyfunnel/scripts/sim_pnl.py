"""sim_pnl.py — hypothetical PnL replay of three toy strategies against the
REAL collected order books + REAL Chainlink settlement outcomes.

NOT realized PnL. Nothing has traded. This charges the live-verified 0.07
crypto taker fee (config/costs.yaml) and enters at ~T-60s to settlement.

Each strategy stakes a fixed $100 of *cost* per trade (shares = 100/entry),
so every bet risks comparable capital. Equity is cumulative $ PnL.
"""
import gzip
import json
import glob
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECT = os.path.join(ROOT, "data", "collect", "btc-up-or-down-5m")
TAKER_RATE = 0.07          # crypto_fees_v2, live-verified 2026-07-06
STAKE = 100.0              # fixed $ cost per trade
ENTRY_OFFSET = 60.0        # seconds before end_date to enter
TOL = 45.0                 # accept a snapshot within +/- this of the target


def iso_to_epoch(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(
        tzinfo=timezone.utc).timestamp()


def load_outcomes():
    out = {}
    for f in glob.glob(os.path.join(COLLECT, "*", "outcomes.ndjson")):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("settled") and r.get("winner") in ("Up", "Down"):
                out[r["market_id"]] = {
                    "winner": r["winner"],
                    "end": iso_to_epoch(r["end_date"]),
                }
    return out


def best_ask(book):
    asks = [float(a["price"]) for a in book.get("asks", [])]
    return min(asks) if asks else None


def best_bid(book):
    bids = [float(b["price"]) for b in book.get("bids", [])]
    return max(bids) if bids else None


def load_book_series():
    """market_id -> ts-sorted list of snapshots:
       {ts, Up:(bid,ask), Down:(bid,ask)} (only fully-two-sided snapshots)."""
    raw = {}
    files = glob.glob(os.path.join(COLLECT, "*", "books-*.ndjson.gz")) + \
        glob.glob(os.path.join(COLLECT, "*", "books-*.ndjson"))
    for fp in files:
        opener = gzip.open if fp.endswith(".gz") else open
        with opener(fp, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    b = json.loads(line)
                except json.JSONDecodeError:
                    continue  # tolerate a torn final line in a live file
                mid, oc = b.get("market_id"), b.get("outcome")
                bid, ask = best_bid(b), best_ask(b)
                if mid is None or oc not in ("Up", "Down") or ask is None or bid is None:
                    continue
                raw.setdefault(mid, {}).setdefault(round(b["ts"], 1), {})[oc] = (bid, ask)
    series = {}
    for mid, by_ts in raw.items():
        snaps = [{"ts": ts, "Up": s["Up"], "Down": s["Down"]}
                 for ts, s in by_ts.items() if "Up" in s and "Down" in s]
        snaps.sort(key=lambda s: s["ts"])
        if snaps:
            series[mid] = snaps
    return series


def entry_index(snaps, target):
    """Index of the snapshot whose ts is closest to target (within TOL)."""
    best = None
    for i, s in enumerate(snaps):
        d = abs(s["ts"] - target)
        if d <= TOL and (best is None or d < best[0]):
            best = (d, i)
    return best[1] if best else None


def simulate():
    outcomes = load_outcomes()
    books = load_book_series()

    strategies = {
        "naive_taker": [],    # taker: buy the favorite at the ask
        "longshot_fade": [],  # taker: buy favorite only when favorite ask >= 0.80
        "coinflip_up": [],    # taker: always buy Up at the ask
        "maker_fav": [],      # maker: post at the favorite's bid, 0 fee, modeled fill
    }
    trades_meta = []
    matched = 0
    maker_attempts = 0   # markets where we posted a maker bid
    maker_fills = 0      # of those, ones the fill proxy filled

    for mid, oc in sorted(outcomes.items(), key=lambda kv: kv[1]["end"]):
        if mid not in books:
            continue
        snaps = books[mid]
        ei = entry_index(snaps, oc["end"] - ENTRY_OFFSET)
        if ei is None:
            continue
        entry = snaps[ei]
        up_bid, up_ask = entry["Up"]
        down_bid, down_ask = entry["Down"]
        matched += 1
        winner = oc["winner"]

        def taker(side, ask):
            shares = STAKE / ask
            payoff = shares if side == winner else 0.0
            fee = shares * TAKER_RATE * ask * (1 - ask)
            return payoff - STAKE - fee

        fav_side = "Up" if up_ask >= down_ask else "Down"
        fav_ask = up_ask if fav_side == "Up" else down_ask
        fav_bid = up_bid if fav_side == "Up" else down_bid

        strategies["naive_taker"].append((oc["end"], taker(fav_side, fav_ask)))
        if fav_ask >= 0.80:
            strategies["longshot_fade"].append((oc["end"], taker(fav_side, fav_ask)))
        strategies["coinflip_up"].append((oc["end"], taker("Up", up_ask)))

        # --- Maker: post a buy on the favorite at its best bid, hold to close. ---
        # No trade tape is collected, so the fill is MODELED, not observed.
        # Conservative trade-through proxy: the resting bid fills iff, in a later
        # in-window snapshot, the favorite's best bid trades below our posted price
        # (our price level got cleared => a taker sold through us). Maker fee = 0;
        # rebates would only help and are deliberately NOT credited (conservative).
        maker_attempts += 1
        post = fav_bid
        filled = any(
            (s["Up"][0] if fav_side == "Up" else s["Down"][0]) < post - 1e-9
            for s in snaps[ei + 1:] if s["ts"] <= oc["end"]
        )
        if filled:
            maker_fills += 1
            shares = STAKE / post
            payoff = shares if fav_side == winner else 0.0
            strategies["maker_fav"].append((oc["end"], payoff - STAKE))  # 0 fee

        trades_meta.append({
            "end": oc["end"], "winner": winner,
            "fav_side": fav_side, "fav_ask": round(fav_ask, 3),
            "fav_bid": round(fav_bid, 3), "maker_filled": filled,
            "up_ask": round(up_ask, 3), "down_ask": round(down_ask, 3),
        })

    curves = {}
    for name, trades in strategies.items():
        trades.sort(key=lambda t: t[0])
        eq, cum = [], 0.0
        for end, pnl in trades:
            cum += pnl
            eq.append({"t": end, "eq": round(cum, 2)})
        wins = sum(1 for _, p in trades if p > 0)
        curves[name] = {
            "equity": eq,
            "n": len(trades),
            "final": round(cum, 2),
            "hit_rate": round(wins / len(trades), 3) if trades else None,
            "avg_pnl": round(cum / len(trades), 3) if trades else None,
        }

    # maker-specific diagnostics: fill rate and hit-rate CONDITIONAL on filling
    # (the adverse-selection tell — a maker only fills when price came to them).
    m = curves["maker_fav"]
    m["attempts"] = maker_attempts
    m["fills"] = maker_fills
    m["fill_rate"] = round(maker_fills / maker_attempts, 3) if maker_attempts else None
    # unconditional hit rate across ALL attempts (missed = no position, not a loss)
    m["hit_rate_if_all_filled"] = None

    return {"matched_markets": matched, "settled_total": len(outcomes),
            "curves": curves, "trades": trades_meta}


if __name__ == "__main__":
    res = simulate()
    print(f"settled markets:        {res['settled_total']}")
    print(f"matched w/ T-60 book:   {res['matched_markets']}")
    print()
    for name, c in res["curves"].items():
        extra = ""
        if name == "maker_fav":
            extra = f"  fill_rate={c['fill_rate']} ({c['fills']}/{c['attempts']})"
        print(f"{name:16s}  n={c['n']:3d}  hit={c['hit_rate']}  "
              f"avg/trade=${c['avg_pnl']}  final=${c['final']}{extra}")
    outp = os.path.join(ROOT, "data", "sim_pnl.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(f"\nwrote {outp}")

    # Append a compact run record so the artifact can show edge-vs-sample-size
    # decay across reruns (answers "did the edge survive more data?").
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settled": res["settled_total"],
        "matched": res["matched_markets"],
        "avg_pnl": {k: c["avg_pnl"] for k, c in res["curves"].items()},
    }
    hist = os.path.join(ROOT, "data", "sim_history.ndjson")
    prev = []
    if os.path.exists(hist):
        prev = [json.loads(l) for l in open(hist, encoding="utf-8") if l.strip()]
    # de-dupe: only append if the matched count changed since the last record
    if not prev or prev[-1].get("matched") != rec["matched"]:
        with open(hist, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"appended run to {hist}")
    else:
        print("sample unchanged since last run — history not appended")
