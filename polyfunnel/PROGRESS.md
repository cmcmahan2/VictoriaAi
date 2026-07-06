# PROGRESS

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
- [~] Phase 0 recon — deliverables written; live verification pending network
- [ ] Phase 1 data engine
- [ ] Phase 2 strategy grid
- [ ] Phase 3 backtest engine
- [ ] Phase 4 filter gauntlet
- [ ] Phase 5 vault
- [ ] Phase 6 paper trading
- [ ] Phase 7 live module (disabled)
Retry session started 2026-07-06T22:34:38Z
