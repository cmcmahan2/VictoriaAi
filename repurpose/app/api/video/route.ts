import { NextRequest, NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import { loadEnv } from '../../../lib/env';
import { getJob } from '../../../lib/db/jobs';

export const runtime = 'nodejs';

// GET /api/video?job=<id> — stream a produced Short for the preview player.
// Only serves files inside MEDIA_DIR (no path traversal).
export async function GET(req: NextRequest) {
  const jobParam = req.nextUrl.searchParams.get('job');
  if (!jobParam) {
    return NextResponse.json({ error: { message: 'job is required' } }, { status: 400 });
  }

  const job = await getJob(Number(jobParam));
  if (!job?.localPath) {
    return NextResponse.json({ error: { message: 'Video not found' } }, { status: 404 });
  }

  const env = loadEnv();
  const root = path.resolve(env.MEDIA_DIR);
  const resolved = path.resolve(job.localPath);
  if (!resolved.startsWith(root) || !fs.existsSync(resolved)) {
    return NextResponse.json({ error: { message: 'Video unavailable' } }, { status: 404 });
  }

  const data = fs.readFileSync(resolved);
  return new NextResponse(data, {
    headers: {
      'Content-Type': 'video/mp4',
      'Content-Length': String(data.length),
      'Cache-Control': 'no-store',
    },
  });
}
