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
const SYSTEM_PROMPT = `You are a wholesale real estate analyst. Your job is to score residential properties for wholesale investment potential — finding deals where an investor can acquire below market value, assign the contract, or flip for profit.

Scoring dimensions:
1. wholesaleScore (1-100): Overall wholesale deal quality. 75+ = strong deal worth pursuing immediately. 50-74 = worth investigating. Below 50 = weak or overpriced.
2. distressScore (1-100): Severity of seller distress and property distress signals. Pre-foreclosure, tax liens, probate/estate, divorce, long vacancy, high days-on-market, price reductions all increase this score.
3. momentumScore (1-100): Market momentum in this zip code / neighborhood. Rising prices, high investor activity, recent flip comps selling above ARV increase this score. Declining markets score lower.
4. sellerMotivation (1-100): Probability that the seller is motivated enough to accept a below-market offer. Absentee owner + distress signals = high motivation. Owner-occupied with no distress = low motivation.

Financial estimates:
- arvEstimate: After Repair Value in USD — what the property would sell for fully renovated to neighborhood standards. Base this on the property's zip code, size (sqft), bedrooms, bathrooms, year built, and property type.
- arvConfidence: "high" if you have high confidence in the estimate (strong comps context), "medium" if moderate, "low" if limited data (use low when no real comps are available).
- repairEstimate: Estimated cost to bring property to ARV condition, in USD. Base on year built, property type, and size. Deferred maintenance signals increase this. Typical range: $15,000 (light cosmetic) to $80,000 (full gut rehab).

Rules:
- Output ONLY valid JSON — no prose, no markdown fences, no explanation outside the JSON structure.
- Be realistic and conservative with ARV estimates — overestimating ARV destroys wholesale deals.
- wholesaleScore should directly reflect whether this is a viable wholesale deal, NOT just how distressed the property is.
- A property with a $200k ARV asking $180k is NOT a wholesale deal even if distressed.
- The classic 70% rule: MAO = ARV × 0.70 − repair estimate. If asking price is near or above MAO, wholesaleScore should be below 50.
- scoreSummary: One punchy sentence explaining the score — specifically what makes this property interesting (or not) for wholesale.`;

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
    const hasDistress = p.distressSignals.length > 0;
    const isHighDom = p.daysOnMarket > 60;
    const isAbsentee = p.ownerType === 'absentee' || p.ownerType === 'estate';
    const taxBase = p.taxAssessedValue ?? p.price;
    const arvEstimate = Math.round(Math.max(taxBase * 1.15, p.price * 0.95) / 1000) * 1000;
    const repairEstimate = p.yearBuilt < 1970 ? 45000 : p.yearBuilt < 1990 ? 25000 : 15000;
    const mao = Math.max(0, Math.round(arvEstimate * 0.70 - repairEstimate));
    const equitySpread = arvEstimate - p.price;
    const projectedProfit = mao - p.price;

    const baseScore = projectedProfit > 0
      ? 60 + Math.min(30, Math.round(projectedProfit / 2000))
      : 20 + Math.max(0, Math.round((projectedProfit + 30000) / 1000));

    const distressBonus = p.distressSignals.length * 5;
    const domBonus = isHighDom ? 8 : 0;
    const wholesaleScore = Math.min(99, Math.max(5, baseScore + distressBonus + domBonus - (i % 3 === 0 ? 10 : 0)));

    return {
      id: p.id,
      wholesaleScore,
      distressScore: Math.min(95, 20 + p.distressSignals.length * 18 + (isHighDom ? 15 : 0)),
      momentumScore: 45 + (i % 5) * 8,
      sellerMotivation: Math.min(90, (hasDistress ? 55 : 25) + (isAbsentee ? 20 : 0) + (isHighDom ? 15 : 0)),
      arvEstimate,
      arvConfidence: 'low' as ArvConfidence,
      repairEstimate,
      scoreSummary: projectedProfit > 0
        ? `Mock score: ${p.distressSignals.length > 0 ? 'Distressed' : 'Standard'} property with ~$${Math.round(projectedProfit / 1000)}k projected profit at list price.`
        : `Mock score: Asking price exceeds MAO by $${Math.round(Math.abs(projectedProfit) / 1000)}k — needs price reduction to work as a wholesale deal.`,
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

  // Cap the per-request time and retries so a slow Claude call can't hang the
  // whole search — fall back to mock scores instead of timing out the route.
  const client = new Anthropic({ apiKey, timeout: 45_000, maxRetries: 1 });

  let response;
  try {
    response = await client.messages.create({
      model: 'claude-sonnet-4-6',
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
