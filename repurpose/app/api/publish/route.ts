import { NextRequest, NextResponse } from 'next/server';
import { publishToYouTube } from '../../../modules/youtube/upload';
import type { ShortsMetadata } from '../../../modules/generate/shorts-metadata';
import { capabilities } from '../../../lib/env';
import { getJob, updateJob } from '../../../lib/db/jobs';

export const runtime = 'nodejs';
export const maxDuration = 300;

type PublishBody = {
  jobId?: number;
  // Used when there's no DB (or to override the stored job).
  localPath?: string;
  metadata?: ShortsMetadata;
  privacyStatus?: 'private' | 'unlisted' | 'public';
};

// POST: upload a downloaded clip to YouTube with generated metadata.
// Either pass { jobId } (reads localPath + metadata from the job row) or pass
// { localPath, metadata } directly.
export async function POST(req: NextRequest) {
  try {
    if (!capabilities.canPublish()) {
      return NextResponse.json(
        {
          error: {
            message:
              'YouTube publishing is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN.',
          },
        },
        { status: 400 },
      );
    }

    const body = (await req.json()) as PublishBody;

    let localPath = body.localPath;
    let metadata = body.metadata;

    // Hydrate from the job row when only a jobId was supplied.
    if ((!localPath || !metadata) && typeof body.jobId === 'number') {
      const job = await getJob(body.jobId);
      if (!job) {
        return NextResponse.json({ error: { message: 'Job not found' } }, { status: 404 });
      }
      localPath = localPath || job.localPath || undefined;
      if (!metadata) {
        metadata = {
          title: job.title || '',
          description: job.description || '',
          tags: job.tags ? (JSON.parse(job.tags) as string[]) : [],
          hashtags: job.hashtags ? (JSON.parse(job.hashtags) as string[]) : [],
          hook: job.hook || '',
        };
      }
    }

    if (!localPath || !metadata?.title) {
      return NextResponse.json(
        { error: { message: 'localPath and generated metadata are required' } },
        { status: 400 },
      );
    }

    const result = await publishToYouTube({
      localPath,
      metadata,
      privacyStatus: body.privacyStatus || 'private',
    });

    if (typeof body.jobId === 'number') {
      await updateJob(body.jobId, {
        status: 'published',
        youtubeVideoId: result.youtubeVideoId,
      });
    }

    return NextResponse.json({ result });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
