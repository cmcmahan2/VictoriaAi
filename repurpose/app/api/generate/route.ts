import { NextRequest, NextResponse } from 'next/server';
import { generateShortsMetadata, type GenerateInput } from '../../../modules/generate/shorts-metadata';

// POST: turn source context (caption / transcript) into YouTube Shorts metadata.
// Body: { sourcePlatform?, sourceCaption?, transcript?, channelContext? }
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as GenerateInput;

    const key = process.env.ANTHROPIC_API_KEY;
    if (!key) {
      return NextResponse.json(
        { error: { message: 'ANTHROPIC_API_KEY is not configured' } },
        { status: 400 },
      );
    }

    const metadata = await generateShortsMetadata(body, key);
    return NextResponse.json({ metadata });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
