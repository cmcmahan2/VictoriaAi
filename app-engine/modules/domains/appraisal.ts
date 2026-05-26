import Anthropic from '@anthropic-ai/sdk';
import type { TokenUsage } from '../trends/claude-scorer';
import type { GeneratedCandidate } from './generate';

export type Appraisal = {
  domain: string;
  valueLow: number;
  valueMedian: number;
  valueHigh: number;
  valueSource: 'godaddy' | 'claude';
  sellability: number; // 1-100: likelihood an end-user buyer pays for it
  buyers: string;      // who would plausibly buy it
  reasoning: string;   // one-line justification
};

// --- GoDaddy GoValue -------------------------------------------------------

type GodaddyCreds = { key: string; secret: string };

async function godaddyAppraise(
  domain: string,
  creds: GodaddyCreds,
): Promise<number | null> {
  try {
    const res = await fetch(`https://api.godaddy.com/v1/appraisal/${encodeURIComponent(domain)}`, {
      headers: {
        Authorization: `sso-key ${creds.key}:${creds.secret}`,
        Accept: 'application/json',
      },
      cache: 'no-store',
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { govalue?: number };
    return typeof data.govalue === 'number' ? data.govalue : null;
  } catch {
    return null;
  }
}

// --- Claude sellability + value range --------------------------------------
// One batched call covers all available domains. It always returns sellability
// + buyer profile (the "will it actually sell" judgment), and supplies a value
// range too — used directly when GoDaddy is unavailable, or as a sanity layer.

const SYSTEM_PROMPT = `You are a domain valuation analyst for a professional domain investor. For each domain, judge what an end-user buyer would pay and how desirable the name is to companies and startups.

Rules:
- Output ONLY valid JSON. No prose, no markdown fences.
- "valueLow"/"valueMedian"/"valueHigh" are USD secondary-market estimates. Brandable trend-aligned names: $500–$5k; strong exact-match commercial keywords: $5k–$50k.
- "sellability" 1-100: how desirable is this name to a startup or company building in this space? 70+ = strong brand fit, clear buyer pool; 50-69 = decent, some buyers; below 50 = niche or weak.
- Score generously for names that are: short (under 10 chars), pronounceable, trend-aligned, or match a real product category.
- "buyers": a short phrase naming who would buy it (e.g. "AI code-tooling startups").
- "reasoning": one concise sentence.`;

const userPrompt = (candidates: GeneratedCandidate[]) => `
Appraise these available domains. Each has the trend basis it came from.

DOMAINS:
${candidates.map((c) => `${c.domain} [strategy: ${c.strategy}; basis: ${c.basis || 'n/a'}]`).join('\n')}

Return JSON:
{
  "appraisals": [
    {
      "domain": "cursorflow.com",
      "valueLow": 300,
      "valueMedian": 900,
      "valueHigh": 2500,
      "sellability": 62,
      "buyers": "AI dev-tool startups",
      "reasoning": "Brandable compound tied to a hot IDE trend with plausible startup buyers."
    }
  ]
}
`;

async function claudeAppraise(
  candidates: GeneratedCandidate[],
  apiKey: string,
): Promise<{ map: Map<string, Omit<Appraisal, 'valueSource'>>; usage: TokenUsage }> {
  const map = new Map<string, Omit<Appraisal, 'valueSource'>>();
  if (candidates.length === 0) return { map, usage: { inputTokens: 0, outputTokens: 0 } };

  const client = new Anthropic({ apiKey });
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 8192,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userPrompt(candidates) }],
  });

  const text = response.content
    .filter((b) => b.type === 'text')
    .map((b) => (b as { text: string }).text)
    .join('');

  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error('Claude returned no valid JSON for appraisal');

  const parsed = JSON.parse(jsonMatch[0]) as {
    appraisals: (Omit<Appraisal, 'valueSource'>)[];
  };

  for (const a of parsed.appraisals || []) {
    if (a.domain) map.set(a.domain.toLowerCase(), a);
  }
  return {
    map,
    usage: { inputTokens: response.usage.input_tokens, outputTokens: response.usage.output_tokens },
  };
}

// Appraises available candidates. GoDaddy GoValue supplies the headline number
// when configured; Claude always supplies sellability + buyer analysis and
// fills the value range when GoDaddy is unavailable.
export async function appraiseDomains(
  candidates: GeneratedCandidate[],
  env: { ANTHROPIC_API_KEY: string; GODADDY_API_KEY?: string; GODADDY_API_SECRET?: string },
): Promise<{ appraisals: Appraisal[]; usage: TokenUsage }> {
  if (candidates.length === 0) return { appraisals: [], usage: { inputTokens: 0, outputTokens: 0 } };

  const godaddy =
    env.GODADDY_API_KEY && env.GODADDY_API_SECRET
      ? { key: env.GODADDY_API_KEY, secret: env.GODADDY_API_SECRET }
      : null;

  const [{ map: claudeMap, usage }, godaddyValues] = await Promise.all([
    claudeAppraise(candidates, env.ANTHROPIC_API_KEY),
    godaddy
      ? Promise.all(
          candidates.map(async (c) => [c.domain, await godaddyAppraise(c.domain, godaddy)] as const),
        ).then((entries) => new Map(entries))
      : Promise.resolve(new Map<string, number | null>()),
  ]);

  const appraisals = candidates.map((c) => {
    const claude = claudeMap.get(c.domain);
    const gv = godaddyValues.get(c.domain) ?? null;

    // Fallbacks keep the pipeline producing a row even if a layer is missing.
    const base = claude ?? {
      domain: c.domain,
      valueLow: 100,
      valueMedian: 300,
      valueHigh: 800,
      sellability: 30,
      buyers: 'unknown',
      reasoning: 'No appraisal returned; default conservative estimate.',
    };

    if (gv != null) {
      return {
        domain: c.domain,
        valueLow: Math.round(gv * 0.5),
        valueMedian: gv,
        valueHigh: Math.round(gv * 2),
        valueSource: 'godaddy' as const,
        sellability: base.sellability,
        buyers: base.buyers,
        reasoning: base.reasoning,
      };
    }

    return { ...base, domain: c.domain, valueSource: 'claude' as const };
  });

  return { appraisals, usage };
}
