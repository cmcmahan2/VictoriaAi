// Rank jobs against Christian's profile + priorities.
//
// Primary path: Claude (claude-sonnet-4-6) scores fit and writes a one-line
// rationale, following the repo convention (Anthropic SDK, JSON-only output,
// fence-stripping). Falls back to a transparent heuristic when no
// ANTHROPIC_API_KEY is set, so the tool always produces a ranking.

import { GEOGRAPHIES } from './tracks.js';
import { parseSalary } from './filters.js';

// The Anthropic SDK is imported lazily (only when an API key is set) so the
// heuristic path runs with zero dependencies — no `npm install` required.

const SYSTEM_PROMPT = `You are a career-matching analyst helping a specific candidate prioritize job listings.

The candidate: a Canadian Financial Economics graduate (University of Victoria, May 2026) with golf-industry experience (pro shop, TrackMan analytics), construction/labour background, and skills in data analysis, regression (Stata), Excel, and accounting. He is a post-grad with limited full-time professional experience.

His stated priorities, in order:
1. HIGH WAGE — strongly weight roles likely to pay well.
2. GOOD BENEFITS — weight roles likely to include benefits (health, housing, relocation), especially abroad (tax-free pay in the UAE counts heavily here).
3. SECTOR FIT — golf, finance, or real estate/development.
4. SENIORITY FIT — he is entry-level; roles needing many years of experience or senior licensure should score lower for realism, even if attractive.
5. WORK AUTHORIZATION — he is a Canadian citizen. Abroad roles are fine where a realistic pathway exists (UK Youth Mobility, AU/NZ/IE working holiday, UAE employer sponsorship, US TN visa as an Economist).

Rules:
- Output ONLY valid JSON. No prose, no markdown fences.
- Score each job 1-100 (fitScore). Be discriminating: spread scores out.
- "rationale" is ONE sentence, specific to this candidate.
- "flags" is an array of short tags from: ["high-wage","benefits","abroad","entry-level-friendly","stretch-role","needs-license","great-sector-fit"].`;

function userPrompt(jobs) {
  const lines = jobs.map((j, i) => {
    const g = GEOGRAPHIES[j.geo];
    return `#${i} | ${j.title} @ ${j.company} | ${j.location} (${j.geo}) | sector=${j.sector} | type=${j.type} | comp=${j.compensation} | workAuth=${g ? g.work_authorization : 'unknown'} | tax=${g ? g.tax_note : 'unknown'}`;
  });
  return `Score these ${jobs.length} jobs for the candidate.

JOBS:
${lines.join('\n')}

Return JSON of this exact shape:
{
  "rankings": [
    { "index": 0, "fitScore": 87, "rationale": "...", "flags": ["abroad","high-wage"] }
  ]
}
Include every job exactly once.`;
}

// Transparent fallback scoring when Claude isn't available.
function heuristicScore(job) {
  const g = GEOGRAPHIES[job.geo] || {};
  let score = 50;
  const flags = [];

  // Sector fit
  if (['golf', 'finance', 'real_estate'].includes(job.sector)) {
    score += 8;
    flags.push('great-sector-fit');
  }

  // High wage / benefits signals
  const comp = (job.compensation || '').toLowerCase();
  const taxFree = (g.tax_note || '').toLowerCase().includes('no personal income tax');
  // Use the actual posted salary when available: bigger number, bigger bonus.
  // Confirmed pay is rewarded more than assumed pay, so real high-wage roles
  // win the top spots (wage is a stated priority).
  const salary = parseSalary(job.compensation);
  if (salary) {
    if (salary.mid >= 120000) score += 22;
    else if (salary.mid >= 90000) score += 18;
    else if (salary.mid >= 70000) score += 14;
    else if (salary.mid >= 50000) score += 8;
    else score += 3;
    flags.push('high-wage');
  } else if (/grad program|graduate program/.test(comp)) {
    // Elite grad programs likely pay well, but comp is unconfirmed — modest nudge.
    score += 5;
    flags.push('high-wage');
  }
  // Tax-free pay (e.g. UAE) is a real benefit, but only a modest nudge so a
  // single low-tax city doesn't dominate the whole ranking.
  if (taxFree) {
    score += 5;
    flags.push('benefits');
  }
  if (g.abroad) {
    score += 6;
    flags.push('abroad');
  }
  // Recognized graduate / development programs: strong fit for a new grad and
  // typically come with structured pay, training, and benefits.
  if (/(grad program|graduate program|development program|academy|new analyst|summer analyst)/.test(comp + ' ' + job.title.toLowerCase())) {
    score += 7;
    flags.push('entry-level-friendly');
  }

  // Seniority realism — penalize obviously senior/licensed roles for an entry candidate.
  const t = job.title.toLowerCase();
  if (/(head|senior|vice president|vp|director|manager|lead)\b/.test(t)) {
    score -= 14;
    flags.push('stretch-role');
  } else if (/(intern|junior|graduate|attendant|analyst)/.test(t)) {
    score += 8;
    flags.push('entry-level-friendly');
  }
  if (/appraiser|aaci|underwriter|pga professional/.test(t)) {
    score -= 6;
    flags.push('needs-license');
  }

  score = Math.max(1, Math.min(100, score));
  const rationale = `${flags.includes('great-sector-fit') ? 'On-sector' : 'Adjacent'} ${job.sector.replace('_', ' ')} role${g.abroad ? ` abroad in ${g.label}` : ' in Canada'}${taxFree ? ', tax-free pay' : ''}${flags.includes('stretch-role') ? ' — likely a stretch for an entry-level grad' : ''}.`;
  return { fitScore: score, rationale, flags: [...new Set(flags)] };
}

// Primary sort: fit (which already weights wage/benefits/sector/level).
// Tiebreak by actual posted salary so higher-paying roles float up.
function byFitThenWage(a, b) {
  if (b.fitScore !== a.fitScore) return b.fitScore - a.fitScore;
  const sa = parseSalary(a.compensation)?.mid || 0;
  const sb = parseSalary(b.compensation)?.mid || 0;
  return sb - sa;
}

export async function rankJobs(jobs) {
  const apiKey = process.env.ANTHROPIC_API_KEY;

  if (!apiKey) {
    const ranked = jobs.map((j) => ({ ...j, ...heuristicScore(j) }));
    ranked.sort(byFitThenWage);
    return { ranked, engine: 'heuristic' };
  }

  try {
    const { default: Anthropic } = await import('@anthropic-ai/sdk');
    const client = new Anthropic({ apiKey });
    const response = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
      messages: [{ role: 'user', content: userPrompt(jobs) }],
    });

    const text = response.content
      .filter((b) => b.type === 'text')
      .map((b) => b.text)
      .join('');

    let jsonMatch = text.match(/\{[\s\S]*\}/);
    let parsed;
    try {
      parsed = JSON.parse(jsonMatch ? jsonMatch[0] : text);
    } catch {
      // Truncation safety: close the array at the last complete object.
      const cut = text.lastIndexOf('}');
      parsed = JSON.parse(text.slice(0, cut + 1) + ']}');
    }

    const byIndex = new Map(parsed.rankings.map((r) => [r.index, r]));
    const ranked = jobs.map((j, i) => {
      const r = byIndex.get(i) || heuristicScore(j);
      return { ...j, fitScore: r.fitScore, rationale: r.rationale, flags: r.flags || [] };
    });
    ranked.sort(byFitThenWage);
    return { ranked, engine: 'claude:claude-sonnet-4-6' };
  } catch (err) {
    // Network/key failure — degrade gracefully rather than crash.
    const ranked = jobs.map((j) => ({ ...j, ...heuristicScore(j) }));
    ranked.sort(byFitThenWage);
    return { ranked, engine: `heuristic (Claude error: ${err.message})` };
  }
}
