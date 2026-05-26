// Domain availability checking.
//
// Strategy (in order):
// 1. GoDaddy API — accurate but requires IP whitelisting for production;
//    from Vercel serverless the IP is dynamic so requests often fail.
// 2. RDAP (rdap.org) — free, no auth, works from any IP. Unreliable for
//    .io/.ai/.co (can return 404 for taken domains). Used as primary when
//    GoDaddy fails and as sole checker when no credentials are configured.
// 3. Domainr (api.domainr.com) — fast, JSON, works from serverless, free
//    for light use. Used as a secondary confirmation for RDAP "available"
//    results on TLDs known to have RDAP accuracy issues.
//
// Final rule: a domain is marked available only when at least one authoritative
// source confirms it. "unknown" from all sources → treated as taken (safe).

export type Availability = 'available' | 'taken' | 'unknown';

type GodaddyCreds = { key: string; secret: string };

const RDAP_BASE = 'https://rdap.org/domain/';
const GODADDY_API_BASE = 'https://api.godaddy.com/v1/domains/available';
// Domainr's status API — no key required, returns machine-readable codes
const DOMAINR_BASE = 'https://api.domainr.com/v2/status?domain=';
const TIMEOUT_MS = 7000;
const CONCURRENCY = 6;

// TLDs where RDAP is known to produce false "available" results
const RDAP_UNRELIABLE_TLDS = new Set(['io', 'ai', 'co', 'app', 'dev']);

function tldOf(domain: string): string {
  return domain.split('.').pop() ?? '';
}

// --- GoDaddy (most accurate, but fails without IP whitelist on Vercel) ------

async function checkGodaddy(domain: string, creds: GodaddyCreds): Promise<Availability> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(
      `${GODADDY_API_BASE}?domain=${encodeURIComponent(domain)}&checkType=FAST`,
      {
        signal: ctrl.signal,
        headers: { Authorization: `sso-key ${creds.key}:${creds.secret}`, Accept: 'application/json' },
        cache: 'no-store',
      },
    );
    if (!res.ok) return 'unknown';
    const data = (await res.json()) as { available?: boolean };
    if (data.available === true) return 'available';
    if (data.available === false) return 'taken';
    return 'unknown';
  } catch {
    return 'unknown';
  } finally {
    clearTimeout(t);
  }
}

// --- RDAP (free, works from any IP, unreliable on some TLDs) ----------------

async function checkRdap(domain: string): Promise<Availability> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${RDAP_BASE}${encodeURIComponent(domain)}`, {
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
    clearTimeout(t);
  }
}

// --- Domainr (serverless-safe secondary confirmation) -----------------------

async function checkDomainr(domain: string): Promise<Availability> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${DOMAINR_BASE}${encodeURIComponent(domain)}`, {
      signal: ctrl.signal,
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) return 'unknown';
    const data = (await res.json()) as { status?: { domain: string; status: string }[] };
    const entry = data.status?.find((s) => s.domain.toLowerCase() === domain.toLowerCase());
    if (!entry) return 'unknown';
    // Domainr status codes: "undelegated inactive" / "available" → available
    // "active" / "inactive" (when registered) → taken
    const s = entry.status.toLowerCase();
    if (s.includes('available') || s.includes('undelegated inactive')) return 'available';
    if (s.includes('active') || s.includes('inactive') || s.includes('reserved')) return 'taken';
    return 'unknown';
  } catch {
    return 'unknown';
  } finally {
    clearTimeout(t);
  }
}

// --- Composite check --------------------------------------------------------

async function checkOne(domain: string, godaddy?: GodaddyCreds): Promise<Availability> {
  // Try GoDaddy first if credentials present
  if (godaddy) {
    const gd = await checkGodaddy(domain, godaddy);
    if (gd !== 'unknown') return gd;
    // GoDaddy failed (likely IP whitelist issue) — fall through to RDAP+Domainr
  }

  const rdap = await checkRdap(domain);

  // For TLDs where RDAP is known to lie, require Domainr to confirm "available"
  if (rdap === 'available' && RDAP_UNRELIABLE_TLDS.has(tldOf(domain))) {
    const domainr = await checkDomainr(domain);
    // Both must agree it's available, or treat as unknown (safe default)
    return domainr === 'available' ? 'available' : 'unknown';
  }

  return rdap;
}

// --- Public API -------------------------------------------------------------

export async function checkAvailability(
  domains: string[],
  godaddy?: GodaddyCreds,
): Promise<Map<string, Availability>> {
  const result = new Map<string, Availability>();
  let cursor = 0;

  async function worker() {
    while (cursor < domains.length) {
      const i = cursor++;
      result.set(domains[i], await checkOne(domains[i], godaddy));
    }
  }

  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, domains.length) }, worker));
  return result;
}
