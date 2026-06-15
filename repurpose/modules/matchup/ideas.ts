import Anthropic from '@anthropic-ai/sdk';

// A single debate idea the user can pick from the welcome screen.
export type MatchupIdea = {
  matchup: string;      // "Michael Jordan vs LeBron James"
  sport: string;        // "Basketball"
  angle: string;        // the debate framing / what makes it spicy
  viralReason: string;  // why this one pops off
};

const MODEL = 'claude-sonnet-4-6';

const SYSTEM_PROMPT = `You are a viral sports-debate content strategist for a faceless YouTube Shorts channel. You generate spicy, CONTROVERSIAL "who's better" matchup ideas that blow up the comment section and force people to vote.

Rules:
- Output ONLY valid JSON — no prose, no markdown fences.
- Cross-sport and cross-era are encouraged (basketball, football, soccer, baseball, boxing, tennis, etc.).
- Each matchup must be TWO specific, real, widely-known athletes — the kind casual fans have strong opinions about.
- HEAVILY favor AGE-ANCHORED and PRIME-VS-PRIME framings, because they are the most debatable (career comparisons are too "settled"). Examples of the vibe:
  - "LeBron James at 22 vs Victor Wembanyama at 22"
  - "Rookie Michael Jordan vs Rookie Kobe Bryant"
  - "Prime Shaq vs Prime Joel Embiid"
  - "Messi at 25 vs Kylian Mbappé at 25"
  - "2009 LeBron vs 1989 Michael Jordan"
- When using an age/season anchor, put the SAME anchor on both players (both "at 22", both "rookie year", both "in their prime").
- Prioritize debates that are genuinely close and divisive — where smart fans land on opposite sides.
- "angle" = the specific framing that sparks the argument (e.g. "same age, who was further along", "hype vs proven").
- "viralReason" = one sentence on why this triggers comments/votes.
- Keep it about on-field greatness. No personal-life controversy or anything defamatory.`;

function buildUserPrompt(opts: { count: number; sportFilter?: string | null; theme?: string | null }): string {
  const lines = [`Generate ${opts.count} sports debate matchup ideas for Shorts.`];
  if (opts.sportFilter) lines.push(`Focus on this sport: ${opts.sportFilter}.`);
  if (opts.theme) lines.push(`Lean into this theme/era if possible: ${opts.theme}.`);
  lines.push(`Return JSON of this exact shape:
{
  "ideas": [
    { "matchup": "Player A vs Player B", "sport": "Basketball", "angle": "...", "viralReason": "..." }
  ]
}`);
  return lines.join('\n');
}

// Lenient JSON extraction shared with the rest of the matchup engine.
export function extractJson<T>(raw: string): T {
  const match = raw.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('No JSON object found in Claude response');
  let text = match[0];
  try {
    return JSON.parse(text) as T;
  } catch {
    // Truncation recovery: cut to the last complete element and close braces.
    const lastBrace = text.lastIndexOf('}');
    if (lastBrace > 0) {
      text = text.slice(0, lastBrace + 1);
      // Balance any open array/object from the truncation.
      const open = (text.match(/\[/g) || []).length;
      const close = (text.match(/\]/g) || []).length;
      if (open > close) text += ']'.repeat(open - close);
      text += '}'.repeat(Math.max(0, (text.match(/\{/g) || []).length - (text.match(/\}/g) || []).length));
      return JSON.parse(text) as T;
    }
    throw new Error('Claude returned malformed JSON for matchup ideas');
  }
}

export async function generateMatchupIdeas(
  opts: { count?: number; sportFilter?: string | null; theme?: string | null } = {},
  apiKey?: string,
): Promise<MatchupIdea[]> {
  const key = apiKey || process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error('ANTHROPIC_API_KEY is required');

  const client = new Anthropic({ apiKey: key });
  const count = opts.count ?? 8;

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 1500,
    system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
    messages: [{ role: 'user', content: buildUserPrompt({ count, sportFilter: opts.sportFilter, theme: opts.theme }) }],
  });

  const text = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('');

  const parsed = extractJson<{ ideas: MatchupIdea[] }>(text);
  return Array.isArray(parsed.ideas) ? parsed.ideas : [];
}
