import type { RawProperty } from './types';

export async function fetchRentcastProperties(
  query: { market?: string; zipCodes?: string[] },
  apiKey: string,
): Promise<RawProperty[]> {
  try {
    const zip = query.zipCodes?.[0] ?? '';
    const cityState = query.market ?? '';
    const [city, state] = cityState.split(',').map(s => s.trim());

    const params = new URLSearchParams({ limit: '25', propertyType: 'Single Family' });
    if (zip) params.set('zipCode', zip);
    else if (city && state) { params.set('city', city); params.set('state', state); }
    else return [];

    const res = await fetch(`https://api.rentcast.io/v1/listings/sale?${params}`, {
      headers: { 'X-Api-Key': apiKey, Accept: 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) return [];

    const data = (await res.json()) as unknown[];
    if (!Array.isArray(data)) return [];

    return data.map((p: unknown, i) => {
      const prop = p as Record<string, unknown>;
      return {
        id: `rentcast-${String(prop.id ?? i)}`,
        address: String(prop.formattedAddress ?? ''),
        city: String(prop.city ?? ''),
        state: String(prop.state ?? ''),
        zip: String(prop.zipCode ?? ''),
        price: Number(prop.price ?? 0),
        bedrooms: Number(prop.bedrooms ?? 0),
        bathrooms: Number(prop.bathrooms ?? 0),
        sqft: Number(prop.squareFootage ?? 0),
        yearBuilt: Number(prop.yearBuilt ?? 0),
        propertyType: 'SFR' as const,
        daysOnMarket: Number(prop.daysOnMarket ?? 0),
        priceReductions: 0,
        source: 'rentcast' as const,
        distressSignals: [],
        estimatedRent: Number(prop.rentEstimate ?? 0),
        lastSoldDate: String(prop.lastSaleDate ?? ''),
        lastSoldPrice: Number(prop.lastSalePrice ?? 0),
      };
    });
  } catch {
    return [];
  }
}
