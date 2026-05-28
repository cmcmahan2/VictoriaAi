# VictoriaAi

Two Next.js apps in a monorepo: a music social network (**Tracklist**) and a domain investing intelligence platform (**App-Engine**). Both use Anthropic Claude as a core capability, not a bolt-on.

## Apps

### Tracklist (`/tracklist`)
Music social network. Users rate albums (1–10), write reviews, follow each other, debate music, and maintain lists.

- Framework: Next.js 16, React 19, Tailwind CSS v4
- Database: PostgreSQL via Prisma ORM
- Auth: NextAuth v4 — email + Spotify OAuth
- External APIs: Spotify, iTunes/Apple Music, MusicBrainz, Resend (email)
- **Claude role**: Generates 2–3 sentence album descriptions (`claude-haiku-4-5-20251001`), cached in DB to avoid redundant calls.

Key files:
- `app/api/album-blurb/[albumId]/route.ts` — Claude album description endpoint, DB-cached
- `app/api/auth/[...nextauth]/route.ts` — NextAuth handler
- `app/api/albums/route.ts` — Album CRUD + external API sync
- `lib/auth.ts` — NextAuth config with Spotify OAuth
- `prisma/schema.prisma` — Full DB schema

Dev commands:
```
cd tracklist
npm run dev              # localhost:3000
npx prisma studio        # DB GUI
npx prisma migrate dev   # apply schema changes
```

### App-Engine (`/app-engine`)
Domain investing intelligence. Aggregates market signals → scores naming trends → generates domain candidates → appraises their value.

- Framework: Next.js 14, React 18, Tailwind CSS v3
- Database: LibSQL (Turso) via Drizzle ORM
- External APIs: GoDaddy, Reddit, Product Hunt, GitHub Trending, YCombinator, Crunchbase, Google Trends
- **Claude role**: Trend scoring, domain name generation, domain appraisal — all using `claude-sonnet-4-6`.

Intelligence pipeline:
1. `modules/trends/index.ts` — Aggregates signals from 7 sources (parallel fetches)
2. `modules/trends/claude-scorer.ts` — Ranks trends by commercial domain value (1–100 score)
3. `modules/domains/generate.ts` — Generates registerable domain candidates (4 strategies)
4. `modules/domains/appraisal.ts` — Values domains, integrates GoDaddy GoValue for market pricing

Key API routes:
- `app/api/trends/route.ts` — POST: run full trend pipeline
- `app/api/domains/route.ts` — POST: generate domain candidates from trends
- `app/api/appraise/route.ts` — POST: appraise specific domains
- `app/api/analyze/route.ts` — POST: generic Claude prompt endpoint
- `app/api/tasks/route.ts` — POST/GET: async dispatch task queue (background Claude jobs)

Dev commands:
```
cd app-engine
npm run dev              # localhost:3001
npx drizzle-kit studio   # DB GUI
```

## Claude Models

| Model | Use case |
|-------|----------|
| `claude-haiku-4-5-20251001` | Fast, low-cost — album blurbs, short descriptions |
| `claude-sonnet-4-6` | Balanced quality/speed — trend scoring, domain gen, appraisal |
| `claude-opus-4-7` | Complex reasoning — use for multi-step analysis tasks |

Always import from `@anthropic-ai/sdk`, not raw fetch. The SDK handles retries, streaming, and type safety.

## Code Patterns

**Structured JSON output**: All Claude calls that need structured data use explicit JSON schemas in the system prompt. Strip markdown fences before parsing (`text.match(/\{[\s\S]*\}/)`).

**Truncation safety**: If Claude cuts off mid-response, find the last complete object (`raw.lastIndexOf('},')`) and close the array rather than crashing.

**DB caching**: Cache Claude outputs wherever the same input produces the same output (album descriptions, trend scores). Avoid redundant API calls.

**Prompt caching**: For long, repeated system prompts (>1024 tokens), add `"cache_control": {"type": "ephemeral"}` to the system block. Reduces cost and latency by up to 90% on cache hits.

**Route exports**: API routes export named HTTP method handlers (`GET`, `POST`, `PUT`, `DELETE`) — no default exports.

**Env vars**: Never hardcode keys. Use `process.env.ANTHROPIC_API_KEY` in both apps. App-engine validates env at startup via `lib/env.ts`.

## MCP Servers (Plugins)

These are your "plugins" — role-specific tool connections already active in this Claude Code session:

| Server | What it can do |
|--------|---------------|
| **GitHub** (`mcp__github__*`) | Read/write repos, PRs, issues, branches |
| **Gmail** (`mcp__d2397c28__*`) | Search threads, create drafts, label email |
| **Google Drive** (`mcp__df53f26e__*`) | Read/write/search files |
| **Finance data** (`mcp__0a3b9efa__*`) | Market quotes, company financials, earnings, crypto |
| **LinkedIn Jobs** (`mcp__d0448e87__*`) | Search jobs, company data, resume |
| **Meta Ads** (`mcp__c12424fc__*`) | Ad campaign management, insights, audiences |

> Risk: Data piped through MCP servers (email content, financial data) goes to Anthropic's API. Review data retention policy for sensitive inputs.

## Git

- Main branch: `main`
- Feature branches: `claude/<feature>-<id>` (auto-created by Claude Code on the web)
- Commit style: imperative, concise (`Add prompt caching to trend scorer`, not `Added caching`)
- Always push to feature branch; create PR only when explicitly asked

## Skills (Custom Slash Commands)

Project-level slash commands live in `.claude/commands/`. Run them as `/project:<name>` in Claude Code:

| Command | Purpose |
|---------|---------|
| `/project:domain-hunt` | Full domain hunting pipeline briefing |
| `/project:trend-report` | Weekly trend intelligence report |
| `/project:music-review` | Draft an album review or artist brief |
| `/project:domain-outreach` | Draft cold email to a potential domain buyer |
| `/project:board-memo` | Format analysis into a one-page board memo |
