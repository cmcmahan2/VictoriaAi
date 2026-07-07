# PROGRESS

## Session 2026-07-07 (later) — research integrated: the referee is Chainlink

- User deep-research PDF archived to vault/research/ (load-bearing claims live-verified where possible).
- CONFIRMED from live market rules: 5m markets settle on the **Chainlink BTC/USD data stream** (not Binance/spot), ties resolve **Up**.
- Polymarket relays the exact resolution feed on a free WebSocket (RTDS). Built `scripts/collect_rtds.py`: stdlib-only mini-RFC6455 client (codec loopback-tested in-session; host firewalled in sandbox), records chainlink + binance BTC ticks hour-partitioned. Runs on the user's machine next to collect_updown.py.
- Strategy implications adopted: (1) strike/settlement must be computed from the Chainlink feed, never Binance; (2) Binance-vs-Chainlink basis in final 30s is both the main failure mode of naive bots and a measurable edge candidate; (3) maker-first execution is the working default (community post-mortems + our T-60 study agree takers face a fee wall); (4) fee params change silently — read feeSchedule live per market.
- T-60 calibration study (earlier today, vault/studies/): market well-calibrated at n=200; no naive taker edge; faint longshot-overpricing hint.

## Session 2026-07-07 — Phase 1 started: up/down collector built + live-validated

User go-ahead: focus on the 5-minute BTC up/down series.

**Done**
- `scripts/collect_updown.py` — Phase 1 collector (books ~1 Hz w/ hash-dedupe + provable-gap heartbeats, series auto-discovery every 30s, settled-outcome capture). Stdlib-only so it runs in this restricted container AND on any local machine with no installs. `ClobPublic.books()` batch endpoint added.
- Live validation (25 min + 13 min runs): 8 markets, 7,466 book rows at median 1.00s cadence, full 1 Hz coverage of each market's final 60s, 4/4 in-window settlements captured with official winners. Full stats + runbook: `docs/DATA_REPORT.md`.
- New Gamma quirks discovered and documented in GROUND_TRUTH (§ API): settlement lags window end ~6–30 min; settled markets vanish from default listing (need `closed=true` by slug); `?id=` broken for recent market ids.
- Branch: `claude/new-session-v5f8js` = prior polyfunnel work + main (Trading Hub merge, which also brought in `polybot/` — a BTC-5m bot spec + backtest scaffold from another session).

**Known issue logged (not yet fixed)**
- `polybot/config.py` has `POLYMARKET_FEE = 0.0` ("no trading fee today") — contradicted by live-verified 0.07 crypto taker rate. Its backtests overstate PnL until aligned with `config/costs.yaml`.

**Next**
- Durable multi-day collection on the user's local machine (runbook in DATA_REPORT) — container data dies with the session.
- Then: calibration + microstructure analysis on real books; wire real data into polybot's backtest engine (replaces its synthetic orderbook caveat); maker-vs-taker execution study (fee wall: 0.07 × p(1−p) taker, maker free + rebates).
- Account/credentials: user exported wallet key to local `.env` (never in repo/chat). Execution stays unbuilt per Phase 7 gate.

## Session 2026-07-06 (retry) — Phase 0 recon COMPLETE

**Environment re-check (all three prior blockers cleared)**
- Network: `clob.polymarket.com/time` → HTTP 200. Polymarket hosts allowlisted.
- Push: trivial commit pushed to `claude/session-h1yrsc` without error.
- Signing: commits are unsigned locally (`git log --show-signature` → "No signature"); GitHub accepts them. No signing key configured in this environment — noted, not fixed.
- NEW constraint: PyPI/npm are NOT allowlisted (`x-deny-reason: host_not_allowed`) → no `.venv`, no third-party packages. Handled: stdlib HTTP shim (`src/polyfunnel/api/_compat.py`, with transient-error retry/backoff) behind httpx-optional imports in both API clients; recon aggregates in pure python and writes `data/universe.ndjson.gz` when polars is missing. pytest unavailable here → `tests/test_costs.py` not re-run this session (unchanged code path except comment edits; re-run locally).

**Live recon results (scan 2026-07-06T22:56Z)**
- **46,816 active markets** scanned (4,358 = 9.3% are "zombies": past endDate, not closed; flagged per-row). Full bucket table in `docs/UNIVERSE_REPORT.md`; universe rows local-only in `data/universe.ndjson.gz`.
- Top buckets by 24h vol: cat_sports $65.6M, sports_game $32.3M, cat_unknown/fee-free $8.5M, cat_politics $5.6M, econ_print $5.2M (World Cup + Wimbledon inflate sports this week).
- **Fees verified live; 0.07-vs-0.072 RESOLVED → 0.07** (`crypto_fees_v2`, seen on a live btc-updown-5m market; rebate 0.20). Sports 0.03/rebate 0.25, politics 0.04, economics/culture/weather/general 0.05, tech/mentions/finance_prices 0.04. `GET /fee-rate` returns `{"base_fee": bps}` — 1000 for all fee-enabled markets, 0 for fee-free; it is the order-protocol bound, NOT the category rate (which lives in Gamma `feeSchedule.rate`). costs.yaml stamped `last_verified_live: 2026-07-06`.
- **Surprises vs doc-derived assumptions** (details in GROUND_TRUTH, all [LIVE]-tagged):
  1. Crypto up/down recurrence is now **5-minute** (btc-up-or-down-5m ≈ $24M/24h series volume; slug format `btc-updown-5m-<unix_ts>`), not 15-min. ~288 BTC markets/day.
  2. Market-level scan understates recurrer volume ~160× (resolved 5m markets leave the active set); Gamma `/series` volume is authoritative for recurrence buckets.
  3. Gamma pagination changed: `limit` capped at 100, offset capped at 2000, keyset cursor not honored publicly → endDate-window pagination implemented in `GammaClient.iter_markets`.
  4. Gamma `category` is null on live data; `feeType` is the server-side taxonomy now.
  5. Fee-free segment (feesEnabled=false, 1,323 markets, $8.5M/24h, tight spreads) is liquid — structurally cheapest hunting ground for Families B/E.
  6. `prices-history` at fidelity=1 works fine on LIVE markets (~1 pt/min); the 12h+ constraint applies to resolved history — Phase 1 collectors remain top priority.
  7. One legacy zombie market carries feeType `crypto_15_min` rate 0.25 — never hardcode fee tables.

## Session 2026-07-06 — Phase 0 (partial: blocked on network)

**Done**
- Workspace scanned: no prior Polymarket edge-finder or py-clob-client setup exists anywhere in VictoriaAi → fresh scaffold under `polyfunnel/`.
- Project scaffold: pyproject, `.venv` (Python 3.11), deps installed (httpx, websockets, polars, pandas, numpy, pyarrow, duckdb, pyyaml, py-clob-client 0.34.6, ccxt, matplotlib, pytest).
- Security: `.env` gitignored + `.env.example`; dependency-free pre-commit secret scan (`scripts/hooks/pre-commit`, installer `scripts/install_hooks.sh`) — installed into repo hooks. Re-run installer after fresh clones.
- Recon: `docs/GROUND_TRUTH.md` — APIs, WS, rate limits, Fee V2 schedule + formula, granularity constraints; every claim labeled [SOURCE]/[DOC]/[UNVERIFIED]. Endpoints cross-verified from py-clob-client source.
- `config/costs.yaml` + `src/polyfunnel/costs.py` with staleness gate (trusted backtests blocked until fees live-verified). 6 unit tests pass.
- Thin API clients: `src/polyfunnel/api/gamma.py`, `clob.py` (public reads only).
- `scripts/phase0_recon.py`: live verification + taxonomy scan + `data/universe.parquet` + report writer. Verified it fails loudly (exit 2) in this container.

**Blocked**
- Container network policy 403s `*.polymarket.com` and exchange hosts → no live probes, no `data/universe.parquet`, no live bucket ranking. Resolution options in `docs/UNIVERSE_REPORT.md`.

**Key findings that shape strategy design**
1. Fee V2 (2026-03-30): taker `shares×rate×p(1−p)`; crypto highest at 0.07 — introduced explicitly to kill latency arb on short-term crypto markets (Family A's exact hypothesis). Maker side is free + rebated → maker execution is a first-class design axis.
2. CLOB `prices-history` unreliable below 12h fidelity for resolved markets → intraday backtests depend on live collection; collectors are the top Phase 1 priority.
3. Order placement enforces per-market dynamic `fee_rate_bps` (client rejects mismatches) → single runtime-fetched cost source for backtester + executor.

**Next (awaiting checkpoint go-ahead)**
- Get network access (env policy or local run) → run `phase0_recon.py` → real universe report → CHECKPOINT review → Phase 1 collectors immediately after.

## Phase status
- [x] Phase 0 recon — COMPLETE 2026-07-06: live universe scan (46,816 markets), fees verified, costs.yaml stamped. Awaiting CHECKPOINT review before Phase 1.
- [~] Phase 1 data engine — collector built + live-validated 2026-07-07; durable multi-day collection pending (runs on user's machine)
- [ ] Phase 2 strategy grid
- [ ] Phase 3 backtest engine
- [ ] Phase 4 filter gauntlet
- [ ] Phase 5 vault
- [ ] Phase 6 paper trading
- [ ] Phase 7 live module (disabled)
