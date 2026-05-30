import type { RawProperty } from '../properties/types';
import type { ScoredProperty, ArvConfidence } from '../scoring/claude-scorer';

export type DealAnalysis = {
  property: RawProperty;
  wholesaleScore: number;
  distressScore: number;
  momentumScore: number;
  sellerMotivation: number;
  arvEstimate: number;
  arvConfidence: ArvConfidence;
  repairEstimate: number;
  /** MAO = ARV × maoPercentage − repairEstimate (clamped to 0) */
  mao: number;
  /** ARV − asking price: positive means below-market, negative means overpriced */
  equitySpread: number;
  /** MAO − asking price: positive means viable wholesale deal at list, negative means needs negotiation */
  projectedProfit: number;
  /** projectedProfit / price — normalized for cross-market ranking */
  profitRatio: number;
  isViableDeal: boolean;
  scoreSummary: string;
};

/**
 * Merges raw property data with Claude's score output into a complete deal analysis.
 * maoPercentage must be a decimal between 0 and 1 (e.g. 0.70 for the 70% rule).
 * If a value > 1 is received it is divided by 100 to prevent silent arithmetic errors.
 */
export function buildDealAnalysis(
  property: RawProperty,
  scoreData: Partial<ScoredProperty>,
  maoPercentage: number = 0.70,
): DealAnalysis {
  // Guard: if caller sends 70 instead of 0.70, normalize it; clamp to valid range
  const rawPct = maoPercentage > 1 ? maoPercentage / 100 : maoPercentage;
  const pct = Math.max(0.01, Math.min(0.99, rawPct));

  const arvEstimate = scoreData.arvEstimate ?? fallbackArv(property);
  const arvConfidence: ArvConfidence = scoreData.arvConfidence ?? 'low';
  const repairEstimate = scoreData.repairEstimate ?? fallbackRepair(property);

  const mao = Math.max(0, Math.round(arvEstimate * pct - repairEstimate));
  const equitySpread = Math.round(arvEstimate - property.price);
  const projectedProfit = Math.round(mao - property.price);
  const profitRatio = property.price > 0 ? projectedProfit / property.price : 0;
  // A deal is viable if it passes the 70% rule at list price OR has a strong score
  // (high-score properties often have negotiation room even if list > MAO)
  const wholesaleScore = scoreData.wholesaleScore ?? 0;
  const isViableDeal = projectedProfit > 0 || (wholesaleScore >= 75 && equitySpread > 0);

  return {
    property,
    wholesaleScore: scoreData.wholesaleScore ?? 0,
    distressScore: scoreData.distressScore ?? 0,
    momentumScore: scoreData.momentumScore ?? 0,
    sellerMotivation: scoreData.sellerMotivation ?? 0,
    arvEstimate,
    arvConfidence,
    repairEstimate,
    mao,
    equitySpread,
    projectedProfit,
    profitRatio,
    isViableDeal,
    scoreSummary: scoreData.scoreSummary ?? '',
  };
}

/**
 * Fallback ARV when Claude is unavailable.
 * Tax assessed value is typically 78–82% of market value — dividing by 0.78
 * gives a more accurate ARV than the old ×1.15 multiplier. Falls back to
 * last-sale-with-appreciation when assessed value is missing.
 */
function fallbackArv(p: RawProperty): number {
  const taxBase = p.taxAssessedValue ?? 0;
  if (taxBase > 0) {
    return Math.round(taxBase / 0.78 / 1000) * 1000;
  }
  // Last sale + ~4% annual appreciation (capped at 10 years)
  if (p.lastSoldPrice && p.lastSoldPrice > 0 && p.lastSoldDate) {
    const soldYear = parseInt(p.lastSoldDate.slice(0, 4), 10);
    const yearsAgo = Math.min(new Date().getFullYear() - soldYear, 10);
    return Math.round(p.lastSoldPrice * Math.pow(1.04, yearsAgo) / 1000) * 1000;
  }
  return Math.round(p.price * 1.08 / 1000) * 1000;
}

/**
 * Renovation premium tiers by age — scaled to 8–22% of typical ARV.
 * Pre-1965 homes commonly need full gut rehabs; post-2010 need cosmetic work only.
 */
function fallbackRepair(p: RawProperty): number {
  const age = new Date().getFullYear() - (p.yearBuilt || 1980);
  if (age > 60) return 55000;
  if (age > 40) return 40000;
  if (age > 25) return 28000;
  if (age > 15) return 18000;
  return 10000;
}

export function buildMarketSummary(analyses: DealAnalysis[]): {
  totalProperties: number;
  hotDeals: number;
  potentialDeals: number;
  avgWholesaleScore: number;
  avgEquitySpread: number;
  medianListPrice: number;
  topDistressSignals: string[];
} {
  if (analyses.length === 0) {
    return {
      totalProperties: 0,
      hotDeals: 0,
      potentialDeals: 0,
      avgWholesaleScore: 0,
      avgEquitySpread: 0,
      medianListPrice: 0,
      topDistressSignals: [],
    };
  }

  const hotDeals = analyses.filter(a => a.wholesaleScore >= 75).length;
  const potentialDeals = analyses.filter(a => a.wholesaleScore >= 50 && a.wholesaleScore < 75).length;
  const avgWholesaleScore = Math.round(analyses.reduce((s, a) => s + a.wholesaleScore, 0) / analyses.length);
  const avgEquitySpread = Math.round(analyses.reduce((s, a) => s + a.equitySpread, 0) / analyses.length);

  const prices = analyses.map(a => a.property.price).sort((a, b) => a - b);
  const mid = Math.floor(prices.length / 2);
  const medianListPrice = prices.length % 2 === 0
    ? Math.round(((prices[mid - 1] ?? 0) + (prices[mid] ?? 0)) / 2)
    : (prices[mid] ?? 0);

  const signalCounts = new Map<string, number>();
  for (const a of analyses) {
    for (const sig of a.property.distressSignals) {
      signalCounts.set(sig, (signalCounts.get(sig) ?? 0) + 1);
    }
  }
  const topDistressSignals = [...signalCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([sig]) => sig);

  return { totalProperties: analyses.length, hotDeals, potentialDeals, avgWholesaleScore, avgEquitySpread, medianListPrice, topDistressSignals };
}
