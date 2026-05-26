import Anthropic from '@anthropic-ai/sdk';
import type { RawSignal } from './sources/hackernews';

export type ScoredTrend = {
  name: string;
  velocity: 'rising' | 'peak' | 'declining';
  commercialScore: number; // 1-100
  demand: number;          // 1-100: how many buyers exist / how easy to sell
  category?: string;       // broad vertical, e.g. "fitness", "fintech"
  sources: string[];
  keywords: string[];
  summary: string;
};

const SYSTEM_PROMPT = `You are a domain investing intelligence analyst. Your job is to find commercially valuable naming trends that domain investors can act on NOW. Cast a WIDE net across the whole economy — do NOT restrict yourself to AI or tech.

Cover ALL commercial categories where domains sell, for example:
- Tech & startups (SaaS, AI, crypto, dev tools)
- Health, wellness, fitness, supplements, mental health
- Personal finance, fintech, investing, side hustles
- E-commerce, DTC consumer products, retail niches
- Food, beverage, restaurants, recipes
- Home, garden, real estate, DIY, home services
- Travel, hospitality, local services
- Beauty, fashion, skincare, lifestyle
- Pets, parenting, education, hobbies, gaming
- Sustainability, energy, outdoor

Two kinds of trends are valuable, include BOTH:
1. SPECIFIC trends — named entities, products, or rising niches with real momentum (e.g. "Cursor IDE", "GLP-1 weight loss", "pickleball gear").
2. EVERGREEN high-demand naming themes — broad, timeless commercial concepts and word/phrase patterns that consistently attract buyers (e.g. "AI + everyday service", "two-word brandable consumer goods", "[city] + service", short single dictionary words). These sell easily because demand is constant and many buyers exist.

Rules:
- Output ONLY valid JSON — no prose, no markdown fences, no explanation.
- Return 18–28 trends maximum, ranked by commercialScore descending.
- Aim for VARIETY across categories — do not return a list that is mostly tech/AI. At most ~40% of trends should be tech/AI.
- "keywords" must be concrete and usable for generating domain names: specific products/companies, OR strong commercial words and short phrases (e.g. "trail", "ledger", "bloom", "hydrate", "freelance"). Avoid vague academic terms like "machine learning".
- "velocity" reflects acceleration: rising = still climbing, peak = at max, declining = falling. Evergreen themes are "peak".
- "commercialScore" 1-100: will companies/founders pay $1k–$50k for related domains? >70 = yes, 40-70 = maybe, <40 = unlikely.
- "demand" 1-100: how MANY potential buyers exist and how EASY the names are to sell (liquidity). Broad consumer categories with many small businesses = high demand; narrow niches = low. This is distinct from price — a cheap name with thousands of buyers can have very high demand.
- Cluster duplicates from different sources into one trend.
- Skip pure news events (deaths, politics, sports scores) that won't generate ongoing branding or business demand.`;

const USER_PROMPT = (signals: RawSignal[]) => `
Here are raw signals from many sources (Hacker News, Reddit across diverse verticals, Product Hunt, GitHub, YCombinator, Crunchbase, Google Trends, Wikipedia most-read). Analyze them for domain-investable naming trends across the WHOLE economy, not just tech.

SIGNALS (${signals.length} shown):
${interleaveBySource(signals, 240)
  .map((s) => `[${s.source}] ${s.title}`)
  .join('\n')}

Return a JSON array of trend objects with this exact schema:
{
  "trends": [
    {
      "name": "Trend Name",
      "velocity": "rising",
      "commercialScore": 85,
      "demand": 72,
      "category": "fitness",
      "sources": ["reddit/r/fitness", "google-trends"],
      "keywords": ["recoveryband", "mobility", "coldplunge"],
      "summary": "One sentence on why domains here are commercially valuable and who buys them."
    }
  ]
}
`;

// Round-robin across sources so a high-volume source (e.g. Reddit) can't crowd
// out smaller broad sources (Wikipedia, Google Trends) before the cap.
function interleaveBySource(signals: RawSignal[], cap: number): RawSignal[] {
  const bySource = new Map<string, RawSignal[]>();
  for (const s of signals) {
    const key = s.source.split('/')[0];
    if (!bySource.has(key)) bySource.set(key, []);
    bySource.get(key)!.push(s);
  }
  const queues = [...bySource.values()];
  const out: RawSignal[] = [];
  let added = true;
  while (out.length < cap && added) {
    added = false;
    for (const q of queues) {
      const next = q.shift();
      if (next) {
        out.push(next);
        added = true;
        if (out.length >= cap) break;
      }
    }
  }
  return out;
}

export async function scoreTrendsWithClaude(
  signals: RawSignal[],
  apiKey: string,
): Promise<ScoredTrend[]> {
  if (signals.length === 0) return [];

  const client = new Anthropic({ apiKey });

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: USER_PROMPT(signals) }],
  });

  const text = response.content
    .filter((b) => b.type === 'text')
    .map((b) => b.text)
    .join('');

  // Extract JSON even if Claude adds any surrounding text
  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error('Claude returned no valid JSON');
  }

  const parsed = JSON.parse(jsonMatch[0]) as { trends: ScoredTrend[] };
  return (parsed.trends || [])
    .map((t) => ({ ...t, demand: typeof t.demand === 'number' ? t.demand : 50 }))
    .sort((a, b) => b.commercialScore - a.commercialScore);
}
