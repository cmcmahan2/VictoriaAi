# stock-desk — wheel options + congressional copy-trading (backtest-first)

A second, separate tool (sibling to `regime-terminal/`) for **stocks and options**,
built with the same look-ahead-free, honest-backtest discipline. Pure Python, no
required dependencies.

> **Reality check on the YouTube pitch.** The "follow politicians for insider
> gains" story oversells it: disclosures are **30–45+ days late**, amounts are
> ranges, and the headline backtests are hindsight-picked single names. The wheel
> is a real income strategy but **caps your upside** and has **tail risk** (you get
> assigned right when a stock craters). So: backtest first, **paper-trade only**,
> and never auto-execute real money without guardrails.

## What's here

| File | What it does |
|---|---|
| `options.py` | Black-Scholes pricing (call/put premium, delta) + realized-vol estimate. Validated (put-call parity holds). |
| `data.py` | Daily bars — synthetic generator + Alpaca loader (`/v2/stocks/.../bars`). |
| `wheel.py` | **Wheel backtest**: sell cash-secured puts → assignment → covered calls → called away, collecting premium. No look-ahead; premiums **modeled** with Black-Scholes (real IV/spread differ). |
| `congress.py` | **Congressional copy-trading**: fetch House/Senate disclosures (the free stock-watcher datasets), rank active traders, build lagged copy signals, and backtest the copy. |
| `config.py` | All knobs (strike %, expiry, profit-take, disclosure lag, copy size…). |

## Run

```bash
cd stock-desk
python wheel.py --source synthetic --days 504          # backtest the wheel (sandbox)
python wheel.py --source alpaca --ticker AAPL --days 730   # real data (Alpaca keys, run locally)
python congress.py                                      # copy-trading pipeline (sample data in sandbox)
```

Real data needs `pip install requests` (already a dep) and environment keys:
```
ALPACA_API_KEY=...      ALPACA_SECRET_KEY=...
```
The sandbox blocks Alpaca + the disclosure datasets, so they fall back to synthetic/
sample here — the **logic is verified**, the **numbers are plumbing, not edge**.

## What honest backtests already show
- The **wheel underperforms buy-and-hold in a strong uptrend** (it caps gains) but
  with far lower drawdown — it's a flat/choppy-market income strategy, not a moonshot.
- Copy-trading is a **delayed signal source** to research, not a guaranteed edge.

## Live / paper execution (next step)
Equity copy-trades can execute through the same Alpaca adapter the crypto tool uses
(`regime-terminal/execution.py` — paper-first, guarded, `--arm` required). Live
**options** orders (the wheel placing real puts/calls) are the next build on top of
that. Everything stays **paper-default** until you explicitly arm it.
