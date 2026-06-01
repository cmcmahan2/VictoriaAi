# Repurpose Engine

Paste a TikTok / Instagram Reel / YouTube Short link → Claude generates
YouTube Shorts metadata (title, description, tags, hashtags, hook) → publish to
your YouTube channel.

Shorts-first. Long-form support comes later.

## Pipeline

```
paste link → download → understand → generate metadata → review → publish
```

| Stage | Module | Status |
|-------|--------|--------|
| Download source clip + caption | `modules/ingest/download.ts` | step 2 (stub) |
| Transcribe audio (optional) | `modules/ingest/transcribe.ts` | step 2 (stub) |
| Generate metadata (Claude) | `modules/generate/shorts-metadata.ts` | ✅ working |
| YouTube OAuth | `modules/youtube/oauth.ts` | consent URL ✅ / exchange stub |
| Upload to YouTube | `modules/youtube/upload.ts` | publish step (stub) |

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

## Routes

- `POST /api/ingest` — `{ url }` → detects platform (download lands step 2)
- `POST /api/generate` — `{ sourcePlatform?, sourceCaption?, transcript?, channelContext? }` → `{ metadata }`
- `POST /api/publish` — `{ localPath, metadata, privacyStatus? }` (publish step)
- `GET  /api/auth/youtube` — start Google OAuth consent / handle callback
