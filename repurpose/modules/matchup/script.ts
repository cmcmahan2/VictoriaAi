import Anthropic from '@anthropic-ai/sdk';
import { extractJson } from './ideas';

// A player's side of the comparison.
export type PlayerProfile = {
  name: string;          // display name, e.g. "LeBron James"
  oneLiner: string;      // short identity, e.g. "4x champion, all-time scoring leader"
  accolades: string[];   // bullet highlights (titles, MVPs, records)
  wikiTitle: string;     // best-guess Wikipedia/Wikimedia page title for photo lookup
};

// One row of the head-to-head stat card. Values are strings so we can show
// "6" or "32.4 PPG" or "—". `edge` marks who wins that row.
export type StatRow = {
  label: string;         // "Championships"
  a: string;             // player A value
  b: string;             // player B value
  edge: 'A' | 'B' | 'EVEN';
};

// The full plan that downstream phases (graphics, voice, assembly) consume.
export type MatchupPlan = {
  matchup: string;       // "Michael Jordan vs LeBron James"
  sport: string;
  playerA: PlayerProfile;
  playerB: PlayerProfile;
  statRows: StatRow[];
  hook: string;          // scroll-stopping opening line
  narration: string[];   // ordered narration beats (also used for captions)
  verdict: string;       // closing line that drives the vote
  youtube: {
    title: string;
    description: string;
    tags: string[];
    hashtags: string[];
  };
  // Surfaced so the user knows numbers are AI-generated and should be sanity-checked.
  statsDisclaimer: string;
};

const MODEL = 'claude-sonnet-4-6';

const SYSTEM_PROMPT = `You are the writing and research engine for a faceless sports-debate YouTube Shorts channel. Given a matchup of two real athletes, you produce a complete, ready-to-produce debate plan.

Rules:
- Output ONLY valid JSON — no prose, no markdown fences.
- Be ACCURATE with stats and accolades to the best of your knowledge. Use widely-accepted career numbers. If unsure of an exact figure, give the commonly-cited value and keep it plausible — never invent fake records.
- "statRows": 5-7 rows of the most argument-relevant head-to-head stats for THIS sport (e.g. basketball: championships, MVPs, PPG, All-Star selections, scoring titles). Mark "edge" honestly per row.
- "narration": 5-9 short spoken beats (one sentence each) that flow as a 30-45 second voiceover. Beat 1 = the hook. Build the case for each side fairly, then tee up the vote. Conversational, punchy, no fluff.
- "verdict": a closing line that explicitly asks viewers to vote in the comments (e.g. "Drop a 1 for Jordan, a 2 for LeBron 👇").
- "wikiTitle": your best guess at the athlete's Wikipedia article title (usually their full name) for photo lookup.
- "youtube.title": <=100 chars, debate-forward. "youtube.tags": 10-15 search tags (no '#'). "youtube.hashtags": 3-5 incl. "#Shorts".
- Keep it about on-field/on-court greatness. No personal-life controversy.
- Always fill "statsDisclaimer" with a brief reminder that stats are AI-generated and should be verified before publishing.`;

function buildUserPrompt(matchup: string): string {
  return `Create the full debate plan for this matchup: "${matchup}".

Return JSON of this exact shape:
{
  "matchup": "Player A vs Player B",
  "sport": "Basketball",
  "playerA": { "name": "...", "oneLiner": "...", "accolades": ["..."], "wikiTitle": "..." },
  "playerB": { "name": "...", "oneLiner": "...", "accolades": ["..."], "wikiTitle": "..." },
  "statRows": [ { "label": "Championships", "a": "6", "b": "4", "edge": "A" } ],
  "hook": "...",
  "narration": ["...", "..."],
  "verdict": "...",
  "youtube": { "title": "...", "description": "...", "tags": ["..."], "hashtags": ["#Shorts", "..."] },
  "statsDisclaimer": "..."
}`;
}

function normalizePlan(plan: MatchupPlan): MatchupPlan {
  // Guard #Shorts and basic shape so downstream phases never choke.
  const hashtags = Array.isArray(plan.youtube?.hashtags) ? plan.youtube.hashtags : [];
  if (!hashtags.some((h) => h.toLowerCase() === '#shorts')) hashtags.unshift('#Shorts');
  return {
    ...plan,
    statRows: Array.isArray(plan.statRows) ? plan.statRows : [],
    narration: Array.isArray(plan.narration) ? plan.narration : [],
    youtube: {
      title: plan.youtube?.title || plan.matchup,
      description: plan.youtube?.description || '',
      tags: Array.isArray(plan.youtube?.tags) ? plan.youtube.tags : [],
      hashtags,
    },
    statsDisclaimer:
      plan.statsDisclaimer || 'Stats are AI-generated — double-check them before publishing.',
  };
}

export async function generateMatchupPlan(matchup: string, apiKey?: string): Promise<MatchupPlan> {
  const key = apiKey || process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error('ANTHROPIC_API_KEY is required');
  if (!matchup?.trim()) throw new Error('A matchup is required');

  const client = new Anthropic({ apiKey: key });

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 2500,
    system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
    messages: [{ role: 'user', content: buildUserPrompt(matchup.trim()) }],
  });

  const text = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('');

  return normalizePlan(extractJson<MatchupPlan>(text));
}
