"""
hunt.py — multi-factor US stock hunter (free data via yfinance).

Two-phase scan so it stays fast over thousands of names:
  PHASE 1 (whole universe, cheap): batch-download price history, compute the
          price factors — momentum (3/6/12-mo), trend (vs 50/200-day SMA),
          relative strength (position in 52-week range) — and gate on liquidity.
  PHASE 2 (finalists only, pricey): pull fundamentals (P/E, margin, ROE, growth)
          for the top price-ranked names, add quality + value, blend, re-rank.

Usage:
  python hunt.py                 # full US universe (~5000), ~slow
  python hunt.py --max 400       # cap universe size for a quick run
  python hunt.py --top 25        # how many finalists to show / enrich
  python hunt.py --json out.json # also write results for the dashboard
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

import pandas as pd
import yfinance as yf

NASDAQ_FILES = [
    "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
]


def get_universe(max_n: int | None = None) -> list[str]:
    """All common-stock tickers from the free Nasdaq Trader symbol files."""
    syms: list[str] = []
    for url in NASDAQ_FILES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            text = urllib.request.urlopen(req, timeout=25).read().decode("latin-1")
        except Exception as exc:
            print(f"  (universe fetch failed for {url}: {exc})")
            continue
        lines = text.splitlines()
        header = lines[0].split("|")
        sym_i = 0
        etf_i = header.index("ETF") if "ETF" in header else None
        test_i = header.index("Test Issue") if "Test Issue" in header else None
        for line in lines[1:]:
            if line.startswith("File Creation Time"):
                continue
            f = line.split("|")
            if len(f) <= sym_i:
                continue
            sym = f[sym_i].strip()
            if not sym or "." in sym or "$" in sym:        # skip preferreds/warrants/units
                continue
            if etf_i is not None and len(f) > etf_i and f[etf_i] == "Y":
                continue                                    # skip ETFs
            if test_i is not None and len(f) > test_i and f[test_i] == "Y":
                continue                                    # skip test issues
            syms.append(sym)
    syms = sorted(set(syms))

    # Cache the universe locally: write on success, fall back to it on a network
    # hiccup so the autonomous loop never dies on a transient DNS/connection error.
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe_cache.txt")
    if syms:
        try:
            with open(cache, "w", encoding="utf-8") as f:
                f.write("\n".join(syms))
        except OSError:
            pass
    elif os.path.exists(cache):
        print("  (universe fetch failed — using cached universe)")
        with open(cache, encoding="utf-8") as f:
            syms = [s.strip() for s in f if s.strip()]

    return syms[:max_n] if max_n else syms


def _pct_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100.0


def phase1_prices(symbols: list[str], chunk: int = 150) -> pd.DataFrame:
    """Download ~1y daily closes for the universe; compute price factors."""
    rows = []
    n = len(symbols)
    for i in range(0, n, chunk):
        batch = symbols[i:i + chunk]
        print(f"  prices {i+1}-{min(i+chunk, n)} / {n}…", flush=True)
        try:
            data = yf.download(batch, period="1y", interval="1d", group_by="ticker",
                               auto_adjust=True, threads=True, progress=False)
        except Exception as exc:
            print(f"    batch failed: {exc}")
            continue
        for sym in batch:
            try:
                close = data[sym]["Close"].dropna() if len(batch) > 1 else data["Close"].dropna()
                vol = data[sym]["Volume"].dropna() if len(batch) > 1 else data["Volume"].dropna()
            except (KeyError, TypeError):
                continue
            if len(close) < 200:
                continue
            px = float(close.iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1])
            sma200 = float(close.rolling(200).mean().iloc[-1])
            hi52, lo52 = float(close.max()), float(close.min())
            dollar_vol = float((close * vol).tail(30).mean())
            if px < 5 or dollar_vol < 5e6:                  # liquidity gate
                continue

            def ret(days):
                return px / float(close.iloc[-days]) - 1.0 if len(close) > days else None

            rows.append({
                "symbol": sym, "price": px,
                "mom_3m": ret(63), "mom_6m": ret(126), "mom_12m": ret(252),
                "above_200": px > sma200, "above_50": px > sma50,
                "trend_pct": px / sma200 - 1.0,
                "rs_52w": (px - lo52) / (hi52 - lo52) if hi52 > lo52 else 0.0,
                "dollar_vol": dollar_vol,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # composite momentum (blend of horizons), then percentile-rank cross-sectionally
    df["mom"] = df[["mom_3m", "mom_6m", "mom_12m"]].mean(axis=1)
    df["mom_score"] = _pct_rank(df["mom"])
    df["rs_score"] = df["rs_52w"] * 100.0
    df["trend_score"] = (df["above_200"].astype(int) * 60 + df["above_50"].astype(int) * 40)
    df["price_score"] = 0.55 * df["mom_score"] + 0.25 * df["rs_score"] + 0.20 * df["trend_score"]
    return df.sort_values("price_score", ascending=False).reset_index(drop=True)


def phase2_fundamentals(df: pd.DataFrame, top: int) -> pd.DataFrame:
    """Enrich the top price-ranked finalists with quality + value factors."""
    finalists = df.head(top * 3).copy()                     # enrich a wider pool, then cut
    qual, val, pes = [], [], []
    for sym in finalists["symbol"]:
        roe = margin = growth = pe = None
        try:
            info = yf.Ticker(sym).info
            roe, margin = info.get("returnOnEquity"), info.get("profitMargins")
            growth, pe = info.get("revenueGrowth"), info.get("trailingPE")
        except Exception:
            pass
        # quality 0-100: reward ROE, margin, growth (clipped)
        q = 0.0
        if roe is not None:    q += max(min(roe, 0.5), -0.2) / 0.5 * 40
        if margin is not None: q += max(min(margin, 0.4), -0.2) / 0.4 * 30
        if growth is not None: q += max(min(growth, 0.5), -0.2) / 0.5 * 30
        # value 0-100: reward a sane P/E, penalize none/negative/extreme
        if pe is None or pe <= 0:
            v = 30.0
        elif pe < 15:  v = 100.0
        elif pe < 25:  v = 80.0
        elif pe < 40:  v = 55.0
        elif pe < 60:  v = 30.0
        else:          v = 10.0
        qual.append(max(0.0, q)); val.append(v); pes.append(pe)
        time.sleep(0.05)
    finalists["quality"] = qual
    finalists["value"] = val
    finalists["pe"] = pes
    finalists["score"] = (0.50 * finalists["price_score"]
                          + 0.30 * finalists["quality"]
                          + 0.20 * finalists["value"])
    return finalists.sort_values("score", ascending=False).reset_index(drop=True).head(top)


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-factor US stock hunter")
    ap.add_argument("--max", type=int, default=None, help="cap universe size (for quick runs)")
    ap.add_argument("--top", type=int, default=20, help="finalists to show")
    ap.add_argument("--json", help="write results to this JSON path")
    args = ap.parse_args()

    t0 = time.time()
    print("Building universe…", flush=True)
    universe = get_universe(args.max)
    print(f"  {len(universe)} tickers", flush=True)

    print("Phase 1 — price/momentum screen…", flush=True)
    df = phase1_prices(universe)
    if df.empty:
        print("No candidates passed the liquidity screen."); return
    print(f"  {len(df)} liquid candidates scored", flush=True)

    print(f"Phase 2 — fundamentals on top finalists…", flush=True)
    res = phase2_fundamentals(df, args.top)

    print(f"\nDone in {(time.time()-t0)/60:.1f} min.\n")
    print("=" * 92)
    print(f"  {'#':>2}  {'TICKER':<7}{'SCORE':>6}{'PRICE':>9}{'MOM':>7}{'52W':>6}"
          f"{'TREND':>7}{'QUAL':>6}{'VAL':>6}  {'P/E':>6}")
    print("-" * 92)
    for i, r in res.iterrows():
        trend = "↑200" if r["above_200"] else "<200"
        pe = f"{r['pe']:.0f}" if r.get("pe") else "—"
        print(f"  {i+1:>2}  {r['symbol']:<7}{r['score']:>6.0f}{r['price']:>9.2f}"
              f"{r['mom']*100:>6.0f}%{r['rs_52w']*100:>5.0f}%{trend:>7}"
              f"{r['quality']:>6.0f}{r['value']:>6.0f}  {pe:>6}")
    print("=" * 92)

    if args.json:
        cols = ["symbol", "price", "score", "mom", "rs_52w", "above_200", "quality", "value", "pe"]
        out = res[cols].to_dict(orient="records")
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"generated": int(time.time()), "picks": out}, f, indent=2, default=str)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
