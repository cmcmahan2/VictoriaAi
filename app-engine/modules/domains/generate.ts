import Anthropic from '@anthropic-ai/sdk';
import type { ScoredTrend } from '../trends/claude-scorer';

export type GeneratedCandidate = {
  domain: string;      // full domain, lowercase, e.g. "cursorflow.com"
  sld: string;         // second-level label, e.g. "cursorflow"
  tld: string;         // e.g. "com"
  strategy: string;    // 'exact-match' | 'brandable' | 'compound' | 'keyword-suffix'
  basis: string;       // the trend/keyword this came from
};

// TLDs we generate for, in priority order. RDAP coverage is good for all of these.
export const TARGET_TLDS = ['com', 'io', 'ai', 'co'] as const;

const SYSTEM_PROMPT = `You are a domain name generator for a professional domain investor. Given commercially valuable naming trends, you invent concrete, registerable domain names that an end-user company would plausibly pay to acquire.

Rules:
- Output ONLY valid JSON. No prose, no markdown fences.
- Each domain must be a real, typeable second-level label: lowercase letters and digits only, no hyphens, no spaces, 3-20 characters.
- Use these strategies, mixed:
  - "exact-match": the trend keyword itself as a domain (e.g. a product/tech name).
  - "brandable": invented, pronounceable, memorable coinages evoking the trend.
  - "compound": two real words joined (e.g. "trendforge", "signalbase").
  - "keyword-suffix": trend keyword + a commercial suffix (ai, hq, app, labs, hub, flow, base, kit).
- Favor names that sound like a real startup or product, not keyword spam.
- Do NOT include the TLD in the "sld" field — only the label.
- Prefer short, brandable .com-worthy names.`;

const USER_PROMPT = (trends: ScoredTrend[], perTrend: number) => `
Generate domain name candidates from these ranked naming trends. For EACH trend, produce ${perTrend} strong second-level labels using a mix of the strategies. Higher-ranked trends deserve your best names.

TRENDS:
${trends
  .map(
    (t, i) =>
      `${i + 1}. ${t.name} (score ${t.commercialScore}) — keywords: ${t.keywords.slice(0, 6).join(', ')}`,
  )
  .join('\n')}

Return JSON with this exact schema:
{
  "candidates": [
    { "sld": "cursorflow", "strategy": "compound", "basis": "Cursor IDE" }
  ]
}
`;

function sanitizeSld(raw: string): string | null {
  const s = (raw || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  if (s.length < 3 || s.length > 20) return null;
  return s;
}

// Generates a deduplicated list of full-domain candidates across TARGET_TLDS.
export async function generateDomainCandidates(
  trends: ScoredTrend[],
  apiKey: string,
  opts: { perTrend?: number; maxTotal?: number } = {},
): Promise<GeneratedCandidate[]> {
  const perTrend = opts.perTrend ?? 8;
  const maxTotal = opts.maxTotal ?? 160;
  if (trends.length === 0) return [];

  const client = new Anthropic({ apiKey });

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: USER_PROMPT(trends, perTrend) }],
  });

  const text = response.content
    .filter((b) => b.type === 'text')
    .map((b) => (b as { text: string }).text)
    .join('');

  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error('Claude returned no valid JSON for domain generation');

  const parsed = JSON.parse(jsonMatch[0]) as {
    candidates: { sld: string; strategy: string; basis: string }[];
  };

  // Expand each label across TLDs (exact-match labels favor .com first only to
  // avoid flooding), dedupe by full domain, and cap the total.
  const seen = new Set<string>();
  const out: GeneratedCandidate[] = [];

  for (const c of parsed.candidates || []) {
    const sld = sanitizeSld(c.sld);
    if (!sld) continue;

    // .com first always — it commands 5-10x higher resale prices than other TLDs.
    // Exact-match stays .com only; brandable/compound get .com + .io as secondary.
    const tlds =
      c.strategy === 'exact-match'
        ? (['com'] as const)
        : (['com', 'io'] as const);

    for (const tld of tlds) {
      const domain = `${sld}.${tld}`;
      if (seen.has(domain)) continue;
      seen.add(domain);
      out.push({
        domain,
        sld,
        tld,
        strategy: c.strategy || 'brandable',
        basis: c.basis || '',
      });
      if (out.length >= maxTotal) return out;
    }
  }

  return out;
}
