# Regime Terminal — HMM market-regime detection + regime-gated strategy

A Hidden Markov Model classifies the market into regimes (bull / bear / crash /
chop / …); a leveraged strategy is layered **on top**, acting only when the regime
and your confirmations agree. Inspired by the "regime terminal" HMM approach
(popularized via Renaissance/Jim Simons lore), but built **honestly**.

> **Read this first.** This is a real, respected technique — but the popular video
> version has a fatal flaw, and leverage magnifies mistakes. Two non-negotiables
> baked in here:
>
> 1. **No look-ahead.** A Gaussian HMM trained on the *whole* history and read via
>    its *smoothed* (forward-backward) or Viterbi path uses **future** data to
>    label the past. Backtesting trades on those labels is look-ahead bias — it
>    looks spectacular and fails live. We decide on the **filtered** (causal)
>    posterior — only data up to each bar — and retrain **walk-forward**. The
>    smoothed overlay exists for charts only, clearly marked *not tradeable*.
> 2. **Honest validation.** The HMM is validated against synthetic data with
>    *planted* regimes (`verify_hmm.py`): it recovers them at **~99%**. We also
>    found the video's `volume_change` feature **halves** recovery (98%→53%) — a
>    first-difference is noise within a regime — so the default features are
>    **returns + range**. Volume stays selectable for your own experiments.
>
> Done honestly, results will **not** look like the video's "3×'d the market."
> That number depends on the look-ahead. A truthful backtest is the point.

## How it works (two layers)

```
REGIME layer (stable)            STRATEGY layer (you adapt over time)
─────────────────────            ───────────────────────────────────
Gaussian HMM, N states           enter only if regime is bullish AND
features: returns, range   ─────▶ k-of-n confirmations pass (RSI/MACD/
causal filtered posterior        ADX/momentum/…); exit on regime flip;
+ confidence                     min-hold (hysteresis) + cooldown; leverage
```

The edge thesis: **don't fight the regime.** Strategies churn; the regime read is
the durable filter. As markets change you re-tune the strategy layer; the HMM
re-trains itself.

## Status

- [x] **HMM core** (`hmm.py`) — pure-Python Gaussian HMM: Baum-Welch EM with random
  restarts, causal `filter_states`, `smooth_states`, `viterbi`, log-space. No deps.
- [x] **Data** (`data.py`) — yfinance hourly loader (+ CSV cache) and seeded
  synthetic OHLCV with planted regimes for validation/sandbox.
- [x] **Features** (`features.py`) — returns / range / (optional) volume, causal, z-scored.
- [x] **Validation** (`verify_hmm.py`) — ~99% regime recovery; quantifies the
  filter-vs-smooth look-ahead gap.
- [ ] **Regimes** (`regimes.py`) — auto-label states (bull/bear/crash/chop) + causal stream.
- [ ] **Strategy** (`strategy.py`) — k-of-n confirmations, hysteresis, cooldown.
- [ ] **Backtest** (`backtest.py`) — leveraged, walk-forward (no look-ahead), honest metrics.
- [ ] **Terminal** (`terminal.py`) — HTML dashboard: current regime + confidence, signal, chart, equity, trades.
- [ ] **Test** (`tests/test_no_lookahead.py`).

## Run

```bash
cd regime-terminal
python verify_hmm.py              # validate the HMM core (synthetic, no deps)
# later: python -m terminal --ticker BTC-USD --days 730   (real data, run locally)
```

Sandbox note: this environment's network allowlist blocks Yahoo Finance, so real
data must be fetched on your machine; synthetic data keeps everything runnable here.
Pure stdlib by default; `hmmlearn`/`yfinance` are optional production swaps.
