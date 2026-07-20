# Study: BTC 5m — basis-lead and maker-fill null (closes the two open 5m questions)

**Date:** 2026-07-20 · **Data:** live-collected 2026-07-08→07-20.
- Basis: RTDS Chainlink+Binance ticks (273.5k / 276.8k covered secs), 1070
  settled windows, **638 strike-computable** (Chainlink tick at both window
  start and end). Script: `scripts/basis_analysis.py`.
- Maker: CLOB trade tape (`scripts/collect_trades.py`), **989,301 trades**
  joined to a settled winner (07-10/07-11 overlap, where the up/down outcome
  sweep was still live). Script: `scripts/analyze_trades.py`.

These two questions were the local session's assignment before winding down the
5m collectors (PROGRESS 2026-07-11/12). Both resolve NULL. Settlement model
validated: computed Up/Down from Chainlink strike matched the official winner on
**100.0% of 638** windows.

## 1. Basis-lead → NULL (conclusive, fully powered)

Does the Binance-vs-Chainlink basis in the final seconds predict the Chainlink
residual move? Share of windows where `sign(basis) == sign(Chainlink move to close)`:

| offset | basis leads | n |
|---|---|---|
| T-1s | 49.7% | 608 |
| T-3s | 49.5% | 636 |
| T-5s | 51.3% | 637 |
| T-10s | 52.9% | 637 |

Flat on the 50% coin-flip line at every offset, n≈630. **The Binance feed carries
no independent signal about the Chainlink settlement.** The mechanism the whole
latency-arb thesis needs simply isn't there. (The downstream edge-vs-book test
stayed underpowered — only ~9% of windows are still contested that late, and the
book collector died 07-11 — but it's moot: no lead ⇒ can't beat the book.)

## 2. Maker fills → NULL for a strategy, but NOT via adverse selection

A CLOB trade's `side` is the taker aggressor, so `taker_side=SELL` is a realized
**maker-BUY fill**. Held to settlement at zero maker fee, edge/share =
(fill-conditional win rate − price). Size-weighted, by price bin:

| price bin | maker-BUY win rate | edge/sh |
|---|---|---|
| 0.0–0.1 | 4.5% (px 3.5%) | +1.01c |
| 0.4–0.5 | 46.2% (px 44.6%) | +1.57c |
| 0.7–0.8 | 74.4% (px 74.7%) | −0.35c |
| 0.8–0.9 | 87.9% (px 84.7%) | +3.18c |
| 0.9–1.0 | 98.1% (px 97.3%) | +0.78c |
| **favorites ≥0.80** | **96.0% (px 94.8%)** | **+1.26c** (37,002 fills) |

**The headline surprise: maker fills are NOT adversely selected.** Every bin's
maker-BUY edge is ≥0 (bar a −0.35c blip). This *contradicts* the modeled-fill sim
(2026-07-08), which assumed toxic fills and collapsed the maker thesis to
~$0.04/trade. Measured ≠ modeled — and the model was too pessimistic. On this
market, resting bids get hit at roughly fair value; makers are **not** picked off.

**Why it still doesn't make a strategy:** the only positive signal — favorites
winning 96.0% at a 94.8% price, +1.26c/share — is (a) weak: effective n is the
~900 distinct market outcomes, not 37k trades, so the 1.2pp gap is ≈1.8 SE
(p≈0.07); (b) in-sample to the 07-10/11 regime; and (c) **already falsified out
of sample** by calibration sample 3 (n=391, 07-11/12): longshots priced 7.7% vs
7.8% implied — dead-on fair, which makes the mirror favorite edge fair too. It is
the same regime-noise the longshot fade died of. Zero fees × no persistent
mispricing = zero.

## Conclusion — both 5m questions closed

- **Basis:** no lead. Dead.
- **Maker:** the failure mode is **"no persistent edge to quote around," not
  "adverse selection."** That distinction matters for the fee-free pivot's F3
  (maker-quoting) candidate: Polymarket crypto maker fills are not inherently
  toxic, so a maker strategy is viable *where a real edge exists* — 5m BTC just
  isn't one. Scoreboard unchanged: five 5m candidates, five dead, **$0 lost.**

5m BTC is fully worked out. The collectors can wind down (the up/down book
collector already died 07-11; RTDS + trade tape kept for this study are no longer
needed). Reusable assets: `analyze_trades.py`, `basis_analysis.py`, and the
verified-live `collect_trades.py` (its `last_trade_price`/taker-side mechanics
transfer directly to the fee-free maker study, F3).
