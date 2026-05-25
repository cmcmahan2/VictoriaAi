// Domain availability via RDAP (Registration Data Access Protocol).
// rdap.org is a public aggregator that 302-redirects to the authoritative
// RDAP server for the domain's TLD. A 404 means the domain is not registered
// (available); a 200 means it is registered (taken). Anything else is unknown.
//
// This is free, keyless, and standardized — the reliable base layer.

export type Availability = 'available' | 'taken' | 'unknown';

const RDAP_BASE = 'https://rdap.org/domain/';
const PER_REQUEST_TIMEOUT_MS = 6000;
const CONCURRENCY = 12;

async function checkOne(domain: string): Promise<Availability> {
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
    // 429/5xx/other — we can't be sure.
    return 'unknown';
  } catch {
    return 'unknown';
  } finally {
    clearTimeout(timer);
  }
}

// Checks a list of domains with bounded concurrency. Returns a map of
// domain -> availability, preserving robustness if individual lookups fail.
export async function checkAvailability(
  domains: string[],
): Promise<Map<string, Availability>> {
  const result = new Map<string, Availability>();
  let cursor = 0;

  async function worker() {
    while (cursor < domains.length) {
      const i = cursor++;
      const domain = domains[i];
      result.set(domain, await checkOne(domain));
    }
  }

  const workers = Array.from({ length: Math.min(CONCURRENCY, domains.length) }, worker);
  await Promise.all(workers);

  return result;
}
