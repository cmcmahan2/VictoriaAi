import Anthropic from '@anthropic-ai/sdk';
import type { RawProperty } from '../properties/types';

export type ArvConfidence = 'high' | 'medium' | 'low';

// Fields Claude returns. MAO / equitySpread / projectedProfit are computed
// in analysis.ts from these values — Claude does not return them.
export type ScoredProperty = RawProperty & {
  wholesaleScore: number;
  distressScore: number;
  momentumScore: number;
  sellerMotivation: number;
  arvEstimate: number;
  arvConfidence: ArvConfidence;
  repairEstimate: number;
  scoreSummary: string;
};

export type TokenUsage = { inputTokens: number; outputTokens: number };

// System prompt is >1024 tokens so ephemeral caching applies — ~90% cost
// reduction on repeated calls within the same cache window.
const SYSTEM_PROMPT = `You are a real estate investment analyst scoring properties for two audiences: wholesale investors and real estate developers.

PROPERTY TYPES — score each differently:

RESIDENTIAL (SFR, MFR, Condo, Townhouse):
- wholesaleScore: Fix-and-flip / assignment potential. 75+ = strong deal. 50-74 = worth investigating. Below 50 = weak.
- Use the 70% rule: MAO = ARV × 0.70 − repairs. If asking price is near or above MAO, score below 50.
- arvEstimate: Post-renovation market value based on zip, size, beds/baths, year built.
- repairEstimate: Cost to bring to ARV condition. Range: $10k (cosmetic) to $80k (gut rehab).

LAND / VACANT LOTS:
- wholesaleScore: Development / infill potential. Score based on: location quality, price vs comparable improved lots, motivated seller signals (high DOM, below last sale price), and development demand in that zip/city.
- arvEstimate: Estimated value of the lot after entitlement or with a finished structure — e.g., a $12k Memphis lot in a rezoning corridor might support a $180k build with $140k in construction costs.
- repairEstimate: Estimated site prep + infrastructure cost (utilities, grading, permits). Typical: $15k–$60k for infill lots.
- Do NOT penalize land for having 0 bedrooms or 0 sqft — those are expected. Score the land on its own merits.
- High DOM on land often signals a motivated seller willing to negotiate, NOT a bad asset.

SHARED SCORING DIMENSIONS:
1. wholesaleScore (1-100): Overall investment potential for the property type.
2. distressScore (1-100): Seller/asset distress. High DOM, below last-sale price, tax liens, pre-foreclosure, estate, absentee owner all increase this.
3. momentumScore (1-100): Market momentum in that zip/neighborhood. Development activity, rising prices, investor demand increase this.
4. sellerMotivation (1-100): Probability seller accepts a below-market offer. Long DOM + absentee/estate = high motivation.

Rules:
- Output ONLY valid JSON — no prose, no markdown fences, no explanation outside the JSON.
- arvConfidence: "high" = strong local comps; "medium" = reasonable estimate; "low" = limited data.
- scoreSummary: One punchy sentence — what makes this property interesting (or not) for investment. Mention the asset type (lot, SFR, etc.) and the key reason for the score.`;

const userPrompt = (properties: RawProperty[]) => `
Score these ${properties.length} properties for wholesale potential. Each has address, price, size, condition signals, and distress indicators.

PROPERTIES:
${properties.map((p, i) => `
[${i}] ID: ${p.id}
  Address: ${p.address}, ${p.city}, ${p.state} ${p.zip}
  Price: $${p.price.toLocaleString()} | Type: ${p.propertyType} | ${p.bedrooms}bd/${p.bathrooms}ba | ${p.sqft} sqft | Built ${p.yearBuilt}
  Days on Market: ${p.daysOnMarket} | Price Reductions: ${p.priceReductions}
  Owner Type: ${p.ownerType ?? 'unknown'} | Distress Signals: ${p.distressSignals.length > 0 ? p.distressSignals.join(', ') : 'none'}
  Last Sold: ${p.lastSoldDate ?? 'unknown'} at $${(p.lastSoldPrice ?? 0).toLocaleString()}
  Tax Assessed Value: $${(p.taxAssessedValue ?? 0).toLocaleString()}
`).join('')}

Return JSON:
{
  "scores": [
    {
      "id": "property-id",
      "wholesaleScore": 78,
      "distressScore": 85,
      "momentumScore": 60,
      "sellerMotivation": 72,
      "arvEstimate": 185000,
      "arvConfidence": "medium",
      "repairEstimate": 25000,
      "scoreSummary": "Pre-foreclosure SFR priced 18% below MAO with absentee owner — strong assignment candidate."
    }
  ]
}
`;

// Pre-computed mock scores for when ANTHROPIC_API_KEY is absent
function mockScores(properties: RawProperty[]): { scores: Partial<ScoredProperty>[]; usage: TokenUsage } {
  const scores = properties.map((p, i) => {
    const distressCount = p.distressSignals.length;
    const hasDistress = distressCount > 0;
    const isHighDom = p.daysOnMarket > 60;
    const isAbsentee = p.ownerType === 'absentee' || p.ownerType === 'estate';
    const isLand = p.propertyType === 'Land';

    let arvEstimate: number;
    let repairEstimate: number;
    let wholesaleScore: number;
    let scoreSummary: string;

    if (isLand) {
      // Land: value is development potential, not renovation
      // Rough rule: a buildable infill lot is worth ~15-25% of finished home value
      // Reverse: lot value × 5-7 ≈ finished home value (ARV for land = post-build value)
      const lotMultiplier = 5 + (i % 3); // 5x, 6x, or 7x depending on location proxy
      arvEstimate = Math.round(p.price * lotMultiplier / 1000) * 1000;
      // Site prep + infrastructure for infill lot
      repairEstimate = 25000 + (i % 4) * 10000; // $25k–$55k
      const devSpread = arvEstimate - p.price - repairEstimate;
      const devRatio = devSpread / Math.max(1, p.price);

      const baseScore = devRatio > 3 ? 72 : devRatio > 1.5 ? 60 : devRatio > 0.5 ? 48 : 35;
      const domBonus = isHighDom ? 10 : 0; // motivated seller on land = opportunity
      wholesaleScore = Math.min(95, Math.max(15, baseScore + distressCount * 4 + domBonus));

      scoreSummary = devSpread > 0
        ? `Demo: Infill lot with ~$${Math.round(devSpread / 1000)}k development spread — verify zoning and utilities.`
        : `Demo: Land priced near development cost — negotiate down or pass.`;
    } else {
      // Residential: standard wholesale / fix-and-flip analysis
      // ARV: tax assessed values are typically ~78% of market value; divide to recover
      // implied market value, then add renovation premium by age.
      const assessedValue = p.taxAssessedValue ?? 0;
      const renovationPremium = p.yearBuilt < 1970 ? 0.22 : p.yearBuilt < 1990 ? 0.15 : 0.08;
      const impliedMarket = assessedValue > 0 ? assessedValue / 0.78 : p.price * (1 + renovationPremium);
      arvEstimate = Math.round(impliedMarket * (1 + renovationPremium) / 1000) * 1000;

      const agePool = p.yearBuilt < 1960
        ? [20000, 35000, 50000, 65000]
        : p.yearBuilt < 1985 ? [12000, 22000, 35000, 50000]
        : p.yearBuilt < 2000 ? [8000, 15000, 25000, 35000]
        : [5000, 10000, 18000, 25000];
      repairEstimate = agePool[(i * 7 + distressCount) % agePool.length] ?? 15000;

      const mao = Math.max(0, Math.round(arvEstimate * 0.70 - repairEstimate));
      const projectedProfit = mao - p.price;
      const profitRatio = projectedProfit / Math.max(1, p.price);

      const baseScore = profitRatio >= 0
        ? Math.min(90, 62 + Math.round(profitRatio * 60))
        : Math.max(12, 50 + Math.round(profitRatio * 80));

      wholesaleScore = Math.min(99, Math.max(10,
        baseScore + Math.min(20, distressCount * 6) + (isHighDom ? 7 : 0) + (isAbsentee ? 5 : 0)
      ));

      const prefix = wholesaleScore >= 75 ? 'Hot lead' : wholesaleScore >= 50 ? 'Worth investigating' : 'Needs negotiation';
      const profitStr = projectedProfit >= 0
        ? `~$${Math.round(projectedProfit / 1000)}k profit at list`
        : `$${Math.round(Math.abs(projectedProfit) / 1000)}k below MAO`;
      scoreSummary = `Demo: ${prefix} — ${profitStr}${distressCount > 0 ? ` · ${distressCount} distress signal${distressCount > 1 ? 's' : ''}` : ''}.`;
    }

    return {
      id: p.id,
      wholesaleScore,
      distressScore: Math.min(95, 15 + distressCount * 20 + (isHighDom ? 12 : 0)),
      momentumScore: 40 + (i % 6) * 8,
      sellerMotivation: Math.min(90, (hasDistress ? 52 : 20) + (isAbsentee ? 22 : 0) + (isHighDom ? 14 : 0)),
      arvEstimate,
      arvConfidence: (p.taxAssessedValue ?? 0) > 0 ? 'medium' as ArvConfidence : 'low' as ArvConfidence,
      repairEstimate,
      scoreSummary,
    };
  });
  return { scores, usage: { inputTokens: 0, outputTokens: 0 } };
}

export async function scorePropertiesWithClaude(
  properties: RawProperty[],
  apiKey: string | undefined,
): Promise<{ scores: Map<string, Partial<ScoredProperty>>; usage: TokenUsage }> {
  if (properties.length === 0) {
    return { scores: new Map(), usage: { inputTokens: 0, outputTokens: 0 } };
  }

  if (!apiKey) {
    const { scores, usage } = mockScores(properties);
    const map = new Map<string, Partial<ScoredProperty>>();
    for (const s of scores) {
      if (s.id) map.set(s.id, s);
    }
    return { scores: map, usage };
  }

  // Cap the per-request time and disable retries so a slow Claude call can't
  // hang the whole search. With maxRetries > 0 a 45s first attempt plus a retry
  // could exceed the route's 55s budget, timing out the WHOLE search before this
  // function's mock-score fallback ever runs. Keep this comfortably under that
  // budget and fall back to mock scores on any failure.
  const client = new Anthropic({ apiKey, timeout: 30_000, maxRetries: 0 });

  let response;
  try {
    response = await client.messages.create({
      // Haiku: ~3-4x cheaper than Sonnet. Wholesale scoring is a structured
      // JSON task it handles well, so credits last much longer.
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 4096,
      system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
      messages: [{ role: 'user', content: userPrompt(properties) }],
    });
  } catch (err) {
    console.warn('[scorer] Claude call failed — using mock scores:', err instanceof Error ? err.message : err);
    const { scores, usage: mockUsage } = mockScores(properties);
    const map = new Map<string, Partial<ScoredProperty>>();
    for (const s of scores) {
      if (s.id) map.set(s.id, s);
    }
    return { scores: map, usage: mockUsage };
  }

  const usage: TokenUsage = {
    inputTokens: response.usage.input_tokens,
    outputTokens: response.usage.output_tokens,
  };

  const text = response.content
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('');

  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    console.warn('[scorer] Claude returned no valid JSON — falling back to mock scores');
    const { scores, usage: mockUsage } = mockScores(properties);
    const map = new Map<string, Partial<ScoredProperty>>();
    for (const s of scores) {
      if (s.id) map.set(s.id, s);
    }
    return { scores: map, usage: mockUsage };
  }

  let raw = jsonMatch[0];
  let parsed: { scores: Array<Partial<ScoredProperty> & { id: string }> };

  try {
    parsed = JSON.parse(raw) as typeof parsed;
  } catch {
    // Salvage completed score objects before the truncation point
    const lastComplete = raw.lastIndexOf('},');
    if (lastComplete === -1) {
      const { scores, usage: mockUsage } = mockScores(properties);
      const map = new Map<string, Partial<ScoredProperty>>();
      for (const s of scores) {
        if (s.id) map.set(s.id, s);
      }
      return { scores: map, usage: mockUsage };
    }
    raw = raw.slice(0, lastComplete + 1) + ']}';
    parsed = JSON.parse(raw) as typeof parsed;
  }

  const map = new Map<string, Partial<ScoredProperty>>();
  for (const s of parsed.scores ?? []) {
    if (s.id) map.set(s.id, s);
  }

  return { scores: map, usage };
}
