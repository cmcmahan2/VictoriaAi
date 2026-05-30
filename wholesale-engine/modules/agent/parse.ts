import Anthropic from '@anthropic-ai/sdk';
import { getMockMarkets } from '../properties/mock';
import type { PropertyType } from '../properties/types';

// Structured criteria extracted from a wholesaler's plain-English buy-box.
export type ParsedBuyBox = {
  market: string | null;
  zipCodes: string[] | null;
  minPrice: number | null;
  maxPrice: number | null;
  minBedrooms: number | null;
  propertyTypes: PropertyType[];
  maxDaysOnMarket: number | null;
  requireDistressSignals: boolean;
  minScore: number | null;
  /** Minimum projected profit at list price the buyer will accept, in USD */
  minProfit: number | null;
  summary: string;
};

const PROPERTY_TYPES: PropertyType[] = ['SFR', 'MFR', 'Condo', 'Townhouse', 'Land'];

const SYSTEM_PROMPT = `You translate a real-estate wholesaler's plain-English buy-box description into structured search criteria. A "buy box" is the set of deal criteria an investor or developer is looking for.

Return ONLY valid JSON — no prose, no markdown fences. Use this exact shape:
{
  "market": "City, ST" or null,
  "zipCodes": ["38103"] or null,
  "minPrice": number or null,
  "maxPrice": number or null,
  "minBedrooms": number or null,
  "propertyTypes": ["SFR" | "MFR" | "Condo" | "Townhouse" | "Land"],
  "maxDaysOnMarket": number or null,
  "requireDistressSignals": boolean,
  "minScore": number (1-100) or null,
  "minProfit": number or null,
  "summary": "one short sentence restating the criteria in plain English"
}

Rules:
- "market" must be "City, ST" with a two-letter state code if a US city is named. If only ZIP codes are given, set market to null and fill zipCodes.
- Interpret money shorthand: "150k" = 150000, "$1.2M" = 1200000.
- "single family"/"houses"/"homes" -> "SFR"; "duplex"/"multifamily"/"multi-family"/"units" -> "MFR".
- "motivated sellers", "distressed", "pre-foreclosure", "vacant", "as-is", "needs work", "fixer", "estate sale", "absentee" -> requireDistressSignals: true.
- "hot deals"/"best deals"/"strong margin" -> minScore: 75. "good deals"/"worth looking at" -> minScore: 50.
- "X+ beds"/"at least X bedrooms" -> minBedrooms: X.
- Profit requirements like "$30k profit", "at least 25k margin", "spread of 40000" -> minProfit (in USD).
- Leave anything not mentioned as null (or [] for propertyTypes, false for requireDistressSignals).
- Always write a helpful one-sentence summary.`;

const userPrompt = (text: string) => `Known markets with rich data (prefer these spellings when the user names one): ${getMockMarkets().join('; ')}.

Buy-box description:
"""${text}"""

Return the JSON criteria.`;

function parseMoney(s: string): number {
  const m = s.replace(/[$,\s]/g, '');
  if (/m$/.test(m)) return Math.round(parseFloat(m) * 1_000_000);
  if (/k$/.test(m)) return Math.round(parseFloat(m) * 1_000);
  return Math.round(parseFloat(m));
}

// Lightweight fallback parser for when ANTHROPIC_API_KEY is absent.
export function fallbackParse(text: string): ParsedBuyBox {
  const t = text.toLowerCase();

  let maxPrice: number | null = null;
  const under = t.match(/(?:under|below|less than|max(?:imum)?|up to)\s*\$?\s*([\d.,]+\s*[mk]?)/);
  if (under) maxPrice = parseMoney(under[1]);

  let minPrice: number | null = null;
  const over = t.match(/(?:over|above|more than|min(?:imum)?|at least)\s*\$?\s*([\d.,]+\s*[mk]?)/);
  if (over && !/bed|bd|bath|profit|margin|spread/.test(over[0])) minPrice = parseMoney(over[1]);

  let minProfit: number | null = null;
  const profit = t.match(/\$?\s*([\d.,]+\s*[mk]?)\s*(?:\+)?\s*(?:in\s+)?(?:profit|margin|spread)/);
  if (profit) minProfit = parseMoney(profit[1]);

  let minBedrooms: number | null = null;
  const beds = t.match(/(\d+)\s*\+?\s*(?:bed|bd|br|bedroom)/);
  if (beds) minBedrooms = parseInt(beds[1], 10);

  const propertyTypes: PropertyType[] = [];
  if (/single.?family|\bsfr\b|\bhouse|\bhome/.test(t)) propertyTypes.push('SFR');
  if (/duplex|multi.?family|\bmfr\b|\bunits?\b|triplex|fourplex/.test(t)) propertyTypes.push('MFR');
  if (/condo/.test(t)) propertyTypes.push('Condo');
  if (/townhouse|townhome/.test(t)) propertyTypes.push('Townhouse');
  if (/\bland\b|\blot\b/.test(t)) propertyTypes.push('Land');

  const requireDistressSignals =
    /motivated|distress|pre.?foreclosure|foreclosure|vacant|as.?is|needs work|fixer|estate sale|absentee|tax lien|divorce/.test(t);

  let minScore: number | null = null;
  if (/hot deal|best deal|strong margin|great deal/.test(t)) minScore = 75;
  else if (/good deal|worth looking|decent deal/.test(t)) minScore = 50;

  const zipMatches = text.match(/\b\d{5}\b/g);
  const zipCodes = zipMatches && zipMatches.length > 0 ? zipMatches : null;

  let market: string | null = null;
  if (!zipCodes) {
    const known = getMockMarkets().find(m => t.includes(m.split(',')[0].toLowerCase()));
    if (known) market = known;
    else {
      const inMatch = text.match(/\bin\s+([A-Za-z .]+),\s*([A-Za-z]{2})\b/);
      if (inMatch) market = `${inMatch[1].trim()}, ${inMatch[2].toUpperCase()}`;
    }
  }

  const parts: string[] = [];
  if (minBedrooms) parts.push(`${minBedrooms}+ bed`);
  parts.push(propertyTypes.length ? propertyTypes.join('/') : 'properties');
  if (maxPrice) parts.push(`under $${maxPrice.toLocaleString()}`);
  if (minPrice) parts.push(`over $${minPrice.toLocaleString()}`);
  if (market) parts.push(`in ${market}`);
  else if (zipCodes) parts.push(`in ${zipCodes.join(', ')}`);
  if (requireDistressSignals) parts.push('with distress signals');
  if (minProfit) parts.push(`$${minProfit.toLocaleString()}+ profit`);
  if (minScore) parts.push(`scoring ${minScore}+`);

  return {
    market, zipCodes, minPrice, maxPrice, minBedrooms, propertyTypes,
    maxDaysOnMarket: null, requireDistressSignals, minScore, minProfit,
    summary: parts.join(' '),
  };
}

function sanitize(raw: Partial<ParsedBuyBox>): ParsedBuyBox {
  const types = Array.isArray(raw.propertyTypes)
    ? raw.propertyTypes.filter((t): t is PropertyType => PROPERTY_TYPES.includes(t as PropertyType))
    : [];
  return {
    market: typeof raw.market === 'string' && raw.market.trim() ? raw.market.trim() : null,
    zipCodes: Array.isArray(raw.zipCodes) && raw.zipCodes.length ? raw.zipCodes.map(String) : null,
    minPrice: typeof raw.minPrice === 'number' ? raw.minPrice : null,
    maxPrice: typeof raw.maxPrice === 'number' ? raw.maxPrice : null,
    minBedrooms: typeof raw.minBedrooms === 'number' ? raw.minBedrooms : null,
    propertyTypes: types,
    maxDaysOnMarket: typeof raw.maxDaysOnMarket === 'number' ? raw.maxDaysOnMarket : null,
    requireDistressSignals: raw.requireDistressSignals === true,
    minScore: typeof raw.minScore === 'number' ? raw.minScore : null,
    minProfit: typeof raw.minProfit === 'number' ? raw.minProfit : null,
    summary: typeof raw.summary === 'string' ? raw.summary : '',
  };
}

/**
 * Turns a plain-English buy-box into structured criteria. Uses Claude when an
 * API key is available, otherwise a regex/keyword fallback so it still works
 * in demo mode.
 */
export async function parseBuyBox(
  text: string,
  apiKey: string | undefined,
): Promise<{ parsed: ParsedBuyBox; usedAi: boolean }> {
  if (!apiKey) return { parsed: fallbackParse(text), usedAi: false };

  try {
    const client = new Anthropic({ apiKey });
    const response = await client.messages.create({
      // Haiku: cheap and fast for parsing a short buy-box description into JSON.
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 512,
      system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
      messages: [{ role: 'user', content: userPrompt(text) }],
    });

    const out = response.content.filter(b => b.type === 'text').map(b => b.text).join('');
    const match = out.match(/\{[\s\S]*\}/);
    if (!match) return { parsed: fallbackParse(text), usedAi: false };

    return { parsed: sanitize(JSON.parse(match[0]) as Partial<ParsedBuyBox>), usedAi: true };
  } catch {
    return { parsed: fallbackParse(text), usedAi: false };
  }
}
