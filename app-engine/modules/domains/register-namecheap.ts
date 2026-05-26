// Namecheap domain registration via their XML API.
// https://www.namecheap.com/support/api/methods/domains/create/

export type NamecheapCreds = {
  apiUser: string;
  apiKey: string;
  clientIp: string;
};

export type RegistrationResult =
  | { ok: true; domain: string; orderId: string; transactionId: string }
  | { ok: false; domain: string; error: string };

const NC_API = 'https://api.namecheap.com/xml.response';

function parseError(xml: string): string {
  const match = xml.match(/<Error[^>]*Number="(\d+)"[^>]*>([^<]*)<\/Error>/i);
  if (match) return `[${match[1]}] ${match[2].trim()}`;
  const msgMatch = xml.match(/<Errors>([\s\S]*?)<\/Errors>/i);
  if (msgMatch) return msgMatch[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  return 'Unknown Namecheap error.';
}

// Register a single domain. Returns immediately after order placement — does
// not poll for completion. The caller should surface the orderId for tracking.
export async function registerDomain(
  domain: string,
  creds: NamecheapCreds,
  opts: {
    years?: number;
    // Registrant contact info — Namecheap requires this for ICANN compliance.
    // If omitted, the call will fail. The caller should collect these from the user.
    registrant?: {
      firstName: string;
      lastName: string;
      address1: string;
      city: string;
      stateProvince: string;
      postalCode: string;
      country: string; // 2-letter ISO
      phone: string;   // +1.5555555555
      emailAddress: string;
    };
  } = {},
): Promise<RegistrationResult> {
  const parts = domain.split('.');
  const sld = parts.slice(0, -1).join('.');
  const tld = parts.at(-1) ?? '';

  const params = new URLSearchParams({
    ApiUser: creds.apiUser,
    ApiKey: creds.apiKey,
    UserName: creds.apiUser,
    ClientIp: creds.clientIp,
    Command: 'namecheap.domains.create',
    DomainName: sld,
    TLD: tld,
    Years: String(opts.years ?? 1),
  });

  const r = opts.registrant;
  if (r) {
    const contacts = ['Registrant', 'Tech', 'Admin', 'AuxBilling'] as const;
    for (const role of contacts) {
      params.set(`${role}FirstName`, r.firstName);
      params.set(`${role}LastName`, r.lastName);
      params.set(`${role}Address1`, r.address1);
      params.set(`${role}City`, r.city);
      params.set(`${role}StateProvince`, r.stateProvince);
      params.set(`${role}PostalCode`, r.postalCode);
      params.set(`${role}Country`, r.country);
      params.set(`${role}Phone`, r.phone);
      params.set(`${role}EmailAddress`, r.emailAddress);
    }
  }

  try {
    const res = await fetch(`${NC_API}?${params}`, {
      signal: AbortSignal.timeout(15000),
    });
    const text = await res.text();

    if (text.includes('Status="ERROR"')) {
      return { ok: false, domain, error: parseError(text) };
    }

    const orderMatch = text.match(/OrderID="(\d+)"/i);
    const txMatch = text.match(/TransactionID="(\d+)"/i);

    return {
      ok: true,
      domain,
      orderId: orderMatch?.[1] ?? '',
      transactionId: txMatch?.[1] ?? '',
    };
  } catch (e) {
    return { ok: false, domain, error: `Network error: ${(e as Error).message}` };
  }
}

// Check domain availability via Namecheap (useful as a secondary check
// before attempting registration to get a clear error message).
export async function checkAvailabilityNamecheap(
  domains: string[],
  creds: NamecheapCreds,
): Promise<Map<string, boolean>> {
  const result = new Map<string, boolean>();
  if (domains.length === 0) return result;

  const params = new URLSearchParams({
    ApiUser: creds.apiUser,
    ApiKey: creds.apiKey,
    UserName: creds.apiUser,
    ClientIp: creds.clientIp,
    Command: 'namecheap.domains.check',
    DomainList: domains.join(','),
  });

  try {
    const res = await fetch(`${NC_API}?${params}`, { signal: AbortSignal.timeout(10000) });
    const text = await res.text();

    const matches = text.matchAll(/Domain="([^"]+)"\s+Available="([^"]+)"/gi);
    for (const m of matches) {
      result.set(m[1].toLowerCase(), m[2].toLowerCase() === 'true');
    }
  } catch {
    // Return empty map — RDAP is the primary availability check
  }

  return result;
}
