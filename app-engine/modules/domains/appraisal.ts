import Anthropic from '@anthropic-ai/sdk';
import type { GeneratedCandidate } from './generate';
import { fetchNameBioComps, domainToKeyword, type NameBioResult } from './namebio';

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

const SYSTEM_PROMPT = `You are a domain valuation and liquidity analyst for a professional domain investor. For each domain, judge what an end-user buyer (a company that wants exactly this name) would realistically pay on the secondary market, and how likely it is to actually sell.

Rules:
- Output ONLY valid JSON. No prose, no markdown fences.
- "valueLow"/"valueMedian"/"valueHigh" are USD secondary-market estimates (what a buyer pays, not registration cost). Be realistic: most brandable names resell for $0-$2,500; strong exact-match commercial terms can reach $5k-$50k; be conservative.
- "sellability" 1-100: likelihood of an actual sale within ~24 months. High = clear end-user buyers and demand; low = speculative with no obvious buyer.
- "buyers": a short phrase naming who would buy it (e.g. "AI code-tooling startups").
- "reasoning": one concise sentence.
- A great name nobody will buy is worth little — weight real buyer demand heavily.`;

const userPrompt = (candidates: GeneratedCandidate[], comps?: Map<string, NameBioResult>) => `
Appraise these available domains. Each has the trend basis it came from.${comps && comps.size > 0 ? '\nReal historical sale comps are provided where available — anchor your value estimates to these.' : ''}

DOMAINS:
${candidates.map((c) => {
  const comp = comps?.get(c.domain.toLowerCase());
  const compNote = comp && comp.medianSalePrice
    ? ` [NameBio comps: median=${comp.medianSalePrice}, avg=${comp.avgSalePrice}, n=${comp.comps.length}]`
    : '';
  return `${c.domain} [strategy: ${c.strategy}; basis: ${c.basis || 'n/a'}]${compNote}`;
}).join('\n')}

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
  comps?: Map<string, NameBioResult>,
): Promise<Map<string, Omit<Appraisal, 'valueSource'>>> {
  const map = new Map<string, Omit<Appraisal, 'valueSource'>>();
  if (candidates.length === 0) return map;

  const client = new Anthropic({ apiKey });
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userPrompt(candidates, comps) }],
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
  return map;
}

// Appraises available candidates. GoDaddy GoValue supplies the headline number
// when configured; Claude always supplies sellability + buyer analysis and
// fills the value range when GoDaddy is unavailable. NameBio comps anchor
// Claude's estimates to real sale data when available.
export async function appraiseDomains(
  candidates: GeneratedCandidate[],
  env: {
    ANTHROPIC_API_KEY: string;
    GODADDY_API_KEY?: string;
    GODADDY_API_SECRET?: string;
    NAMEBIO_API_KEY?: string;
  },
): Promise<Appraisal[]> {
  if (candidates.length === 0) return [];

  const godaddy =
    env.GODADDY_API_KEY && env.GODADDY_API_SECRET
      ? { key: env.GODADDY_API_KEY, secret: env.GODADDY_API_SECRET }
      : null;

  // Fetch NameBio comps in parallel with GoDaddy (best-effort, failures ignored)
  const namebioComps = env.NAMEBIO_API_KEY
    ? await Promise.all(
        candidates.map(async (c) => {
          const result = await fetchNameBioComps(domainToKeyword(c.domain), env.NAMEBIO_API_KEY!);
          return [c.domain.toLowerCase(), result] as const;
        }),
      ).then((entries) =>
        new Map(entries.filter((e): e is [string, NameBioResult] => e[1] !== null)),
      )
    : new Map<string, NameBioResult>();

  const [claudeMap, godaddyValues] = await Promise.all([
    claudeAppraise(candidates, env.ANTHROPIC_API_KEY, namebioComps),
    godaddy
      ? Promise.all(
          candidates.map(async (c) => [c.domain, await godaddyAppraise(c.domain, godaddy)] as const),
        ).then((entries) => new Map(entries))
      : Promise.resolve(new Map<string, number | null>()),
  ]);

  return candidates.map((c) => {
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
}
