import { NextRequest, NextResponse } from 'next/server';
import { detectPlatform, downloadSource } from '../../../modules/ingest/download';

// POST: download a source clip + original caption from a pasted link.
// Body: { url: string }
// NOTE: the downloader itself lands in step 2 — for now this validates the
// link and reports the detected platform so the UI can be built against it.
export async function POST(req: NextRequest) {
  try {
    const { url } = (await req.json()) as { url?: string };
    if (!url || !/^https?:\/\//i.test(url)) {
      return NextResponse.json(
        { error: { message: 'A valid http(s) URL is required' } },
        { status: 400 },
      );
    }

    const platform = detectPlatform(url);

    try {
      const result = await downloadSource(url);
      return NextResponse.json({ result });
    } catch (stubErr: unknown) {
      // Step-1 scaffold: downloader not wired yet. Surface platform detection
      // and a 501 so the client can show "coming in step 2".
      const message = stubErr instanceof Error ? stubErr.message : 'Downloader unavailable';
      return NextResponse.json({ platform, error: { message } }, { status: 501 });
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
