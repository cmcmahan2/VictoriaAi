import { NextResponse } from 'next/server';
import { sendOutreachEmail } from '@/modules/outreach/resend';

export async function POST(req: Request) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { ok: false, error: 'RESEND_API_KEY is not configured. Add it in Settings.' },
      { status: 503 },
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: 'Invalid JSON body.' }, { status: 400 });
  }

  const b = body as Record<string, unknown>;
  const required = ['to', 'domain', 'askPrice', 'senderName', 'senderEmail'] as const;
  for (const field of required) {
    if (!b[field]) {
      return NextResponse.json({ ok: false, error: `Missing required field: ${field}` }, { status: 400 });
    }
  }

  const result = await sendOutreachEmail(
    {
      to: String(b.to),
      domain: String(b.domain),
      askPrice: Number(b.askPrice),
      senderName: String(b.senderName),
      senderEmail: String(b.senderEmail),
      buyerProfile: b.buyerProfile ? String(b.buyerProfile) : undefined,
    },
    apiKey,
  );

  return NextResponse.json(result, { status: result.ok ? 200 : 400 });
}
