import { NextRequest, NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';

export const runtime = 'nodejs';
export const maxDuration = 300;

// POST (multipart/form-data): accept a dropped video file, save it under
// MEDIA_DIR/uploads, and return a preview URL + its path for publishing.
export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const file = form.get('file');
    if (!file || typeof file === 'string') {
      return NextResponse.json({ error: { message: 'No file provided' } }, { status: 400 });
    }
    const f = file as File;

    const root = path.resolve(process.env.MEDIA_DIR || './tmp-media');
    const dir = path.join(root, 'uploads');
    fs.mkdirSync(dir, { recursive: true });

    const safe = (f.name || 'upload.mp4').replace(/[^a-z0-9._-]+/gi, '_');
    const dest = path.join(dir, `${Date.now()}-${safe}`);
    fs.writeFileSync(dest, Buffer.from(await f.arrayBuffer()));

    const rel = path.relative(root, dest).split(path.sep).join('/');
    return NextResponse.json({
      videoPath: dest,
      videoUrl: `/api/video?path=${encodeURIComponent(rel)}`,
      name: f.name,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Upload failed';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
