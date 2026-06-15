# Job Search Tool — Christian McMahan

A personalized job-search tool for a **Financial Economics post-grad**
(University of Victoria, May 2026) targeting **golf, finance, and real estate**
roles — at home in Canada and **anywhere abroad a Canadian or American can
realistically work** — with a heavy weight on **high wage and good benefits**.

It is not tied to any one city. The default snapshot deliberately spans
Australia, the UK, New Zealand, Ireland, the US, the UAE, and Canada so no
single low-tax market dominates the ranking.

It does three things:

1. **Ranks listings** against your specific profile and priorities.
2. **Tells you how you can legally work** in each country (visa pathway for a Canadian).
3. **Generates live search links** so you can re-run the hunt yourself anytime.

## Quick start

No install needed for the default (heuristic) ranking:

```bash
cd job-search
node index.js                 # rank all seed listings + print report
node index.js --links         # also list live Indeed/LinkedIn search links
node index.js --md > report.md
```

Filter by sector or geography:

```bash
node index.js --sectors golf,real_estate
node index.js --geos AE,US,GB        # Dubai, USA, UK only
node index.js --sectors finance --geos US --links
```

## Smarter ranking with Claude (optional)

Set an API key to have `claude-sonnet-4-6` score fit and write tailored
rationales (matches the repo's Anthropic SDK conventions). Without a key, a
transparent heuristic is used instead.

```bash
npm install                                   # installs @anthropic-ai/sdk
ANTHROPIC_API_KEY=sk-ant-... node index.js
```

## How it scores

Priorities, in order: **high wage → good benefits → sector fit → entry-level
realism → work authorization.** Tax-free pay (e.g. UAE) is weighted heavily for
the high-wage/benefits goal, and obviously senior or licensed roles
(Head Pro, VP, AACI appraiser) are discounted as stretches for a new grad.

Each result is tagged: 💰 high-wage · 🎁 benefits · ✈️ abroad · 🌱 entry-level ·
🎯 sector fit · 📈 stretch · 📜 needs license.

## Files

| File | Purpose |
|------|---------|
| `profile.json` | Your background, skills, and priorities — edit to re-tune. |
| `tracks.js` | Sectors, target geographies, and **visa pathways for Canadians**. |
| `seed-jobs.json` | Live listings pulled 2026-06-15 (so it ranks something out of the box). |
| `rank.js` | Claude + heuristic fit scoring. |
| `index.js` | CLI entry / report generator. |

## Work-authorization pathways baked in

| Country | How a Canadian works there | Why it's here |
|---------|----------------------------|---------------|
| 🇦🇪 UAE (Dubai) | Employer-sponsored work permit | **Tax-free pay**, housing/flights often included; booming luxury golf + real estate |
| 🇬🇧 UK | Youth Mobility Scheme (18–35, 2 yrs, no sponsor) | London finance + golf heritage |
| 🇦🇺 Australia | Working Holiday visa 417 (18–35, up to 3 yrs) | High minimum wage, Gold Coast golf |
| 🇳🇿 New Zealand | Working Holiday visa (18–35) | Resort golf |
| 🇮🇪 Ireland | Working Holiday Authorisation (18–35) | EU finance hub |
| 🇺🇸 USA | **TN visa — "Economist" is TN-eligible** | Highest finance pay; premier golf market |

> The TN visa angle is worth underlining: as a Financial Economics grad you may
> qualify under the **Economist** profession with a US job offer — a far easier
> route to the US than the H-1B lottery.

**For Americans:** the pathways above are written for a Canadian citizen. A US
citizen has different (often equivalent) routes — the US is home; Australia,
NZ, and Ireland offer comparable working-holiday/skilled programs; the UK uses
the Skilled Worker route rather than Youth Mobility; and TN works in reverse
(Canada hires US Economists). Edit `tracks.js` → `work_authorization` to retune
for a different citizenship.

## Refreshing listings

`seed-jobs.json` is a snapshot. To refresh, run the live searches again (via the
job-board tools) or simply use the `--links` output to browse current postings,
then paste new roles into `seed-jobs.json` and re-rank.
