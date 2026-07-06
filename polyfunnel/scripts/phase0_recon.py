#!/usr/bin/env python3
"""Phase 0 recon: live API verification + market taxonomy scan.

Run:  PYTHONPATH=src .venv/bin/python scripts/phase0_recon.py
      (or system python3 — httpx/polars are optional, see below)

Produces:
  data/universe.parquet        one row per active market, bucketed + tagged
                               (falls back to data/universe.ndjson.gz when
                               polars is unavailable; data/ is gitignored)
  docs/UNIVERSE_REPORT.md      one-page report (bucket ranking table)
  config/costs.yaml            stamps meta.last_verified_live on fee verification

Requires outbound HTTPS to *.polymarket.com. The script fails loudly
(never silently) when endpoints are unreachable. In containers that can
reach Polymarket but not PyPI, the API clients fall back to a stdlib
HTTP shim and this script aggregates without polars.

Live API shapes this script was corrected against (2026-07-06):
- Gamma /markets no longer returns `category`; `feeType` (e.g.
  "crypto_fees_v2") is the closest server-side taxonomy and is used as
  the bucket fallback.
- Gamma caps `limit` at 100 and 422s past offset 2000 — full enumeration
  handled inside GammaClient.iter_markets (endDate-window pagination).
- Crypto up/down series now run at 5-minute recurrence with slugs like
  `btc-updown-5m-<unix_ts>` (recurrer patterns updated to match).
- `active=true&closed=false` includes stale markets whose endDate is in
  the past ("zombies"); rows carry an `expired` flag and the report
  counts them separately.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import polars as pl  # noqa: E402
except ModuleNotFoundError:  # no PyPI access in some containers
    pl = None

from polyfunnel.api.clob import ClobPublic  # noqa: E402
from polyfunnel.api.gamma import GammaClient  # noqa: E402

RECURRER_PATTERNS = [
    # slug patterns that identify structurally-repeating market series
    (re.compile(r"(bitcoin|btc).*(up-or-down|updown|hourly|-et$|15-?m|5-?m)", re.I), "crypto_btc_updown"),
    (re.compile(r"(ethereum|eth)-?.*(up-or-down|updown|hourly|15-?m|5-?m)", re.I), "crypto_eth_updown"),
    (re.compile(r"(solana|sol|xrp|doge)-.*(up-or-down|updown|hourly|15-?m|5-?m)", re.I), "crypto_alt_updown"),
    (re.compile(r"^(nba|nfl|mlb|nhl|epl|ucl|fifwc|atp|wta|wimbledon|lol|cs2)-|(-vs-)", re.I), "sports_game"),
    (re.compile(r"(fed-|cpi|nonfarm|jobs-report|gdp|fomc|rate-decision)", re.I), "econ_print"),
]


def bucket_market(m: dict) -> str:
    slug = (m.get("slug") or "").lower()
    for pat, name in RECURRER_PATTERNS:
        if pat.search(slug):
            return name
    cat = (m.get("category") or "").lower()
    if not cat:
        # live /markets returns category=null; feeType ("politics_fees",
        # "sports_fees_v2", ...) is the server's own category assignment
        cat = re.sub(r"_fees(_v2)?$", "", (m.get("feeType") or "").lower())
    return f"cat_{cat}" if cat else "cat_unknown"


def verify_apis(clob: ClobPublic, gamma: GammaClient) -> dict:
    """Hit each API family once; raise with a clear message on failure."""
    checks = {}
    checks["clob_time"] = clob.server_time()
    sample = gamma.get("/markets", limit=1, active="true", closed="false")
    checks["gamma_markets_ok"] = bool(sample)
    if sample:
        tok = json.loads(sample[0].get("clobTokenIds") or "[]")
        if tok:
            checks["clob_book_ok"] = bool(clob.book(tok[0]))
            checks["fee_rate_sample"] = clob.fee_rate(tok[0])
    return checks


def scan_universe(gamma: GammaClient) -> list[dict]:
    now_iso = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for m in gamma.iter_markets(active=True, closed=False):
        end = m.get("endDate")
        fee = m.get("feeSchedule") or {}
        rows.append({
            "id": m.get("id"),
            "slug": m.get("slug"),
            "question": m.get("question"),
            "category": m.get("category"),
            "fee_type": m.get("feeType"),
            "fee_rate": fee.get("rate"),
            "fees_enabled": m.get("feesEnabled"),
            "bucket": bucket_market(m),
            "volume_24h": float(m.get("volume24hr") or 0),
            "volume_total": float(m.get("volume") or 0),
            "liquidity": float(m.get("liquidity") or 0),
            "spread": float(m.get("spread") or 0),
            "best_bid": m.get("bestBid"),
            "best_ask": m.get("bestAsk"),
            "end_date": end,
            "expired": bool(end and end < now_iso),  # zombie: past end, not closed
            "clob_token_ids": m.get("clobTokenIds"),
            "neg_risk": m.get("negRisk"),
        })
    return rows


def write_universe(rows: list[dict]) -> Path:
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    if pl is not None:
        out = data_dir / "universe.parquet"
        pl.DataFrame(rows).write_parquet(out)
    else:
        out = data_dir / "universe.ndjson.gz"  # stdlib fallback, same rows
        with gzip.open(out, "wt", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    return out


def rank_buckets(rows: list[dict]) -> list[dict]:
    """day-tradeability = recurrence x liquidity x data availability."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["bucket"]].append(r)
    recurrer = {name for _, name in RECURRER_PATTERNS}
    ranked = []
    for bucket, ms in groups.items():
        ranked.append({
            "bucket": bucket,
            "n_markets": len(ms),
            "vol24_sum": sum(m["volume_24h"] for m in ms),
            "vol24_median": statistics.median(m["volume_24h"] for m in ms),
            "spread_median": statistics.median(m["spread"] for m in ms),
            "liq_median": statistics.median(m["liquidity"] for m in ms),
            "recurring": bucket in recurrer,
            "has_underlying": bucket.startswith("crypto"),
        })
    ranked.sort(key=lambda r: r["vol24_sum"], reverse=True)
    return ranked


def fee_snapshot(rows: list[dict]) -> list[dict]:
    """Distinct live feeType -> rate observed across the scan."""
    agg: dict[tuple, int] = defaultdict(int)
    for r in rows:
        agg[(r["fee_type"] or "(none)", r["fee_rate"])] += 1
    return [{"fee_type": ft, "rate": rate, "n_markets": n}
            for (ft, rate), n in sorted(agg.items(), key=lambda kv: -kv[1])]


def top_series(gamma: GammaClient, limit: int = 15) -> list[dict]:
    """Recurring series ranked by 24h volume — the recurrence axis, live."""
    out = []
    for s in gamma.get("/series", limit=limit, closed="false",
                       order="volume24hr", ascending="false"):
        out.append({"slug": s.get("slug"), "recurrence": s.get("recurrence"),
                    "vol24": float(s.get("volume24hr") or 0)})
    return out


def write_report(checks: dict, ranked: list[dict], rows: list[dict],
                 series: list[dict], universe_path: Path) -> None:
    out = ROOT / "docs" / "UNIVERSE_REPORT.md"
    n_expired = sum(1 for r in rows if r["expired"])
    lines = [
        "# POLYFUNNEL universe report",
        f"\nGenerated {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')} — LIVE DATA",
        f"\nAPI checks: `{json.dumps({k: bool(v) for k, v in checks.items()})}`",
        f"\nActive markets scanned: **{len(rows)}** "
        f"(of which {n_expired} are past their endDate but not closed — "
        "'zombies'; they stay in the table but rank low on vol24)",
        f"\nUniverse rows written to `{universe_path.relative_to(ROOT)}` (gitignored, local only).\n",
        "## Buckets by 24h volume",
        "",
        "| bucket | n | vol24 sum | vol24 med | spread med | liq med | recurring | underlying |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in ranked:
        lines.append(
            f"| {r['bucket']} | {r['n_markets']} | {r['vol24_sum']:,.0f} | "
            f"{r['vol24_median']:,.0f} | {r['spread_median']:.3f} | "
            f"{r['liq_median']:,.0f} | "
            f"{'Y' if r['recurring'] else 'N'} | {'Y' if r['has_underlying'] else 'N'} |"
        )
    lines += [
        "",
        "## Live fee schedule observed (Gamma `feeSchedule.rate` by `feeType`)",
        "",
        "| feeType | rate | n markets |",
        "|---|---|---|",
    ]
    for f in fee_snapshot(rows):
        rate = "—" if f["rate"] is None else f"{f['rate']:.3f}"
        lines.append(f"| {f['fee_type']} | {rate} | {f['n_markets']} |")
    lines += [
        "",
        "## Top recurring series by 24h volume (Gamma `/series`)",
        "",
        "| series | recurrence | vol24 |",
        "|---|---|---|",
    ]
    for s in series:
        lines.append(f"| {s['slug']} | {s['recurrence']} | {s['vol24']:,.0f} |")
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out}")


def stamp_costs_verified() -> None:
    # targeted line edit — yaml.safe_dump would strip the file's comments
    p = ROOT / "config" / "costs.yaml"
    raw = p.read_text()
    new = re.sub(r"(?m)^(\s*last_verified_live:)\s*\S+.*$",
                 rf"\g<1> {dt.date.today().isoformat()}", raw, count=1)
    if new == raw and "last_verified_live" not in raw:
        raise RuntimeError("costs.yaml: last_verified_live key not found")
    p.write_text(new)


def main() -> int:
    clob, gamma = ClobPublic(), GammaClient()
    try:
        checks = verify_apis(clob, gamma)
    except Exception as e:  # noqa: BLE001
        print(f"FATAL: API verification failed: {e}\n"
              "This environment likely blocks *.polymarket.com — run locally "
              "or widen the network policy. No deliverables written.", file=sys.stderr)
        return 2
    print("API checks passed:", json.dumps(checks, default=str)[:500])
    if pl is None:
        print("note: polars unavailable — stdlib aggregation, ndjson.gz output")

    rows = scan_universe(gamma)
    universe_path = write_universe(rows)
    print(f"wrote {universe_path} ({len(rows)} markets)")

    ranked = rank_buckets(rows)
    series = top_series(gamma)
    write_report(checks, ranked, rows, series, universe_path)
    if "fee_rate_sample" in checks:
        stamp_costs_verified()
        print("stamped costs.yaml meta.last_verified_live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
