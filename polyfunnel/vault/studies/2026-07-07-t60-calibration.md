# Study: BTC 5m up/down calibration at T-60s

**Date:** 2026-07-07 · **Data:** 200 consecutive settled `btc-up-or-down-5m`
markets (~17h ending 07:20 UTC) · **Source:** CLOB `prices-history`
fidelity=1 on the Up token, last observed price ≤ T-60s / T-240s before
window end; official winners from Gamma `outcomePrices`.
**Script:** `scripts/study_t60_calibration.py` (rerunnable).

## Findings

1. **The market is well-calibrated one minute before close.** Every price
   bucket's realized Up-win rate sits on the diagonal within its 95% CI
   (e.g. priced 0.7–0.8 → won 80.0%; priced 0.9+ → won 96.9%; priced <0.1 →
   won 0.0%). No naive price-only mispricing detected at n=200.

2. **"Buy the favorite at T-60" ≈ zero after honest accounting.** 191
   trades, favorite won 81.7% (CI 76–87%). Nominal +0.65¢/share after the
   0.07·p(1−p) taker fee — but (a) SE per trade is ~2.5¢, so the estimate is
   statistically indistinguishable from zero, and (b) entry is modeled at the
   minute-history price, not the executable ask: the ~1¢ spread alone eats
   the whole nominal edge. **Verdict: no lazy taker edge.**

3. **Momentum continuation (T-240→T-60 direction) 82.1%** — but this is
   nearly the same event as "the favorite wins" (price has already moved
   toward the winner). Not an independent signal at this granularity.

4. **Longshot hint:** tokens priced ≤0.15 at T-60 (avg 0.058) won only 3.9%
   (CI 1–11%). Consistent with mild longshot overpricing (≈ favorite side
   marginally cheap), but the CI includes fair value. Watch at larger n.

## Limitations

- One ~17-hour window, one volatility regime, n=200. No claim survives
  Phase 4 deflation from this sample size alone.
- Minute-fidelity trade prices, not books: no spread/depth, no executable
  entry price, no sub-minute structure. The live collector exists precisely
  to remove this limitation.
- `prices-history` fidelity=1 returned data for **200/200 recently-settled
  markets** — decision-time *price* datasets can be extended retroactively
  for at least ~17h back (books still cannot).

## Follow-up 2026-07-08 (~05:40 UTC): n=400 rerun

Fresh sample (400 settled markets, ~33h window, again 400/400 with usable
minute history):

- **Calibration still holds globally; taker favorite strategy exactly zero**
  (382 trades, avg PnL −0.0000/share before spread — i.e. clearly negative
  after spread).
- **Longshot overpricing strengthened:** sides priced ≤0.15 at T-60
  (avg implied 6.4%) won **2.5%** (n=162, CI [0.01,0.06] — upper bound now
  at/below implied). Pooled with 2026-07-07: ~7 wins in 239 ≈ **2.9% realized
  vs ~6.2% implied**.
- Shape detail: mid-favorites (0.6–0.8) ran slightly *below* implied while
  extreme favorites (0.9+) ran above — the mispricing concentrates in the
  tails (classic favorite-longshot bias).
- Candidate expression (NOT validated): **maker-sell the ≤15¢ longshot side
  near T-60** — zero fee, rebate-eligible, gross EV ≈ +3.5¢/share sold *if*
  fills are not adversely selected. The adverse-selection question (are
  longshot buyers in the final minute the informed ones catching reversals?)
  is unanswerable from price history — it needs the collector's book data +
  the Chainlink/Binance basis. This is now the #1 question for Phase 3.
- Still one-ish regime, ~2 days, and a post-hoc bucket choice — Phase 4
  deflation applies. Do not size anything on this yet.

## Implications for the funnel

- Fee + spread + calibrated prices ⇒ any real edge must come from
  information the last-minute price does not already contain: order-book
  microstructure (collector data), underlying spot lead (local feed), or
  from **maker-side execution** capturing the spread instead of paying it.
- Next studies once collector data accrues: T-30s book-imbalance vs outcome;
  effective spread at decision time; maker fill probability near close.
