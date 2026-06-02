import { NextRequest, NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import { getJob } from '../../../lib/db/jobs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

// GET /api/video?job=<id>  — stream a produced Short by job id (needs a DB)
// GET /api/video?path=<rel> — stream by file path relative to MEDIA_DIR (no DB)
// Either way, only files inside MEDIA_DIR are served (no path traversal).
// Reads MEDIA_DIR directly (not loadEnv) so it never requires other keys.
export async function GET(req: NextRequest) {
  const root = path.resolve(process.env.MEDIA_DIR || './tmp-media');

  const jobParam = req.nextUrl.searchParams.get('job');
  const pathParam = req.nextUrl.searchParams.get('path');

  let target: string | null = null;
  if (pathParam) {
    target = path.resolve(root, pathParam);
  } else if (jobParam) {
    const job = await getJob(Number(jobParam));
    target = job?.localPath ? path.resolve(job.localPath) : null;
  } else {
    return NextResponse.json({ error: { message: 'job or path is required' } }, { status: 400 });
  }

  const resolved = target;
  if (!resolved || !resolved.startsWith(root) || !fs.existsSync(resolved)) {
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
