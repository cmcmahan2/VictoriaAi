// Domain availability checking.
//
// Primary: GoDaddy Domains API (GET /v1/domains/available) — used when
// credentials are provided. Far more reliable than RDAP, especially for
// .io, .ai, and .co TLDs where RDAP has known false-negative issues.
//
// Fallback: RDAP (rdap.org public aggregator). Free and keyless but can
// return stale or incorrect results for certain TLDs.

export type Availability = 'available' | 'taken' | 'unknown';

type GodaddyCreds = { key: string; secret: string };

const RDAP_BASE = 'https://rdap.org/domain/';
const GODADDY_API_BASE = 'https://api.godaddy.com/v1/domains/available';
const PER_REQUEST_TIMEOUT_MS = 8000;
const CONCURRENCY = 8; // GoDaddy rate-limits; keep concurrency moderate

// --- GoDaddy availability (primary) ----------------------------------------

async function checkOneGodaddy(domain: string, creds: GodaddyCreds): Promise<Availability> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PER_REQUEST_TIMEOUT_MS);
  try {
    const url = `${GODADDY_API_BASE}?domain=${encodeURIComponent(domain)}&checkType=FAST`;
    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        Authorization: `sso-key ${creds.key}:${creds.secret}`,
        Accept: 'application/json',
      },
      cache: 'no-store',
    });
    if (!res.ok) return 'unknown';
    const data = (await res.json()) as { available?: boolean };
    if (data.available === true) return 'available';
    if (data.available === false) return 'taken';
    return 'unknown';
  } catch {
    return 'unknown';
  } finally {
    clearTimeout(timer);
  }
}

// --- RDAP fallback (no credentials required) --------------------------------

async function checkOneRdap(domain: string): Promise<Availability> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PER_REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(`${RDAP_BASE}${encodeURIComponent(domain)}`, {
      signal: controller.signal,
      headers: { Accept: 'application/rdap+json' },
      redirect: 'follow',
      cache: 'no-store',
    });
    if (res.status === 404) return 'available';
    if (res.status === 200) return 'taken';
    return 'unknown';
  } catch {
    return 'unknown';
  } finally {
    clearTimeout(timer);
  }
}

// --- Public API -------------------------------------------------------------

// Checks a list of domains with bounded concurrency. Returns a map of
// domain -> availability. GoDaddy is used when credentials are present
// (recommended — RDAP is unreliable for .io/.ai/.co).
export async function checkAvailability(
  domains: string[],
  godaddy?: GodaddyCreds,
): Promise<Map<string, Availability>> {
  const result = new Map<string, Availability>();
  let cursor = 0;

  async function worker() {
    while (cursor < domains.length) {
      const i = cursor++;
      const domain = domains[i];
      result.set(
        domain,
        godaddy
          ? await checkOneGodaddy(domain, godaddy)
          : await checkOneRdap(domain),
      );
    }
  }

  const workers = Array.from({ length: Math.min(CONCURRENCY, domains.length) }, worker);
  await Promise.all(workers);

  return result;
}
