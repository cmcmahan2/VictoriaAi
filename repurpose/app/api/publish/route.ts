import { NextRequest, NextResponse } from 'next/server';
import { publishToYouTube, type PublishInput } from '../../../modules/youtube/upload';
import { capabilities } from '../../../lib/env';

// POST: upload a downloaded clip to YouTube with generated metadata.
// Body: { localPath, metadata, privacyStatus? }
// NOTE: the googleapis upload lands with the publish step. For now this checks
// credentials and returns 501 from the stub.
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

    const body = (await req.json()) as PublishInput;

    try {
      const result = await publishToYouTube(body);
      return NextResponse.json({ result });
    } catch (stubErr: unknown) {
      const message = stubErr instanceof Error ? stubErr.message : 'Publisher unavailable';
      return NextResponse.json({ error: { message } }, { status: 501 });
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
