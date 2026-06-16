import Anthropic from '@anthropic-ai/sdk';
import type { RawSignal } from './sources/hackernews';

export type ScoredTrend = {
  name: string;
  velocity: 'rising' | 'peak' | 'declining';
  commercialScore: number; // 1-100
  sources: string[];
  keywords: string[];
  summary: string;
};

const SYSTEM_PROMPT = `You are a domain investing intelligence analyst. Your job is to find commercially valuable naming trends — specific named entities (companies, products, technologies, movements) that domain investors can act on NOW.

Rules:
- Output ONLY valid JSON — no prose, no markdown fences, no explanation.
- Return 15–25 trends maximum, ranked by commercialScore descending.
- "keywords" must be SPECIFIC: "Cursor IDE", "Pika Labs", "Synthesia AI" — NOT generic terms like "generative AI" or "machine learning".
- "velocity" reflects acceleration: rising = still climbing, peak = at max, declining = falling.
- "commercialScore" 1-100: will companies pay $1k–$50k for related domains? >70 = yes, 40-70 = maybe, <40 = unlikely.
- Cluster duplicates from different sources into one trend.
- Skip pure news events that won't generate ongoing search demand or company branding needs.`;

const USER_PROMPT = (signals: RawSignal[]) => `
Here are raw signals from multiple sources (Hacker News, Reddit, Product Hunt, GitHub Trending, YCombinator, Crunchbase, Google Trends). Analyze them for domain-investable naming trends.

SIGNALS (${signals.length} total):
${signals
  .slice(0, 200) // cap to avoid token overflow
  .map((s) => `[${s.source}] ${s.title}`)
  .join('\n')}

Return a JSON array of trend objects with this exact schema:
{
  "trends": [
    {
      "name": "Trend Name",
      "velocity": "rising",
      "commercialScore": 85,
      "sources": ["hackernews", "reddit/r/artificial"],
      "keywords": ["SpecificProduct1", "SpecificCompany2", "SpecificTech3"],
      "summary": "One sentence explaining why domains in this space are commercially valuable."
    }
  ]
}
`;

export async function scoreTrendsWithClaude(
  signals: RawSignal[],
  apiKey: string,
): Promise<ScoredTrend[]> {
  if (signals.length === 0) return [];

  const client = new Anthropic({ apiKey });

  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
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
  return (parsed.trends || []).sort((a, b) => b.commercialScore - a.commercialScore);
}
