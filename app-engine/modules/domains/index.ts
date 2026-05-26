import type { ScoredTrend, TokenUsage } from '../trends/claude-scorer';
import { generateDomainCandidates } from './generate';
import { checkAvailability } from './availability';
import { appraiseDomains, type Appraisal } from './appraisal';

export type DomainResult = Appraisal & {
  sld: string;
  tld: string;
  strategy: string;
  basis: string;
  estPrice: number; // estimated annual registration cost (USD)
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
    usage: TokenUsage;
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

// Composite score: a buyable domain needs both worth and a buyer. We weight
// sellability heavily, then layer in value (log-scaled so a $50k name doesn't
// drown out everything) and a small premium for short, clean names.
function compositeScore(a: Appraisal, sld: string): number {
  const sellability = Math.max(0, Math.min(100, a.sellability)); // 0-100
  const valueScore = Math.min(100, (Math.log10(Math.max(a.valueMedian, 1)) / 5) * 100); // $1=0, $100k=100
  const lengthBonus = sld.length <= 8 ? 10 : sld.length <= 12 ? 5 : 0;
  const raw = sellability * 0.55 + valueScore * 0.35 + lengthBonus;
  return Math.round(Math.max(0, Math.min(100, raw)));
}

export async function runDomainHunt(
  trends: ScoredTrend[],
  env: { ANTHROPIC_API_KEY: string; GODADDY_API_KEY?: string; GODADDY_API_SECRET?: string },
  opts: { maxTrends?: number; maxCandidates?: number; maxAppraise?: number } = {},
): Promise<DomainHuntResult> {
  const t0 = Date.now();
  const maxTrends = opts.maxTrends ?? 10;
  const maxCandidates = opts.maxCandidates ?? 60;
  const maxAppraise = opts.maxAppraise ?? 20;

  // 1. Generate candidates from the top trends.
  const topTrends = trends.slice(0, maxTrends);
  const { candidates, usage: genUsage } = await generateDomainCandidates(topTrends, env.ANTHROPIC_API_KEY, {
    maxTotal: maxCandidates,
  });

  // 2. Check availability. GoDaddy API is used when credentials are present;
  //    it is significantly more accurate than RDAP for .io, .ai, and .co TLDs.
  const godaddy =
    env.GODADDY_API_KEY && env.GODADDY_API_SECRET
      ? { key: env.GODADDY_API_KEY, secret: env.GODADDY_API_SECRET }
      : undefined;
  const availabilityMap = await checkAvailability(candidates.map((c) => c.domain), godaddy);
  const available = candidates.filter((c) => availabilityMap.get(c.domain) === 'available');

  // 3. Appraise the best available candidates (bounded for time/cost).
  const toAppraise = available.slice(0, maxAppraise);
  const { appraisals, usage: appraisalUsage } = await appraiseDomains(toAppraise, env);
  const appraisalByDomain = new Map(appraisals.map((a) => [a.domain, a]));

  // 4. Merge, score, rank.
  const domains: DomainResult[] = toAppraise
    .map((c): DomainResult | null => {
      const a = appraisalByDomain.get(c.domain);
      if (!a) return null;
      const estPrice = estPriceFor(c.tld);
      return {
        ...a,
        sld: c.sld,
        tld: c.tld,
        strategy: c.strategy,
        basis: c.basis,
        estPrice,
        roi: Math.round((a.valueMedian / estPrice) * 10) / 10,
        score: compositeScore(a, c.sld),
      };
    })
    .filter((d): d is DomainResult => d !== null)
    .sort((a, b) => b.score - a.score);

  const sources = new Set(domains.map((d) => d.valueSource));
  const valuationSource: DomainHuntResult['meta']['valuationSource'] =
    sources.size > 1 ? 'mixed' : sources.has('godaddy') ? 'godaddy' : 'claude';

  return {
    domains,
    meta: {
      generated: candidates.length,
      checked: candidates.length,
      available: available.length,
      appraised: domains.length,
      durationMs: Date.now() - t0,
      valuationSource,
      usage: {
        inputTokens: genUsage.inputTokens + appraisalUsage.inputTokens,
        outputTokens: genUsage.outputTokens + appraisalUsage.outputTokens,
      },
    },
  };
}
