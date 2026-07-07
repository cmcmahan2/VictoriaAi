# DATA_REPORT — Phase 1 collection

## Collector: `scripts/collect_updown.py`

Records the raw material intraday backtests need and Polymarket does not
serve retroactively: live order books and settled outcomes for up/down
recurrer series. Stdlib-only (runs in the restricted web container and on
any machine with Python 3.11+; no pip installs required). See module
docstring for file formats and honesty guarantees.

## Validation run — 2026-07-07, series `btc-up-or-down-5m`

Two in-session runs (13 min aborted + 25 min complete), one UTC-day file set:

| metric | value |
|---|---|
| markets tracked | 8 (5-minute windows, back to back) |
| book snapshot rows | 7,466 (16 heartbeat rows; the rest are real book changes) |
| snapshot cadence | median gap 1.00s, p95 2.01s, max 16.0s per token |
| coverage of final 60s before close | 120 rows/market = full 1 Hz × 2 tokens |
| two-sided book rows | 7,224 — median top spread 0.010 (= one tick), p90 0.010 |
| median top-3-level bid depth | ~1,094 shares |
| settled outcomes captured | 4/4 markets whose settlement window fell inside the run (all official `["1","0"]` prices + winner) |
| provisional outcomes | 1 (market ended near run end; last prices 0.995/0.005 recorded, labeled `settled: false`) |
| raw size | ~26 MB / ~35 min of collection → ~1 GB/day/series uncompressed; hour files gzip ~10× on rotation |

Live behaviors the collector had to handle (details in GROUND_TRUTH § API):
settlement lags window end by ~6–30 min; settled markets vanish from the
default Gamma listing (query `closed=true` by slug); `?id=` lookup is broken
for recent market ids.

## Interpretation limits (read before building on this)

- One ~35-minute window on one series during a single BTC regime — enough to
  validate the pipeline, worthless for strategy inference. All 4 settled
  outcomes were "Up"; that is noise, not signal.
- No underlying spot feed from the web container (exchange hosts blocked).
  Underlying candles/ticks are retroactively downloadable from exchanges, so
  the join can happen later; sub-second lead/lag studies will want a local
  spot poll running alongside.
- The container is ephemeral: data collected here dies with the session.
  Durable collection must run on a persistent machine.

## Runbook — durable collection on a local machine (Windows or otherwise)

```
cd VictoriaAi/polyfunnel
# BTC 5m only:
python scripts/collect_updown.py
# BTC + ETH 5m and BTC 15m, until stopped:
python scripts/collect_updown.py --series btc-up-or-down-5m --series eth-up-or-down-5m --series btc-up-or-down-15m
```

No dependencies to install. Stop with Ctrl-C (flushes and writes provisional
outcome rows). Restarts are safe: files append, dedupe/heartbeats make gaps
visible, discovery re-finds live markets. Target: **≥2 weeks unattended**
before Phase 3 backtests make claims.

## Next

1. Multi-day local collection (user's machine) — the actual Phase 1 dataset.
2. Local spot-price sidecar (Binance/Coinbase poll) for lead/lag features.
3. Parquet conversion + calibration/microstructure summaries once enough
   days exist (needs polars, so local).
4. Feed real books + real outcomes into polybot's backtest engine, replacing
   its synthetic orderbook mode (its README's #1 caveat) — and fix its
   `POLYMARKET_FEE = 0.0` default to the verified fee model
   (0.07 × p(1−p), taker-only) first.
