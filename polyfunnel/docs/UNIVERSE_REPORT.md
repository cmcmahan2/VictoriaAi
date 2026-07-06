# POLYFUNNEL universe report — Phase 0

**Status: BLOCKED — no live data.** This container's network policy 403-blocks
`*.polymarket.com` and exchange APIs, so the taxonomy scan could not run.
This page will be overwritten with live bucket rankings by
`scripts/phase0_recon.py` (which exits loudly with code 2 until then).

## What IS verified (see docs/GROUND_TRUTH.md for full detail + statuses)

- **APIs**: Gamma (catalog), CLOB (books/history/orders), WS market channel —
  endpoint paths verified from py-clob-client v0.34.6 source; params/limits
  doc-derived.
- **Fees (V2, 2026-03-30)**: `shares × rate × p(1−p)`, taker-only, maker $0.
  Crypto 0.07 (highest — deliberately anti-latency-arb), sports 0.03,
  finance/politics 0.04, econ/culture 0.05, geopolitics free. Per-market
  dynamic via `GET /fee-rate`; encoded in `config/costs.yaml` with a
  staleness gate that blocks "trusted" backtests until live-verified.
- **Historical granularity trap**: CLOB `prices-history` often returns *empty*
  below 12-hour fidelity for resolved markets → intraday families cannot be
  backtested from API history alone; live book collection (Phase 1) is the
  only reliable source of intraday data. Today's collection is next month's
  backtest.

## Provisional bucket ranking (doc-derived; DO NOT build on without live scan)

| rank | bucket | recurrence | underlying | expected liquidity | fee tier | note |
|---|---|---|---|---|---|---|
| 1 | crypto BTC/ETH up-down (15m/1h/1d) | perfect | ccxt 1-min spot | continuous | 0.07 (worst) | fee wall targets exactly Family A |
| 2 | sports games | high | in-play feeds ($) | high, event-driven | 0.03 | Family F stays flag-gated |
| 3 | econ prints (CPI/FOMC/NFP) | monthly | macro calendars | bursty | 0.05 | low n; vault material |
| 4 | politics/culture one-offs | none | — | varies | 0.04/0.05 | not backtestable as a class |

## Decision needed at this checkpoint

Live data requires one of:
1. **Widen this environment's network policy** (Claude Code on the web →
   environment settings) to allow `*.polymarket.com` + one exchange API host,
   then re-run `PYTHONPATH=src .venv/bin/python scripts/phase0_recon.py`; or
2. **Run locally**: clone branch, `uv venv && uv pip install -e .`, run the
   same command.

Until one happens, Phases 1–3 (harvest, collectors, backtests) cannot start.
