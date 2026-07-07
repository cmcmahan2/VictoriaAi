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

## Implications for the funnel

- Fee + spread + calibrated prices ⇒ any real edge must come from
  information the last-minute price does not already contain: order-book
  microstructure (collector data), underlying spot lead (local feed), or
  from **maker-side execution** capturing the spread instead of paying it.
- Next studies once collector data accrues: T-30s book-imbalance vs outcome;
  effective spread at decision time; maker fill probability near close.
