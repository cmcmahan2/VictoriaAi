# Polybot — Polymarket Arbitrage Finder

A focused tool that scans **Polymarket's own order books** for internal
arbitrage (the thing OddsJam doesn't do — it only line-shops Polymarket
against sportsbooks), ranks opportunities by **net ROI after fees**, and
tracks every bet's P&L. Built in deliberate phases so live money is the last
step, not the first.

## Why Polymarket-internal arb?

Across any group of mutually-exclusive outcomes, exactly one resolves to $1.
So buying one share of every outcome (a "complete set") should cost ~$1.00.
When thin order books push that sum **below $1**, the gap is risk-free profit:

- **Binary** — `ask(YES) + ask(NO) < $1`
- **Multi-outcome / negRisk** — `Σ ask(all outcomes) < $1`
- **Logical / correlated** — related markets that violate each other's bounds
  (e.g. "Trump wins" can't exceed "a Republican wins"). Scaffolded for a rules
  config; the math reuses the complete-set engine.

## Phases

| Phase | What it does | Risk | Keys |
|-------|--------------|------|------|
| **1 — this build** | Find arbs + paper-track bets + UI | None (read-only) | None |
| 2 — next | Execution engine in **paper mode** (logs orders it *would* place) | None | None |
| 3 — later | **Live** auto-execution, fill-or-kill leg logic, position caps, kill switch | Real money | Burner wallet key |

Auto-execution (Phase 3) is what removes **leg risk** — filling one side of an
arb and getting stuck before the other side fills. That's the single biggest
practical reason to automate.

## Run it

```bash
cd polybot
npm install
npm run dev          # http://localhost:3002
```

Out of the box it runs on **demo data** (no network, no keys) so the UI and
math work immediately.

### Live data (still keyless)

```bash
cp .env.example .env
# set POLYMARKET_LIVE=true
```

This pulls real markets from Polymarket's **public** Gamma + CLOB APIs. No
account or API key is required for read-only price data.

### Fees

Set `POLYMARKET_FEE` (fraction of net winnings, e.g. `0.02` for 2%). Every
ranked edge is **net of this fee**, so a 3% gross arb that nets negative after
fees is filtered out.

## Layout

```
lib/arbitrage.ts   complete-set math: detect arbs, size stakes, after-fee ROI
lib/polymarket.ts  live Gamma+CLOB fetch with demo fallback
lib/types.ts       shared types
app/api/arbs/      GET scan endpoint (force-dynamic; never cached)
app/page.tsx       OddsJam-style finder + bet tracker (localStorage)
components/        ArbCard, ArbDetail
```

## Not yet built (on purpose)

- Live order placement (Phase 3) — requires a funded burner wallet.
- Persistent DB for the tracker (currently localStorage).
- Logical/correlated relationship rules (engine is ready; rules config is empty).
