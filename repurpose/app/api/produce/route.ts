import { NextRequest, NextResponse } from 'next/server';
import path from 'node:path';
import { produceMatchupVideo } from '../../../modules/matchup/produce';
import type { MatchupPlan } from '../../../modules/matchup/script';
import { capabilities } from '../../../lib/env';
import { createJob } from '../../../lib/db/jobs';

export const runtime = 'nodejs';
export const maxDuration = 300;

// POST: produce the full video for a matchup (or a pre-generated plan), persist
// a job, and return a preview URL + the YouTube metadata for the review screen.
// Body: { matchup?: string, plan?: MatchupPlan }
export async function POST(req: NextRequest) {
  try {
    if (!process.env.ANTHROPIC_API_KEY) {
      return NextResponse.json({ error: { message: 'ANTHROPIC_API_KEY is not configured' } }, { status: 400 });
    }
    if (!capabilities.hasVoice()) {
      return NextResponse.json(
        { error: { message: 'No voice configured. Add ELEVENLABS_API_KEY (recommended) or OPENAI_API_KEY.' } },
        { status: 400 },
      );
    }

    const body = (await req.json()) as { matchup?: string; plan?: MatchupPlan; speed?: number };
    if (!body.matchup && !body.plan) {
      return NextResponse.json({ error: { message: 'Provide a matchup or a plan' } }, { status: 400 });
    }

    const { plan, videoPath, attributions } = await produceMatchupVideo(body, process.env.ANTHROPIC_API_KEY);

    // Final description: Claude's copy + hashtags + photo credits.
    const parts = [plan.youtube.description, plan.youtube.hashtags.join(' ')];
    if (attributions.length) parts.push(`Credits:\n${attributions.join('\n')}`);
    const description = parts.filter(Boolean).join('\n\n');

    // Persist a job when a DB is configured (optional — for history/upload by id).
    const jobId = await createJob({
      sourceUrl: `matchup:${plan.matchup}`,
      sourcePlatform: 'matchup',
      status: 'generated',
      localPath: videoPath,
      title: plan.youtube.title,
      description,
      tags: JSON.stringify(plan.youtube.tags),
      hashtags: JSON.stringify(plan.youtube.hashtags),
    });

    // Always provide a working preview URL — by job id if we have a DB, else by
    // the file path relative to MEDIA_DIR (no DB required).
    const root = path.resolve(process.env.MEDIA_DIR || './tmp-media');
    const rel = path.relative(root, videoPath).split(path.sep).join('/');
    const videoUrl =
      jobId !== null ? `/api/video?job=${jobId}` : `/api/video?path=${encodeURIComponent(rel)}`;

    const metadata = { title: plan.youtube.title, description, tags: plan.youtube.tags, hashtags: plan.youtube.hashtags };

    return NextResponse.json({ jobId, videoUrl, videoPath, plan, attributions, metadata });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
