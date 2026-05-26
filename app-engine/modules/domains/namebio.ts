// NameBio historical sale comps — used to anchor Claude valuations to real data.

export type NameBioComp = {
  domain: string;
  price: number;
  date: string;
  venue: string;
};

export type NameBioResult = {
  comps: NameBioComp[];
  avgSalePrice: number | null;
  medianSalePrice: number | null;
};

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

// Fetch comps for a keyword from NameBio. Returns null on failure so the
// caller can degrade gracefully.
export async function fetchNameBioComps(
  keyword: string,
  apiKey: string,
  limit = 10,
): Promise<NameBioResult | null> {
  try {
    const url = new URL('https://namebio.com/api/v2/search');
    url.searchParams.set('q', keyword);
    url.searchParams.set('apikey', apiKey);
    url.searchParams.set('limit', String(limit));

    const res = await fetch(url.toString(), {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(8000),
      cache: 'no-store',
    });

    if (!res.ok) return null;

    const data = (await res.json()) as {
      sales?: Array<{ domain?: string; price?: number; date?: string; venue?: string }>;
    };

    const comps: NameBioComp[] = (data.sales ?? [])
      .filter((s) => typeof s.price === 'number' && s.price > 0)
      .map((s) => ({
        domain: s.domain ?? '',
        price: s.price!,
        date: s.date ?? '',
        venue: s.venue ?? '',
      }));

    const prices = comps.map((c) => c.price);
    return {
      comps,
      avgSalePrice: prices.length > 0 ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length) : null,
      medianSalePrice: median(prices),
    };
  } catch {
    return null;
  }
}

// Derive a simple keyword from a domain name for comp searching
// e.g. "cursorflow.com" → "cursorflow", "aicode.io" → "aicode"
export function domainToKeyword(domain: string): string {
  return domain.split('.')[0] ?? domain;
}
