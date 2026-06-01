import { NextRequest, NextResponse } from 'next/server';
import { generateShortsMetadata, type GenerateInput } from '../../../modules/generate/shorts-metadata';
import { updateJob } from '../../../lib/db/jobs';

// POST: turn source context (caption / transcript) into YouTube Shorts metadata.
// Body: GenerateInput & { jobId?: number }
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as GenerateInput & { jobId?: number };

    const key = process.env.ANTHROPIC_API_KEY;
    if (!key) {
      return NextResponse.json(
        { error: { message: 'ANTHROPIC_API_KEY is not configured' } },
        { status: 400 },
      );
    }

    const metadata = await generateShortsMetadata(body, key);

    if (typeof body.jobId === 'number') {
      await updateJob(body.jobId, {
        status: 'generated',
        title: metadata.title,
        description: metadata.description,
        tags: JSON.stringify(metadata.tags),
        hashtags: JSON.stringify(metadata.hashtags),
        hook: metadata.hook,
      });
    }

    return NextResponse.json({ metadata });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
