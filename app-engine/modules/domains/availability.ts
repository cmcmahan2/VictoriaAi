// Domain availability via authoritative per-TLD RDAP servers.
//
// rdap.org (the public aggregator) is unreliable from Vercel — it frequently
// times out or returns stale data. Instead we hit each TLD's authoritative
// RDAP endpoint directly, which is faster and more accurate.
//
// 404 = not registered (available). 200 = registered (taken). Anything else
// = unknown (treated as taken to avoid wasting money on bad registrations).

export type Availability = 'available' | 'taken' | 'unknown';

// eslint-disable-next-line @typescript-eslint/no-unused-vars
type GodaddyCreds = { key: string; secret: string };

const TIMEOUT_MS = 6000;
const CONCURRENCY = 20;

// Authoritative RDAP base URLs by TLD.
// These are stable registry endpoints — no aggregator, no IP issues.
const RDAP_SERVERS: Record<string, string> = {
  com: 'https://rdap.verisign.com/com/v1/domain/',
  net: 'https://rdap.verisign.com/net/v1/domain/',
  org: 'https://rdap.publicinterestregistry.org/rdap/domain/',
  io:  'https://rdap.nic.io/domain/',
  co:  'https://rdap.nic.co/domain/',
  app: 'https://rdap.nic.google/domain/',
  dev: 'https://rdap.nic.google/domain/',
  ai:  'https://rdap.org/domain/', // .ai has no public RDAP; use aggregator
};
const RDAP_FALLBACK = 'https://rdap.org/domain/';

function rdapBase(tld: string): string {
  return RDAP_SERVERS[tld] ?? RDAP_FALLBACK;
}

async function checkOne(domain: string): Promise<Availability> {
  const tld = domain.split('.').pop() ?? '';
  const url = rdapBase(tld) + encodeURIComponent(domain);

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: ctrl.signal,
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

export async function checkAvailability(
  domains: string[],
  // GoDaddy creds kept in signature for future use (requires IP whitelisting)
  _godaddy?: GodaddyCreds,
): Promise<Map<string, Availability>> {
  const result = new Map<string, Availability>();
  let cursor = 0;

  async function worker() {
    while (cursor < domains.length) {
      const i = cursor++;
      result.set(domains[i], await checkOne(domains[i]));
    }
  }

  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, domains.length) }, worker));
  return result;
}
