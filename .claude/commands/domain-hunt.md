# Domain Hunt

Run the full domain investing intelligence workflow for the App-Engine project.

## Steps

1. **Check the trend pipeline**: Read `app-engine/modules/trends/index.ts` and the source files in `app-engine/modules/trends/sources/` to understand what signals are being aggregated.

2. **Review the scorer**: Read `app-engine/modules/trends/claude-scorer.ts` and examine the current SYSTEM_PROMPT. Identify any gaps — are the scoring criteria still aligned with current market conditions? Suggest refinements if needed.

3. **Check domain generation**: Read `app-engine/modules/domains/generate.ts`. Are the TARGET_TLDS and strategies still optimal? `.ai` domains have surged in value — ensure they're in the mix.

4. **Review appraisal logic**: Read `app-engine/modules/domains/appraisal.ts`. Confirm GoDaddy GoValue integration is working and the Claude appraisal model is current.

5. **Run a manual hunt**: If the user provides keywords or a trend area, generate 10–15 domain candidates using the strategies (exact-match, brandable, compound, keyword-suffix). For each, give:
   - Domain name (with .com and .ai variants)
   - Strategy used
   - Why a company would pay for it
   - Estimated value range

## Output Format

For manual hunts, output a ranked table:

| Domain | Strategy | Buyer Profile | Est. Value |
|--------|----------|---------------|------------|
| example.ai | exact-match | AI startup needing brand | $5k–$25k |

Follow with 2–3 sentences on the strongest candidates and why.

## Context
- App is at `app-engine/`
- Claude scorer uses `claude-sonnet-4-6`
- GoDaddy API key is in env as `GODADDY_API_KEY` / `GODADDY_SECRET`
- Trends DB is LibSQL via Drizzle — schema in `lib/db/`
