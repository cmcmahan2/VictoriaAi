import { NextRequest, NextResponse } from 'next/server';
import { detectPlatform, downloadSource } from '../../../modules/ingest/download';
import { transcribeAudio } from '../../../modules/ingest/transcribe';
import { capabilities } from '../../../lib/env';
import { createJob, updateJob } from '../../../lib/db/jobs';

// yt-dlp spawns a child process and downloads can take a while — force the
// Node runtime and a generous duration rather than the edge runtime.
export const runtime = 'nodejs';
export const maxDuration = 300;

// POST: download a source clip + original caption from a pasted link, and
// (when configured) transcribe the audio for richer metadata generation.
// Body: { url: string }
export async function POST(req: NextRequest) {
  let jobId: number | null = null;
  try {
    const { url } = (await req.json()) as { url?: string };
    if (!url || !/^https?:\/\//i.test(url)) {
      return NextResponse.json(
        { error: { message: 'A valid http(s) URL is required' } },
        { status: 400 },
      );
    }

    const platform = detectPlatform(url);
    jobId = await createJob({ sourceUrl: url, sourcePlatform: platform, status: 'pending' });

    const result = await downloadSource(url);

    let transcript: string | null = null;
    if (capabilities.hasTranscription()) {
      try {
        transcript = await transcribeAudio(result.localPath);
      } catch (txErr) {
        // Transcription is best-effort; the generator falls back to the caption.
        console.warn('Transcription failed:', txErr);
      }
    }

    if (jobId !== null) {
      await updateJob(jobId, {
        status: 'downloaded',
        localPath: result.localPath,
        sourceCaption: result.caption,
        transcript,
      });
    }

    return NextResponse.json({
      jobId,
      platform: result.platform,
      localPath: result.localPath,
      caption: result.caption,
      title: result.title,
      durationSec: result.durationSec,
      transcript,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    if (jobId !== null) await updateJob(jobId, { status: 'error', error: message });
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
