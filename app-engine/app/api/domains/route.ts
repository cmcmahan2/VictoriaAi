import { NextResponse } from 'next/server';
import { runDomainHunt } from '@/modules/domains';
import type { ScoredTrend } from '@/modules/trends/claude-scorer';
import { loadEnv } from '@/lib/env';

export const maxDuration = 60; // Vercel Hobby cap

const TIMEOUT_MS = 50_000;

export async function POST(req: Request) {
  try {
    const env = loadEnv();

    const body = (await req.json().catch(() => ({}))) as { trends?: ScoredTrend[] };
    const trends = Array.isArray(body.trends) ? body.trends : [];

    if (trends.length === 0) {
      return NextResponse.json(
        { ok: false, error: 'No trends provided. Run the trend hunt first.' },
        { status: 400 },
      );
    }

    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Domain hunt timed out — try again in a moment')), TIMEOUT_MS),
    );

    const result = await Promise.race([
      runDomainHunt(trends, {
        ANTHROPIC_API_KEY: env.ANTHROPIC_API_KEY,
        GODADDY_API_KEY: env.GODADDY_API_KEY,
        GODADDY_API_SECRET: env.GODADDY_API_SECRET,
      }),
      timeoutPromise,
    ]);

    return NextResponse.json({ ok: true, domains: result.domains, meta: result.meta, usage: result.meta.usage });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/domains] Error:', message);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
