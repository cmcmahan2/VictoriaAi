import type { ScoredTrend } from '../trends/claude-scorer';
import { generateDomainCandidates } from './generate';
import { checkAvailability } from './availability';
import { appraiseDomains, type Appraisal } from './appraisal';

export type DomainResult = Appraisal & {
  sld: string;
  tld: string;
  strategy: string;
  basis: string;
  estPrice: number; // annual registration cost (USD): real from GoDaddy, else estimated
  priceConfirmed: boolean;            // true when estPrice is the registrar's real price
  availabilitySource: 'godaddy' | 'rdap'; // who confirmed it's available
  score: number;    // composite 1-100 used for ranking
  roi: number;      // valueMedian / estPrice
};

export type DomainHuntResult = {
  domains: DomainResult[];
  meta: {
    generated: number;
    checked: number;
    available: number;
    appraised: number;
    durationMs: number;
    valuationSource: 'godaddy' | 'claude' | 'mixed';
    availabilitySource: 'godaddy' | 'rdap' | 'mixed';
  };
};

// Typical first-year registration prices by TLD (USD). Used to estimate cost
// basis and ROI since RDAP does not expose pricing.
const TLD_PRICE: Record<string, number> = {
  com: 12,
  net: 14,
  org: 12,
  io: 39,
  ai: 70,
  co: 30,
  app: 18,
  dev: 15,
};
const DEFAULT_PRICE = 20;

function estPriceFor(tld: string): number {
  return TLD_PRICE[tld] ?? DEFAULT_PRICE;
}

// Composite score: a buyable domain needs worth, a buyer, AND a liquid market.
// We weight sellability (does THIS name sell) and demand (how many buyers / how
// easy to sell) most heavily, then layer in value (log-scaled so a $50k name
// doesn't drown out everything) and a small premium for short, clean names.
function compositeScore(a: Appraisal, sld: string): number {
  const sellability = Math.max(0, Math.min(100, a.sellability)); // 0-100
  const demand = Math.max(0, Math.min(100, a.demand));           // 0-100
  const valueScore = Math.min(100, (Math.log10(Math.max(a.valueMedian, 1)) / 5) * 100); // $1=0, $100k=100
  const lengthBonus = sld.length <= 8 ? 10 : sld.length <= 12 ? 5 : 0;
  const raw = sellability * 0.4 + demand * 0.3 + valueScore * 0.2 + lengthBonus;
  return Math.round(Math.max(0, Math.min(100, raw)));
}

export async function runDomainHunt(
  trends: ScoredTrend[],
  env: { ANTHROPIC_API_KEY: string; GODADDY_API_KEY?: string; GODADDY_API_SECRET?: string },
  opts: { maxTrends?: number; maxCandidates?: number; maxAppraise?: number } = {},
): Promise<DomainHuntResult> {
  const t0 = Date.now();
  const maxTrends = opts.maxTrends ?? 12;
  const maxCandidates = opts.maxCandidates ?? 80;
  const maxAppraise = opts.maxAppraise ?? 24;

  // 1. Generate candidates from the top trends.
  const topTrends = trends.slice(0, maxTrends);
  const candidates = await generateDomainCandidates(topTrends, env.ANTHROPIC_API_KEY, {
    maxTotal: maxCandidates,
  });

  // 2. Check availability. GoDaddy (authoritative + real prices) when
  //    configured, with RDAP filling the gaps; only confirmed-available
  //    candidates move forward.
  const godaddyCreds =
    env.GODADDY_API_KEY && env.GODADDY_API_SECRET
      ? { key: env.GODADDY_API_KEY, secret: env.GODADDY_API_SECRET }
      : null;
  const availabilityMap = await checkAvailability(candidates.map((c) => c.domain), godaddyCreds);
  const available = candidates.filter(
    (c) => availabilityMap.get(c.domain)?.status === 'available',
  );

  // 3. Appraise the best available candidates (bounded for time/cost).
  const toAppraise = available.slice(0, maxAppraise);
  const appraisals = await appraiseDomains(toAppraise, env);
  const appraisalByDomain = new Map(appraisals.map((a) => [a.domain, a]));

  // 4. Merge, score, rank.
  const domains: DomainResult[] = toAppraise
    .map((c): DomainResult | null => {
      const a = appraisalByDomain.get(c.domain);
      if (!a) return null;
      const avail = availabilityMap.get(c.domain);
      const realPrice = avail?.price;
      const estPrice = realPrice ?? estPriceFor(c.tld);
      return {
        ...a,
        sld: c.sld,
        tld: c.tld,
        strategy: c.strategy,
        basis: c.basis,
        estPrice,
        priceConfirmed: realPrice != null,
        availabilitySource: avail?.source ?? 'rdap',
        roi: Math.round((a.valueMedian / estPrice) * 10) / 10,
        score: compositeScore(a, c.sld),
      };
    })
    .filter((d): d is DomainResult => d !== null)
    .sort((a, b) => b.score - a.score);

  const sources = new Set(domains.map((d) => d.valueSource));
  const valuationSource: DomainHuntResult['meta']['valuationSource'] =
    sources.size > 1 ? 'mixed' : sources.has('godaddy') ? 'godaddy' : 'claude';

  const availSources = new Set(
    available.map((c) => availabilityMap.get(c.domain)?.source).filter(Boolean),
  );
  const availabilitySource: DomainHuntResult['meta']['availabilitySource'] =
    availSources.size > 1 ? 'mixed' : availSources.has('godaddy') ? 'godaddy' : 'rdap';

  return {
    domains,
    meta: {
      generated: candidates.length,
      checked: candidates.length,
      available: available.length,
      appraised: domains.length,
      durationMs: Date.now() - t0,
      valuationSource,
      availabilitySource,
    },
  };
}
