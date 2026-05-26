import { NextResponse } from 'next/server';
import { appraiseDomains } from '@/modules/domains/appraisal';
import { loadEnv } from '@/lib/env';

export const maxDuration = 30;

export async function POST(req: Request) {
  try {
    const env = loadEnv();
    const body = (await req.json().catch(() => ({}))) as { domain?: string };

    // Strip protocol/trailing slash so users can paste full URLs
    const domain = (body.domain || '')
      .toLowerCase()
      .trim()
      .replace(/^https?:\/\//, '')
      .replace(/\/.*$/, '');

    if (!domain || !domain.includes('.')) {
      return NextResponse.json(
        { ok: false, error: 'Enter a valid domain name (e.g. techforge.com)' },
        { status: 400 },
      );
    }

    const parts = domain.split('.');
    const sld = parts[0];
    const tld = parts.slice(1).join('.');

    const { appraisals, usage } = await appraiseDomains(
      [{ domain, sld, tld, strategy: 'manual', basis: 'user lookup' }],
      {
        ANTHROPIC_API_KEY: env.ANTHROPIC_API_KEY,
        GODADDY_API_KEY: env.GODADDY_API_KEY,
        GODADDY_API_SECRET: env.GODADDY_API_SECRET,
      },
    );

    if (appraisals.length === 0) {
      return NextResponse.json({ ok: false, error: 'No appraisal returned' }, { status: 500 });
    }

    return NextResponse.json({ ok: true, appraisal: appraisals[0], usage });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/appraise] Error:', message);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
