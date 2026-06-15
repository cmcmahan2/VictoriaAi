import Anthropic from '@anthropic-ai/sdk';
import { extractJson } from './ideas';

// A player's identity for the comparison.
export type PlayerProfile = {
  name: string;          // display name, e.g. "LeBron James"
  oneLiner: string;      // short identity, e.g. "4x champion, all-time scoring leader"
  wikiTitle: string;     // best-guess Wikipedia/Wikimedia page title for photo lookup
};

// One row of the head-to-head stat card. Values are strings so we can show
// "6" or "32.4" or "—". `edge` marks who wins that row.
export type StatRow = {
  label: string;         // "Championships"
  a: string;             // player A value (short)
  b: string;             // player B value (short)
  edge: 'A' | 'B' | 'EVEN';
};

export type SceneKind = 'awards' | 'teams' | 'coaches' | 'teammates' | 'competition' | 'stats';

// One comparison section of the mini-doc. For list scenes, aItems/bItems hold
// the bullets per player; the 'stats' scene renders statRows instead.
export type ComparisonScene = {
  kind: SceneKind;
  title: string;         // "AWARDS", "TEAMS", "BY THE NUMBERS"
  aItems: string[];      // player A bullets (empty for 'stats')
  bItems: string[];      // player B bullets (empty for 'stats')
  narration: string;     // the voiceover line for this section
};

// The full plan that downstream phases (graphics, voice, assembly) consume.
export type MatchupPlan = {
  matchup: string;       // "Michael Jordan vs LeBron James"
  sport: string;
  playerA: PlayerProfile;
  playerB: PlayerProfile;
  statRows: StatRow[];   // for the 'stats' scene
  hook: string;          // intro narration (scroll-stopper)
  scenes: ComparisonScene[]; // ordered comparison sections
  verdict: string;       // closing narration that drives the vote
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

const SYSTEM_PROMPT = `You are the writing and research engine for a faceless sports-debate YouTube Shorts channel. Given a matchup of two real athletes, you produce a complete, multi-dimensional debate plan — not just stats, but the full case: awards, teams, coaches, star teammates, and the competition/era each player faced.

Rules:
- Output ONLY valid JSON — no prose, no markdown fences.
- SNAPSHOT / AGE ANCHOR (very important): if the matchup specifies a moment — "at 22", "rookie", "rookie year", "in their prime", "through age 25", "2009 LeBron", etc. — then EVERY stat, award, team, coach, teammate, and the narration must reflect ONLY that snapshot in time, NOT career totals. E.g. "LeBron at 22 vs Wemby at 22" compares each player up through their age-22 season only. Make this explicit in the labels (e.g. "Titles by 22", "PPG at 22", "MVPs by 22"). If a player is young/ongoing and hadn't reached that point yet, say so honestly rather than inventing numbers.
- Be ACCURATE to the best of your knowledge. Use widely-accepted facts. If unsure of an exact figure, give the commonly-cited value — never invent fake records, fake teams, or fake teammates.
- "playerA"/"playerB": "name" must be the CLEAN player name only (e.g. "LeBron James", NOT "LeBron at 22"). Put the age/snapshot framing in "oneLiner" instead. "wikiTitle" = your best guess at their Wikipedia article title for photo lookup.
- "statRows": exactly 5-6 head-to-head stats for THIS sport. Each "a"/"b" value must be SHORT — a single number/token, max ~7 chars (e.g. "6", "30.1", "38,652"). Put units/context in "label" (max ~16 chars, e.g. "Career PPG"). One stat per row, never combine with a slash. Mark "edge" honestly.
- "scenes": an ORDERED array of comparison sections. Include these kinds when they apply, in this order: "awards", "teams", "coaches", "teammates", "competition", then "stats" LAST. 5-6 scenes total.
  - For each non-"stats" scene: "aItems" and "bItems" are 2-4 SHORT bullets each (max ~24 chars per bullet) comparing that dimension for player A vs player B. "title" is an ALL-CAPS label ("AWARDS", "TEAMS", "COACHES", "TEAMMATES", "COMPETITION").
  - The "stats" scene has empty "aItems"/"bItems" (it renders statRows), title "BY THE NUMBERS".
  - Every scene has a "narration": one punchy spoken sentence for that section (this is the voiceover + caption).
- "hook": one scroll-stopping opening sentence. "verdict": a closing line that explicitly asks viewers to vote (e.g. "Drop a 1 for Jordan, a 2 for LeBron 👇").
- "youtube.title": <=100 chars, debate-forward. "youtube.tags": 10-15 tags (no '#'). "youtube.hashtags": 3-5 incl. "#Shorts".
- Keep it about on-field greatness. No personal-life controversy. Always fill "statsDisclaimer" reminding that facts are AI-generated and should be verified before publishing.`;

function buildUserPrompt(matchup: string): string {
  return `Create the full multi-dimensional debate plan for this matchup: "${matchup}".

Return JSON of this exact shape:
{
  "matchup": "Player A vs Player B",
  "sport": "Basketball",
  "playerA": { "name": "...", "oneLiner": "...", "wikiTitle": "..." },
  "playerB": { "name": "...", "oneLiner": "...", "wikiTitle": "..." },
  "statRows": [ { "label": "Championships", "a": "6", "b": "4", "edge": "A" } ],
  "hook": "...",
  "scenes": [
    { "kind": "awards", "title": "AWARDS", "aItems": ["..."], "bItems": ["..."], "narration": "..." },
    { "kind": "teams", "title": "TEAMS", "aItems": ["..."], "bItems": ["..."], "narration": "..." },
    { "kind": "coaches", "title": "COACHES", "aItems": ["..."], "bItems": ["..."], "narration": "..." },
    { "kind": "teammates", "title": "TEAMMATES", "aItems": ["..."], "bItems": ["..."], "narration": "..." },
    { "kind": "competition", "title": "COMPETITION", "aItems": ["..."], "bItems": ["..."], "narration": "..." },
    { "kind": "stats", "title": "BY THE NUMBERS", "aItems": [], "bItems": [], "narration": "..." }
  ],
  "verdict": "...",
  "youtube": { "title": "...", "description": "...", "tags": ["..."], "hashtags": ["#Shorts", "..."] },
  "statsDisclaimer": "..."
}`;
}

function asStrArr(v: unknown): string[] {
  return Array.isArray(v) ? v.map((x) => String(x)) : [];
}

function normalizePlan(plan: MatchupPlan): MatchupPlan {
  const hashtags = Array.isArray(plan.youtube?.hashtags) ? plan.youtube.hashtags : [];
  if (!hashtags.some((h) => h.toLowerCase() === '#shorts')) hashtags.unshift('#Shorts');

  const scenes: ComparisonScene[] = Array.isArray(plan.scenes)
    ? plan.scenes.map((s) => ({
        kind: s.kind,
        title: s.title || '',
        aItems: asStrArr(s.aItems),
        bItems: asStrArr(s.bItems),
        narration: s.narration || '',
      }))
    : [];

  return {
    ...plan,
    statRows: Array.isArray(plan.statRows) ? plan.statRows : [],
    scenes,
    youtube: {
      title: plan.youtube?.title || plan.matchup,
      description: plan.youtube?.description || '',
      tags: Array.isArray(plan.youtube?.tags) ? plan.youtube.tags : [],
      hashtags,
    },
    statsDisclaimer:
      plan.statsDisclaimer || 'Facts are AI-generated — double-check them before publishing.',
  };
}

export async function generateMatchupPlan(matchup: string, apiKey?: string): Promise<MatchupPlan> {
  const key = apiKey || process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error('ANTHROPIC_API_KEY is required');
  if (!matchup?.trim()) throw new Error('A matchup is required');

  const client = new Anthropic({ apiKey: key });

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 4000,
    system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
    messages: [{ role: 'user', content: buildUserPrompt(matchup.trim()) }],
  });

  const text = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('');

  return normalizePlan(extractJson<MatchupPlan>(text));
}
