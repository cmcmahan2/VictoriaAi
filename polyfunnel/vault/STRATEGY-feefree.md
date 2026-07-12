# STRATEGY — fee-free segment (v1, 2026-07-11)

Pivot rationale: five 5m-BTC candidates tested, all dead or dying, $0 lost.
The fee-free segment (feesEnabled=false, mostly geopolitics/world events)
is the structurally softest target on the platform: $8.5M+/day observed,
zero taker fees (no 7% wall to climb), spreads up to several cents on
liquid books, news-paced repricing (human-compatible speed), and thinner
bot competition. Same funnel rules apply: hypothesis → backtest → kill or
paper trade. Nothing here is validated yet.

## Candidate F1 — favorite-longshot bias, long-horizon
**Hypothesis:** political/geopolitical longshots are chronically overpriced
(documented across prediction markets for decades; retail buys narratives).
Fee-free means fading them has no fee drag.
**Test available NOW (no collection wait):** historical calibration study
on RESOLVED fee-free markets — price at T-7d/T-30d vs outcome, exactly the
machinery that just executed the 5m candidates. Survivorship caveats apply
(only resolved markets; condition on category and horizon).
**Kill criterion:** calibration diagonal within CI at every price bucket →
dead, same as 5m.

## Candidate F2 — date-ladder coherence (relative value, model-free)
**Hypothesis:** event families like "X happens by March / by June / by
December" must be monotone (P_by_March ≤ P_by_June). Retail flow on one
rung leaves violations or compressed gaps that imply near-arbitrage.
**Test:** screener extension scanning event families for monotonicity
violations and suspicious gaps; log frequency/size/persistence before any
trade design. Model-free — violations are provable mispricings of at least
one leg.
**Kill criterion:** violations rarer than ~1/week above 2c after spread, or
vanish within minutes (bot-served already).

## Candidate F3 — maker quoting on wide fee-free books
**Hypothesis:** wide spreads (2-5c) on $100k+/day fee-free markets pay a
quoting yield with zero fee drag + liquidity-reward eligibility; adverse
selection is news-driven and partially avoidable (pull quotes on headline
risk hours).
**Test:** needs live book tape → `collect_feefree.py` (this session).
Measure: realized spread capture vs mid-drift after fills (the same
adverse-selection question the 5m maker idea died on — but news-paced,
not oracle-paced).
**Kill criterion:** fill-conditional mid-drift eats >70% of quoted spread.

## Candidate F4 — news-lag fade (hardest, last)
**Hypothesis:** fee-free books reprice slowly after verifiable public news;
first mover advantage measured in minutes, not ms.
**Test:** requires live tape + timestamped news source; design only after
F1-F3 verdicts. Parked.

## Hazard ledger (fee-free specific — respect these)
- **Resolution risk:** these markets resolve via UMA's optimistic oracle —
  human-adjudicated, disputable, historically manipulable (research prompt
  covers incidents). A "sure thing" can resolve against you. Cap position
  size per market; prefer markets with unambiguous resolution criteria.
- **Long capital lockup:** months-dated markets tie up bankroll; annualize
  every edge before comparing to the 5m world.
- **Thin far books:** volume concentrates near the top; depth-check before
  sizing anything.
- **Fee status can change silently** (the platform's habit) — screener
  re-checks feesEnabled on every scan.

## Status
- [ ] F1 historical calibration study (cloud session, next)
- [ ] F2 coherence scanner (edge_screener extension)
- [ ] F3 live book collection (`collect_feefree.py` → user's PC)
- [ ] User deep-research pass (prompt in chat 2026-07-11)
- 5m BTC: collectors stay up only until local session closes basis/trade-
  tape; then null study + wind-down.
