# STRATEGY v2 — BTC 5-minute up/down (2026-07-09)

The single working strategy document. Supersedes polybot's original spec
(momentum-taker) where they conflict. Every claim below cites tape or a
study; update this file when evidence changes, not chat threads.

## The kill list — tested and dead, do not resurrect

| Idea | Evidence | Verdict |
|---|---|---|
| Naive taker "buy the favorite" | Calibration study n=638: avg PnL exactly $0.00 pre-spread; sim decayed 75% as sample grew | DEAD |
| Momentum / coinflip directional taker | PnL sim: −$24/trade; the 176-trade community post-mortem hit the same wall (80% win rate at $0.85 entry = structural loser) | DEAD |
| Binance-leads-Chainlink latency arb | Basis-lead flat ~50% at every offset (n≈190); book already decisive by T-30s in ~65% of windows, only ~9% contested; formal close-out pending n≥30/offset (~2-3 days) | DEAD pending formal NULL |
| Last-second taker snipe (99¢ residuals) | Fee = ~7% of gross upside at high p + tail risk of final-tick reversal; killed platform-wide Jan 2026 (research + wallet taxonomy) | DEAD by design |

## The survivor — one candidate, one open question

**Fade the longshot (equivalently: own the heavy favorite ≥$0.80) near the
window close.**

- Raw evidence: +$2.91/trade, 96.6% hit rate, n=238, decayed least of all
  sim candidates; calibration studies (n=638) independently show longshots
  (≤15¢) winning ~3% vs ~6% implied.
- Why it can exist: retail lottery demand + the fee curve pushing sharp
  flow out of exactly this zone; and ties resolve Up (a structural crumb).
- Why it is NOT yet a strategy: sim assumes idealized taker fills (you
  cannot lift unlimited size at the ask at T-30s), and the maker version —
  the only fee-viable expression at scale — collapsed to ~$0.04/trade under
  *modeled* adverse selection. Modeled ≠ measured.
- **The one open question: who fills the maker?** If longshot buyers in the
  final minute are dumb flow, the maker edge is real. If they are informed
  (buying cheap reversals they already see on the feed), makers get picked
  off precisely when it costs the most. Only the trade tape answers this.
  → Trade-tape collector: owned by the local session (in progress).

## v2 architecture (paper first — Phase 6 gate unchanged)

1. **Fair value from the referee, not the proxy.** p_up = Φ(chainlink_move
   / σ√τ) computed off the Chainlink RTDS feed (strike + current); Binance
   feed is a fast confirmation input only. (Basis carries no independent
   signal — measured, not assumed.)
2. **Maker-first expression.** Rest offers on the longshot side (sell the
   overpriced lottery ticket) sized off fair value; zero fee + rebate
   eligibility. Requote/cancel discipline on Chainlink moves > threshold.
3. **Taker only through the fee gate.** Any crossing must clear
   edge ≥ 0.07·p(1−p) + spread + adverse-selection buffer. The fee-aware
   Kelly gate now enforces the fee term mechanically (polybot
   `risk_engine.py`, fixed 2026-07-09): at 50¢ the bar is +1.75 prob
   points, verified by test (51% @ 50¢ refused, 55% trades).
4. **Hard entry cap $0.85 taker** (the 80%-win-at-85¢ trap), **no FOK
   pairs** (100:1 leg-risk post-mortem), **assume no exit after T-30s**
   (book evaporates — size every position for hold-to-settlement), **chop
   filter before any directional logic**, loss-streak cooldown.
5. **Fees read live per market** (feeSchedule); never hardcoded — one
   zombie market carries a 0.25 legacy rate, and the platform changes
   parameters silently.

Breakeven win rates for taker entries (fee only, add spread on top):
50¢ → 51.75% · 60¢ → 61.68% · 70¢ → 71.47% · 80¢ → 81.12% · 90¢ → 90.63%

## Gates before real money (in order, all mandatory)

1. Trade-tape study: maker fills on the longshot side show fill-conditional
   hit rate within 2 points of unconditional (i.e., adverse selection is
   bounded), n ≥ 300 fills.
2. Basis test formally closed (n≥30/offset contested windows).
3. Signal survives ≥2 weeks of tape spanning ≥2 volatility regimes, with
   deflated stats (Phase 4 corrections, all variants counted).
4. ≥2 weeks profitable **paper** trading through polybot with real quotes.
5. User types `GO LIVE` (Phase 7 gate, unchanged).

## Fixed this session (2026-07-09, cloud)

polybot cost model aligned with verified reality (was `POLYMARKET_FEE=0.0`):
Fee V2 curve in `calculate_pnl` (leg fee = stake·rate·(1−p)), backtest cost
accounting matched, fee-aware Kelly gate in `risk_engine.size()`. Its
backtests no longer flatter themselves; `fee_rate=0` remains available to
model maker fills. No-lookahead tests pass; fee math unit-checked.
