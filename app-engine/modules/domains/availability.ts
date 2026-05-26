// Domain availability checking.
//
// Two layers, strongest first:
//   1. GoDaddy /v1/domains/available — the registrar's own data. Authoritative
//      ("definitive") and returns the real registration price. Used when creds
//      are configured. This is what lets us actually trust a domain is buyable.
//   2. RDAP via rdap.org — free, keyless, standardized. A 404 means the domain
//      is not registered; a 200 means it is. Used as the base layer and as a
//      fallback for anything GoDaddy can't answer definitively.
//
// A candidate is only ever surfaced as "available" when a layer confirms it.
// RDAP alone can report premium/reserved names as unregistered even though they
// are not freely registrable, so GoDaddy confirmation is preferred when present.

export type Availability = 'available' | 'taken' | 'unknown';

export type AvailabilityInfo = {
  status: Availability;
  price?: number; // real annual registration price in USD, when known (GoDaddy)
  source: 'godaddy' | 'rdap';
};

export type GodaddyCreds = { key: string; secret: string };

const RDAP_BASE = 'https://rdap.org/domain/';
const PER_REQUEST_TIMEOUT_MS = 6000;
const CONCURRENCY = 12;

const GODADDY_BASE = 'https://api.godaddy.com/v1/domains/available';
const GODADDY_TIMEOUT_MS = 15000;
const GODADDY_BATCH = 50; // bulk availability accepts a list; keep batches modest

// --- RDAP base layer -------------------------------------------------------

async function rdapCheckOne(domain: string): Promise<Availability> {
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

async function rdapCheck(domains: string[]): Promise<Map<string, Availability>> {
  const result = new Map<string, Availability>();
  let cursor = 0;

  async function worker() {
    while (cursor < domains.length) {
      const i = cursor++;
      const domain = domains[i];
      result.set(domain, await rdapCheckOne(domain));
    }
  }

  const workers = Array.from({ length: Math.min(CONCURRENCY, domains.length) }, worker);
  await Promise.all(workers);
  return result;
}

// --- GoDaddy authoritative layer -------------------------------------------

type GodaddyAvailRow = {
  domain: string;
  available?: boolean;
  definitive?: boolean;
  price?: number; // micro-units: actual price * 1,000,000
  currency?: string;
};

// Checks one batch against GoDaddy. Returns only rows GoDaddy answered
// definitively; anything ambiguous or errored is omitted so it can fall through
// to RDAP. Throws nothing — network/auth failures yield an empty map.
async function godaddyCheckBatch(
  domains: string[],
  creds: GodaddyCreds,
): Promise<Map<string, AvailabilityInfo>> {
  const out = new Map<string, AvailabilityInfo>();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), GODADDY_TIMEOUT_MS);
  try {
    const res = await fetch(`${GODADDY_BASE}?checkType=FULL`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Authorization: `sso-key ${creds.key}:${creds.secret}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(domains),
      cache: 'no-store',
    });
    if (!res.ok) return out;

    const data = (await res.json()) as { domains?: GodaddyAvailRow[] };
    for (const row of data.domains || []) {
      if (!row.domain || row.definitive !== true || typeof row.available !== 'boolean') {
        continue; // not definitive — let RDAP decide
      }
      const price =
        typeof row.price === 'number' ? Math.round(row.price / 1_000_000) : undefined;
      out.set(row.domain.toLowerCase(), {
        status: row.available ? 'available' : 'taken',
        price: row.available ? price : undefined,
        source: 'godaddy',
      });
    }
    return out;
  } catch {
    return out;
  } finally {
    clearTimeout(timer);
  }
}

async function godaddyCheck(
  domains: string[],
  creds: GodaddyCreds,
): Promise<Map<string, AvailabilityInfo>> {
  const merged = new Map<string, AvailabilityInfo>();
  for (let i = 0; i < domains.length; i += GODADDY_BATCH) {
    const batch = domains.slice(i, i + GODADDY_BATCH);
    const res = await godaddyCheckBatch(batch, creds);
    for (const [k, v] of res) merged.set(k, v);
  }
  return merged;
}

// --- Public API ------------------------------------------------------------

// Checks a list of domains and returns domain -> availability info. When
// GoDaddy creds are supplied, GoDaddy is the authoritative source (and yields
// real prices); RDAP fills in anything GoDaddy did not answer definitively.
export async function checkAvailability(
  domains: string[],
  creds?: GodaddyCreds | null,
): Promise<Map<string, AvailabilityInfo>> {
  const result = new Map<string, AvailabilityInfo>();
  if (domains.length === 0) return result;

  // Layer 1: GoDaddy (authoritative) when configured.
  if (creds) {
    const gd = await godaddyCheck(domains, creds);
    for (const [k, v] of gd) result.set(k, v);
  }

  // Layer 2: RDAP for anything still unresolved.
  const remaining = domains.filter((d) => !result.has(d));
  if (remaining.length > 0) {
    const rdap = await rdapCheck(remaining);
    for (const [domain, status] of rdap) {
      result.set(domain, { status, source: 'rdap' });
    }
  }

  return result;
}
