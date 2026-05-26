import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

async function testGodaddy() {
  const key = process.env.GODADDY_API_KEY;
  const secret = process.env.GODADDY_API_SECRET;
  if (!key || !secret) return { ok: false, error: 'Keys not configured in environment.' };

  try {
    const res = await fetch('https://api.godaddy.com/v1/appraisal/example.com', {
      headers: {
        Authorization: `sso-key ${key}:${secret}`,
        Accept: 'application/json',
      },
    });
    if (res.status === 401 || res.status === 403) {
      return {
        ok: false,
        error:
          'GoDaddy rejected the credentials (401/403). Double-check your key and secret. ' +
          'Note: GoValue requires a production API key — OTE (sandbox) keys will not work.',
      };
    }
    if (!res.ok) return { ok: false, error: `GoDaddy returned HTTP ${res.status}.` };
    return { ok: true };
  } catch (e) {
    return { ok: false, error: `Network error: ${(e as Error).message}` };
  }
}

async function testNamecheap() {
  const user = process.env.NAMECHEAP_API_USER;
  const key = process.env.NAMECHEAP_API_KEY;
  const ip = process.env.NAMECHEAP_CLIENT_IP;
  if (!user || !key || !ip) return { ok: false, error: 'NAMECHEAP_API_USER, NAMECHEAP_API_KEY, and NAMECHEAP_CLIENT_IP must all be set.' };

  try {
    const params = new URLSearchParams({
      ApiUser: user,
      ApiKey: key,
      UserName: user,
      ClientIp: ip,
      Command: 'namecheap.users.getBalances',
    });
    const res = await fetch(`https://api.namecheap.com/xml.response?${params}`);
    const text = await res.text();
    if (text.includes('Status="ERROR"') || text.includes('errors')) {
      const match = text.match(/<Error[^>]*>([^<]+)<\/Error>/i);
      return { ok: false, error: match ? match[1] : 'Namecheap returned an error. Check credentials and IP whitelist.' };
    }
    if (text.includes('Status="OK"')) return { ok: true };
    return { ok: false, error: 'Unexpected response from Namecheap.' };
  } catch (e) {
    return { ok: false, error: `Network error: ${(e as Error).message}` };
  }
}

async function testResend() {
  const key = process.env.RESEND_API_KEY;
  if (!key) return { ok: false, error: 'RESEND_API_KEY not set.' };

  try {
    const res = await fetch('https://api.resend.com/domains', {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (res.status === 401 || res.status === 403) return { ok: false, error: 'Resend rejected the API key (401/403).' };
    if (!res.ok) return { ok: false, error: `Resend returned HTTP ${res.status}.` };
    return { ok: true };
  } catch (e) {
    return { ok: false, error: `Network error: ${(e as Error).message}` };
  }
}

async function testNamebio() {
  const key = process.env.NAMEBIO_API_KEY;
  if (!key) return { ok: false, error: 'NAMEBIO_API_KEY not set.' };

  try {
    const res = await fetch(`https://namebio.com/api/v2/search?q=test.com&apikey=${encodeURIComponent(key)}`);
    if (res.status === 401 || res.status === 403) return { ok: false, error: 'NameBio rejected the API key.' };
    if (res.status === 404) return { ok: false, error: 'NameBio API endpoint not found — check your plan supports API access.' };
    if (!res.ok) return { ok: false, error: `NameBio returned HTTP ${res.status}.` };
    return { ok: true };
  } catch (e) {
    return { ok: false, error: `Network error: ${(e as Error).message}` };
  }
}

const HANDLERS: Record<string, () => Promise<{ ok: boolean; error?: string }>> = {
  godaddy: testGodaddy,
  namecheap: testNamecheap,
  resend: testResend,
  namebio: testNamebio,
};

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const service = searchParams.get('service') ?? '';

  const handler = HANDLERS[service];
  if (!handler) {
    return NextResponse.json({ ok: false, error: 'Unknown service.' }, { status: 400 });
  }

  const result = await handler();
  return NextResponse.json(result, { status: result.ok ? 200 : 400 });
}
