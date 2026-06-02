# Matchup Maker (Repurpose Engine)

Two tools in one app:

1. **Matchup Maker** (primary) — type a sports debate ("Jordan vs LeBron") →
   Claude researches both players, writes the debate + stats, fetches photos,
   renders graphics, voices the narration, assembles a vertical Short, and
   uploads it to YouTube. Original content, copyright-clean.
2. **Repurpose** (legacy) — paste a TikTok/IG/Short link → metadata → publish.

Shorts-first.

## Matchup Maker pipeline

```
prompt → research/script → photos → scenes → voice → assemble → review → upload
```

| Stage | Module | Status |
|-------|--------|--------|
| Idea generator | `modules/matchup/ideas.ts` | ✅ working |
| Research + debate script + stats | `modules/matchup/script.ts` | ✅ working |
| Player photos (Wikimedia + attribution) | `modules/visuals/photos.ts` | ✅ working |
| Stat-card / scene graphics (SVG→PNG) | `modules/visuals/scenes.ts` | ✅ working |
| AI voiceover (ElevenLabs / OpenAI) | `modules/voice/tts.ts` | ✅ working |
| Video assembly (bundled ffmpeg) | `modules/video/assemble.ts` | ✅ working |
| Orchestrator (one prompt → mp4) | `modules/matchup/produce.ts` | ✅ working |
| Upload to YouTube | `modules/youtube/upload.ts` | ✅ working |

## Repurpose (legacy) pipeline

| Stage | Module | Status |
|-------|--------|--------|
| Download source clip + caption | `modules/ingest/download.ts` | ✅ working (yt-dlp) |
| Transcribe audio (optional) | `modules/ingest/transcribe.ts` | ✅ working (Whisper) |
| Generate metadata (Claude) | `modules/generate/shorts-metadata.ts` | ✅ working |
| YouTube OAuth | `modules/youtube/oauth.ts` | ✅ working |
| Upload to YouTube | `modules/youtube/upload.ts` | ✅ working |

## Stack

- Next.js 14 / React 18 / Tailwind v3 (matches `app-engine`)
- `@anthropic-ai/sdk` — `claude-sonnet-4-6`, prompt-cached system prompt
- Drizzle + libSQL/Turso — one `jobs` table tracks each link through the pipeline
- `youtube-dl-exec` (yt-dlp) + `fluent-ffmpeg` — ingest (step 2)
- `googleapis` — YouTube Data API v3 upload

> Note: `yt-dlp` and `ffmpeg` are native binaries, so ingest runs in a
> long-running Node process (`npm run dev` on :3002), not a serverless function.
> Splitting ingest into a worker for cloud deploys comes later.

## Setup

```bash
cd repurpose
cp .env.local.example .env.local   # add ANTHROPIC_API_KEY at minimum
npm install
npm run dev                        # http://localhost:3002
```

## Connect YouTube (one-time)

1. In **Google Cloud Console** → create an OAuth 2.0 Client ID (type: Web app).
2. Add redirect URI `http://localhost:3002/api/auth/youtube`.
3. Put the client id/secret in `.env.local`.
4. Visit `http://localhost:3002/api/auth/youtube`, approve consent.
5. Copy the returned `refreshToken` into `YOUTUBE_REFRESH_TOKEN`, restart `npm run dev`.

Uploads default to **private** — flip the selector to public when you're ready.
Note: the `youtube.upload` scope needs Google verification before non-test users
can use it, and uploads cost 1,600 quota units each (~6/day default).

## Routes

- `POST /api/ingest` — `{ url }` → detects platform (download lands step 2)
- `POST /api/generate` — `{ sourcePlatform?, sourceCaption?, transcript?, channelContext? }` → `{ metadata }`
- `POST /api/publish` — `{ localPath, metadata, privacyStatus? }` (publish step)
- `GET  /api/auth/youtube` — start Google OAuth consent / handle callback
