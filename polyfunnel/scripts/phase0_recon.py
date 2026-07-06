#!/usr/bin/env python3
"""Phase 0 recon: live API verification + market taxonomy scan.

Run:  PYTHONPATH=src .venv/bin/python scripts/phase0_recon.py

Produces:
  data/universe.parquet        one row per active market, bucketed + tagged
  docs/UNIVERSE_REPORT.md      one-page report (bucket ranking table)
  config/costs.yaml            stamps meta.last_verified_live on fee verification

Requires outbound HTTPS to *.polymarket.com. In the Claude-Code-web container
the network policy blocks this — run locally, or widen the environment's
network policy, and re-run. The script fails loudly (never silently) when
endpoints are unreachable.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import polars as pl  # noqa: E402
import yaml  # noqa: E402

from polyfunnel.api.clob import ClobPublic  # noqa: E402
from polyfunnel.api.gamma import GammaClient  # noqa: E402

RECURRER_PATTERNS = [
    # slug patterns that identify structurally-repeating market series
    (re.compile(r"(bitcoin|btc).*(up-or-down|hourly|-et$|15-min|15m)", re.I), "crypto_btc_updown"),
    (re.compile(r"(ethereum|eth).*(up-or-down|hourly|-et$|15-min|15m)", re.I), "crypto_eth_updown"),
    (re.compile(r"(solana|sol|xrp|doge).*(up-or-down|hourly)", re.I), "crypto_alt_updown"),
    (re.compile(r"(nba|nfl|mlb|nhl|epl|ucl|-vs-)", re.I), "sports_game"),
    (re.compile(r"(fed|cpi|nonfarm|jobs-report|gdp|fomc|rate-decision)", re.I), "econ_print"),
]


def bucket_market(m: dict) -> str:
    slug = (m.get("slug") or "").lower()
    for pat, name in RECURRER_PATTERNS:
        if pat.search(slug):
            return name
    cat = (m.get("category") or "").lower()
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


def scan_universe(gamma: GammaClient) -> pl.DataFrame:
    rows = []
    for m in gamma.iter_markets(active=True, closed=False):
        end = m.get("endDate")
        rows.append({
            "id": m.get("id"),
            "slug": m.get("slug"),
            "question": m.get("question"),
            "category": m.get("category"),
            "bucket": bucket_market(m),
            "volume_24h": float(m.get("volume24hr") or 0),
            "volume_total": float(m.get("volume") or 0),
            "liquidity": float(m.get("liquidity") or 0),
            "spread": float(m.get("spread") or 0),
            "best_bid": m.get("bestBid"),
            "best_ask": m.get("bestAsk"),
            "end_date": end,
            "clob_token_ids": m.get("clobTokenIds"),
            "neg_risk": m.get("negRisk"),
        })
    return pl.DataFrame(rows)


def rank_buckets(df: pl.DataFrame) -> pl.DataFrame:
    """day-tradeability = recurrence x liquidity x data availability."""
    agg = (
        df.group_by("bucket")
        .agg(
            pl.len().alias("n_markets"),
            pl.col("volume_24h").sum().alias("vol24_sum"),
            pl.col("volume_24h").median().alias("vol24_median"),
            pl.col("spread").median().alias("spread_median"),
            pl.col("liquidity").median().alias("liq_median"),
        )
        .sort("vol24_sum", descending=True)
    )
    recurrer = {b for _, b in [(p, n) for p, n in RECURRER_PATTERNS]}
    agg = agg.with_columns(
        pl.col("bucket").is_in(list(recurrer)).alias("recurring"),
        pl.col("bucket").str.starts_with("crypto").alias("has_underlying"),
    )
    return agg


def write_report(checks: dict, ranked: pl.DataFrame, n_markets: int) -> None:
    out = ROOT / "docs" / "UNIVERSE_REPORT.md"
    lines = [
        "# POLYFUNNEL universe report",
        f"\nGenerated {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')} — LIVE DATA",
        f"\nAPI checks: `{json.dumps({k: bool(v) for k, v in checks.items()})}`",
        f"\nActive markets scanned: **{n_markets}**\n",
        "| bucket | n | vol24 sum | vol24 med | spread med | recurring | underlying |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in ranked.iter_rows(named=True):
        lines.append(
            f"| {r['bucket']} | {r['n_markets']} | {r['vol24_sum']:,.0f} | "
            f"{r['vol24_median']:,.0f} | {r['spread_median']:.3f} | "
            f"{'Y' if r['recurring'] else 'N'} | {'Y' if r['has_underlying'] else 'N'} |"
        )
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out}")


def stamp_costs_verified() -> None:
    p = ROOT / "config" / "costs.yaml"
    raw = yaml.safe_load(p.read_text())
    raw["meta"]["last_verified_live"] = dt.date.today().isoformat()
    p.write_text(yaml.safe_dump(raw, sort_keys=False))


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

    df = scan_universe(gamma)
    (ROOT / "data").mkdir(exist_ok=True)
    df.write_parquet(ROOT / "data" / "universe.parquet")
    print(f"wrote data/universe.parquet ({df.height} markets)")

    ranked = rank_buckets(df)
    write_report(checks, ranked, df.height)
    if "fee_rate_sample" in checks:
        stamp_costs_verified()
        print("stamped costs.yaml meta.last_verified_live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
