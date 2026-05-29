import { NextResponse } from 'next/server';
import { loadEnv } from '@/lib/env';
import { parseBuyBox } from '@/modules/agent/parse';

export type { ParsedBuyBox } from '@/modules/agent/parse';

export async function POST(req: Request) {
  try {
    const { text } = (await req.json().catch(() => ({}))) as { text?: string };
    if (!text || !text.trim()) {
      return NextResponse.json({ ok: false, error: 'Describe what you are looking for.' }, { status: 400 });
    }

    const env = loadEnv();
    const { parsed, usedAi } = await parseBuyBox(text, env.ANTHROPIC_API_KEY);
    return NextResponse.json({ ok: true, parsed, usedAi });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
