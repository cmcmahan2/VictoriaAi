import { NextResponse } from 'next/server';
import { capabilities } from '@/lib/env';

export async function GET() {
  if (!capabilities.hasGodaddy()) {
    return NextResponse.json(
      { ok: false, error: 'GODADDY_API_KEY and GODADDY_API_SECRET are not set.' },
      { status: 400 },
    );
  }

  const key = process.env.GODADDY_API_KEY!;
  const secret = process.env.GODADDY_API_SECRET!;

  // Use a known premium domain to validate the key without side effects.
  try {
    const res = await fetch('https://api.godaddy.com/v1/appraisal/google.com', {
      headers: {
        Authorization: `sso-key ${key}:${secret}`,
        Accept: 'application/json',
      },
      cache: 'no-store',
    });

    if (res.status === 401 || res.status === 403) {
      return NextResponse.json(
        { ok: false, error: 'GoDaddy rejected the credentials (401/403). Double-check your key and secret.' },
        { status: 401 },
      );
    }

    if (!res.ok) {
      return NextResponse.json(
        { ok: false, error: `GoDaddy returned HTTP ${res.status}. The key may be valid but the API had an issue.` },
        { status: 502 },
      );
    }

    const data = (await res.json()) as { govalue?: number };
    return NextResponse.json({
      ok: true,
      message: 'GoDaddy credentials are valid.',
      sample: data,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 502 });
  }
}
