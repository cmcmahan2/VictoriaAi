import type { ArbOpportunity, OutcomeLeg, RawMarket } from "./types";

/**
 * Core arbitrage math for Polymarket-internal opportunities.
 *
 * The unifying idea across all three arb types is the "complete set":
 * a group of mutually-exclusive outcome tokens where exactly ONE resolves
 * to $1. Buying one share of every leg costs `sum(askPrice)` and is
 * guaranteed to return exactly $1 at resolution. So whenever
 *
 *     sum(askPrice) < $1
 *
 * the difference is risk-free profit (before fees and execution risk).
 *
 *   - binary: the two legs are YES + NO of a single market.
 *   - multi:  the N legs are the YES tokens of a mutually-exclusive
 *             multi-outcome ("negRisk") market.
 *   - logical: legs assembled from correlated markets via a rules config
 *             (handled upstream; the math here is identical once legs exist).
 */

/** Fee is charged on net winnings (the profit), not the stake. */
export function analyzeMarket(
  market: RawMarket,
  feePct: number,
  bankroll: number,
): ArbOpportunity | null {
  const legs = market.outcomes;
  if (legs.length < 2) return null;

  const costPerSet = round(legs.reduce((s, l) => s + l.askPrice, 0), 6);

  // Each complete set returns exactly $1. No arb unless a set costs < $1.
  if (costPerSet >= 1) return null;

  const grossEdge = round(1 - costPerSet, 6);
  const netEdgePerSet = round(grossEdge * (1 - feePct), 6);
  if (netEdgePerSet <= 0) return null;

  const roiPct = round((netEdgePerSet / costPerSet) * 100, 2);

  // How many complete sets can we actually buy? Limited by the thinnest leg
  // (you can't complete a set without filling its scarcest token) and by the
  // bankroll the user is willing to deploy.
  const depthCap = Math.min(...legs.map((l) => l.askSize));
  const bankrollCap = bankroll > 0 ? Math.floor(bankroll / costPerSet) : depthCap;
  const maxSets = Math.max(0, Math.floor(Math.min(depthCap, bankrollCap)));
  if (maxSets <= 0) return null;

  return {
    id: market.id,
    type: market.type,
    question: market.question,
    slug: market.slug,
    category: market.category,
    endDate: market.endDate,
    legs,
    costPerSet,
    grossEdge,
    feePct,
    netEdgePerSet,
    roiPct,
    maxSets,
    maxStake: round(costPerSet * maxSets, 2),
  };
}

/** Scan many markets, keep the profitable ones, best ROI first. */
export function findArbs(
  markets: RawMarket[],
  opts: { feePct: number; bankroll: number; minRoiPct?: number } = {
    feePct: 0,
    bankroll: 0,
  },
): ArbOpportunity[] {
  const minRoi = opts.minRoiPct ?? 0;
  return markets
    .map((m) => analyzeMarket(m, opts.feePct, opts.bankroll))
    .filter((a): a is ArbOpportunity => a !== null && a.roiPct >= minRoi)
    .sort((a, b) => b.roiPct - a.roiPct);
}

/**
 * Build a concrete stake plan for one opportunity at a chosen total stake.
 * Because every leg of a complete set pays the same $1, equal share counts
 * across legs is what locks the guaranteed return. We buy `sets` of each.
 */
export function buildStakePlan(arb: ArbOpportunity, totalStake: number) {
  const setsAffordable = Math.floor(totalStake / arb.costPerSet);
  const sets = Math.max(0, Math.min(setsAffordable, arb.maxSets));
  const legs = arb.legs.map((l: OutcomeLeg) => ({
    label: l.label,
    price: l.askPrice,
    shares: sets,
    cost: round(l.askPrice * sets, 2),
  }));
  const stake = round(legs.reduce((s, l) => s + l.cost, 0), 2);
  const guaranteedReturn = sets; // sets * $1
  const profit = round((guaranteedReturn - stake) * (1 - arb.feePct), 2);
  return { sets, legs, stake, guaranteedReturn, profit };
}

function round(n: number, dp: number) {
  const f = 10 ** dp;
  return Math.round(n * f) / f;
}
