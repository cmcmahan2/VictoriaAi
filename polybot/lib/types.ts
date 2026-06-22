// Shared types for the Polymarket arbitrage finder.

export type ArbType = "binary" | "multi" | "logical";

/**
 * One leg of an arbitrage = one outcome token you must buy to complete a set.
 * For a "complete set" of mutually-exclusive outcomes, exactly one leg pays
 * out $1 at resolution, so buying one share of every leg guarantees $1 back.
 */
export interface OutcomeLeg {
  label: string; // "Yes" / "No" / candidate name
  tokenId: string;
  askPrice: number; // best ask in USDC, 0..1 (what it costs to buy 1 share)
  askSize: number; // shares available at that ask (depth cap)
}

/** A market pulled from Polymarket (or demo data) before arb analysis. */
export interface RawMarket {
  id: string;
  type: ArbType; // how its legs should be combined into a complete set
  question: string;
  slug?: string;
  category?: string;
  endDate?: string;
  outcomes: OutcomeLeg[];
}

/** A computed, profitable arbitrage opportunity. */
export interface ArbOpportunity {
  id: string;
  type: ArbType;
  question: string;
  slug?: string;
  category?: string;
  endDate?: string;
  legs: OutcomeLeg[];
  costPerSet: number; // sum of ask prices; < 1 means an arb exists
  grossEdge: number; // 1 - costPerSet (profit per set before fees)
  feePct: number; // fee applied to net winnings (fraction)
  netEdgePerSet: number; // profit per set after fees
  roiPct: number; // netEdgePerSet / costPerSet * 100  (the "arb %")
  maxSets: number; // capped by thinnest leg's depth
  maxStake: number; // costPerSet * maxSets (USDC to deploy for full capture)
}

/** A logged bet for the tracker. */
export interface TrackedBet {
  id: string;
  marketId: string; // links the bet to its market chart
  question: string;
  type: ArbType;
  auto?: boolean; // placed by the paper auto-trader vs. logged manually
  legs: { label: string; price: number; shares: number; cost: number }[];
  stake: number; // total USDC deployed
  expectedReturn: number; // guaranteed payout at resolution (= sets * $1)
  expectedProfit: number; // expectedReturn - stake, after fees
  status: "open" | "won" | "lost";
  actualProfit?: number; // filled in when resolved
  placedAt: string; // ISO
  note?: string;
}
