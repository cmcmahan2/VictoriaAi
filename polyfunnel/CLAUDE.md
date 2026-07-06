# POLYFUNNEL — project conventions

Polymarket day-trading research pipeline: mass backtest → brutal filter → knowledge vault → tiny surviving set. Read `PROGRESS.md` first in every session; read `docs/GROUND_TRUTH.md` before touching anything that talks to an API.

## Operating principles (non-negotiable)
1. Null results are valid results — document autopsies, never tune until something "works".
2. Every variant tested is logged to `results/all_variants.parquet` (failures included); the full count N feeds deflated-Sharpe corrections in Phase 4. Never report stats without holdout beside them.
3. Costs kill thin edges. The backtester imports its cost model from `config/costs.yaml`; fee rates are per-market and dynamic — verify via CLOB `GET /fee-rate` at runtime, never hardcode.
4. Prices are bounded [0,1] with terminal resolution. Every signal family states its economic hypothesis before code.
5. Paper before live. Live module ships disabled; nothing trades until Phase 6 gates pass AND the user types `GO LIVE`.
6. Credentials in `.env` only (gitignored). Pre-commit secret scan installed via `scripts/install_hooks.sh` — run it after any fresh clone.
7. Ask before: unusual deps, live orders, deleting collected data, aggressive API usage.

## Layout
- `src/polyfunnel/` — library code (api clients, costs, engine)
- `scripts/` — runnable entry points (recon, collectors, backtests, digest)
- `config/` — costs.yaml, universe.yaml, risk.yaml (Phase 7)
- `docs/` — GROUND_TRUTH.md, DATA_REPORT.md, AUTOPSY.md, reports
- `data/` — parquet lake (gitignored; irreplaceable live-collected books get backed up before any cleanup)
- `results/` — variant logs and survivors (gitignored)
- `vault/` — Obsidian knowledge base (committed; it's the durable asset)

## Conventions
- Python 3.11, venv at `.venv`, deps via `uv pip install`. Keep deps lean.
- All timestamps UTC internally; Polymarket resolutions are ET-anchored — convert explicitly with `zoneinfo`, never naive datetimes.
- Prices as floats in [0,1]; sizes in shares; money in USDC.
- Deterministic variant IDs: `sha1(family + json(params, sort_keys=True))[:12]`.
- Tests in `tests/`, run with `.venv/bin/pytest`.
- Run from `polyfunnel/` directory: `PYTHONPATH=src .venv/bin/python scripts/<script>.py`.

## Environment caveat (Claude Code on the web)
As of 2026-07-06 the network policy allowlists `*.polymarket.com` (live probes work) but **blocks PyPI/npm** — third-party packages cannot be installed, so no `.venv` here. The API clients fall back to a stdlib HTTP shim (`src/polyfunnel/api/_compat.py`) when httpx is missing, and `phase0_recon.py` aggregates without polars (universe file becomes `data/universe.ndjson.gz`). Anything needing compiled deps (polars/pyarrow/ccxt backtests, pytest runs) must run locally or after PyPI is added to the environment's network egress allowlist. See `docs/GROUND_TRUTH.md` § Environment status.
