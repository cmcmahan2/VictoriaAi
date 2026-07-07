# polybot — Polymarket BTC 5-minute directional-momentum bot

A paper/live trading bot for Polymarket's BTC 5-minute up/down markets, plus a
look-ahead-free **backtest engine** (in `backtest/`, built over Phases 1–6).

> **Status / honesty note.** This bot was built from a specification, not evolved
> from a profitable live track record. The parameters in `config.py` are
> reasonable defaults, **not proven edges**. Validate with walk-forward
> backtesting before risking money. And read the backtest caveats below — the
> single most important signal (`orderbook_imbal`) **cannot be backtested on real
> data** and is synthetic in every backtest.

## Strategy in one sentence

At `DECISION_LEAD_SECONDS` before each 5-minute window closes, compute a composite
directional signal in `[-1, +1]`; if `|signal| ≥ SIGNAL_THRESHOLD`, buy the favored
side (**FAV**) plus a smaller opposite-side **HEDGE**, sized by fractional Kelly.

## The 7-indicator composite (`strategy.py`)

Each sub-signal is squashed to `[-1, +1]`; the composite is their weighted sum
(weights in `config.py`, must sum to 1.0):

| Indicator | Weight | What it measures |
|---|---|---|
| `orderbook_imbal` | 0.25 | CLOB top-of-book bid/ask imbalance — the intended primary edge |
| `ema_cross` | 0.18 | fast EMA vs slow EMA (trend direction) |
| `macd` | 0.15 | MACD histogram (trend momentum) |
| `rsi` | 0.12 | RSI distance from 50 |
| `momentum` | 0.12 | short-lookback rate of change |
| `volume_delta` | 0.10 | taker buy/sell imbalance |
| `trend_strength` | 0.08 | signed Kaufman efficiency ratio |

If a sub-signal is unavailable (e.g. no orderbook), its weight is dropped and the
rest renormalized so the composite stays calibrated to `[-1, 1]`.

## Risk model (`risk_engine.py`)

- **Fractional Kelly**: for a token bought at price `q`, net odds `b = (1−q)/q` and
  full-Kelly `f* = p − (1−p)/b`. We deploy `KELLY_FRACTION · f*`, capped at
  `MAX_POSITION_FRAC`, then scaled down by drawdown. **Kelly only bets when
  `p > q`** (estimated win prob beats the price) — no edge, no trade.
- **Win-prob estimate `p`**: blends signal confidence with a Bayesian `Beta(α, β)`
  posterior over the realized FAV win rate (`SIGNAL_TRUST` mixes the two).
- **Hedge**: opposite-side stake = `HEDGE_FRACTION · FAV stake`.
- **Drawdown control**: de-risk past `DERISK_DRAWDOWN`, hard halt at `MAX_DRAWDOWN`.

## Module map

```
config.py             all tunable params (WEIGHTS, thresholds, Kelly, hours, costs)
price_feed.py         Candle / OrderBook dataclasses + indicator math (EMA/RSI/MACD/…)
strategy.py           Strategy.evaluate() -> Signal   (the 7-indicator composite)
risk_engine.py        RiskEngine.size() -> SizeDecision  (Kelly + Bayesian + drawdown)
polymarket_client.py  Market/Fill, calculate_pnl(), discovery + (guarded) execution
logger.py             SQLite trade schema shared by live + backtest
analyze.py            performance analyzer + reusable stat helpers (Wilson CI, Sharpe…)
smoke_test.py         end-to-end wiring proof on synthetic data (no network)
backtest/
  data.py             P1 klines + ground-truth 5m outcomes (real download + synthetic)
  pricing.py          P2 P_up token-price model, mispricing/spread/slippage, synth book
  engine.py           P3 no-look-ahead replay through the REAL Strategy/RiskEngine
  report.py           P4 terminal + HTML report (Wilson CI, significance, break-even)
  walkforward.py      P5 rolling train/test, out-of-sample-only reporting
  optimize.py         P6 parameter sweep, walk-forward evaluated, overfit flags
tests/test_no_lookahead.py   proves the future can't influence a past decision
```

## Backtest usage

```bash
cd polybot
# Phase 1 — data + outcomes (real download; --synthetic for the sandbox)
python -m backtest.data --days 180
python -m backtest.data --days 14 --synthetic

# Phase 3 — full backtest -> backtest_trades.db + reports/backtest.html
python -m backtest.engine --days 180
python -m backtest.engine --days 90 --synthetic --mispricing 0.03 --orderbook momentum

# analyze.py runs unchanged on the backtest DB
python analyze.py --db backtest_trades.db

# Phase 5 — walk-forward (reports OUT-OF-SAMPLE only)
python -m backtest.walkforward --days 120 --synthetic

# Phase 6 — parameter sweep, walk-forward evaluated
python -m backtest.optimize --days 120 --synthetic
python -m backtest.optimize --days 180 --random 20

# the no-look-ahead test
python tests/test_no_lookahead.py
```

Key knobs (all on `BacktestConfig`, all sweepable): `mispricing` (the edge knob,
default 0 = efficient market), `spread`, `slippage`, `gas`, `orderbook_mode`
(`noise` default / `momentum` / `edge`), `orderbook_edge`, `seed`.

## Running

```bash
cd polybot
pip install -r requirements.txt          # only `requests`; everything else is stdlib

python smoke_test.py                      # prove the wiring works (synthetic data)
python analyze.py --db <path-to.db>       # analyze any trade DB (live or backtest)
```

The smoke test prints deliberately absurd numbers — that is the point: it uses a
**circular synthetic orderbook** and a **baked-in mispricing edge**, so it
"predicts" outcomes it is partly derived from. It validates plumbing only.

## Backtest caveats (read before trusting any backtest)

1. **The orderbook signal is synthetic in backtests.** Historical Polymarket CLOB
   order books are not retrievable. Since `orderbook_imbal` is 25% of the signal,
   any backtested edge is partly manufactured. Every report says so in bold.
2. **Token prices are modeled, not observed.** We lack historical Polymarket token
   prices, so `backtest/pricing.py` models them with an explicit `mispricing` knob.
3. **No mid-price fantasy fills.** Spread, slippage, gas, and fees hit every trade.
4. **Out-of-sample only.** Any reported edge comes from walk-forward, never a single
   in-sample fit.

## Environment notes (this repo's web sandbox)

- Pure stdlib + `requests` by design — no numpy/pandas/scipy/matplotlib needed.
- In the Claude-on-the-web sandbox, **all exchange and Polymarket hosts are blocked**
  by the network allowlist, so the real data downloader (`backtest/data.py`) can't
  fetch here — run it locally. A seeded synthetic-candle fallback keeps the pipeline
  demonstrable in-sandbox, clearly labeled as synthetic.
