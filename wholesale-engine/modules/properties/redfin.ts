import type { RawProperty } from './types';

type RedfinValue<T> = { value?: T };
type RedfinHome = {
  mlsId?: string | number;
  streetLine?: RedfinValue<string>;
  city?: string;
  state?: string;
  zip?: string;
  price?: RedfinValue<number>;
  beds?: number;
  baths?: number;
  sqFt?: RedfinValue<number>;
  yearBuilt?: RedfinValue<number>;
  dom?: RedfinValue<number>;
};

// Redfin has no official public API. This adapter uses their internal
// search endpoint for research purposes only; returns [] on any error.
export async function fetchRedfinProperties(
  query: { market?: string; zipCodes?: string[] },
): Promise<RawProperty[]> {
  try {
    const location = query.zipCodes?.[0] ?? query.market ?? '';
    if (!location) return [];

    const searchRes = await fetch(
      `https://www.redfin.com/stingray/do/location-autocomplete?location=${encodeURIComponent(location)}&v=2`,
      {
        headers: { 'User-Agent': 'Mozilla/5.0 (research bot)' },
        signal: AbortSignal.timeout(8000),
        cache: 'no-store',
      },
    );
    if (!searchRes.ok) return [];

    const searchText = await searchRes.text();
    const match = searchText.match(/"id":"(\d+)"/);
    if (!match) return [];

    const regionId = match[1];
    const gisRes = await fetch(
      `https://www.redfin.com/stingray/api/gis?al=1&market=national&region_id=${regionId}&region_type=2&status=1&num_homes=25&v=8`,
      {
        headers: { 'User-Agent': 'Mozilla/5.0 (research bot)' },
        signal: AbortSignal.timeout(8000),
        cache: 'no-store',
      },
    );
    if (!gisRes.ok) return [];

    const gisText = await gisRes.text();
    const jsonStart = gisText.indexOf('{');
    if (jsonStart === -1) return [];
    const data = JSON.parse(gisText.slice(jsonStart)) as { payload?: { homes?: RedfinHome[] } };
    const homes = data.payload?.homes ?? [];

    return homes.slice(0, 25).map((home, i) => ({
      id: `redfin-${String(home.mlsId ?? i)}`,
      address: home.streetLine?.value ?? '',
      city: home.city ?? '',
      state: home.state ?? '',
      zip: home.zip ?? '',
      price: home.price?.value ?? 0,
      bedrooms: home.beds ?? 0,
      bathrooms: home.baths ?? 0,
      sqft: home.sqFt?.value ?? 0,
      yearBuilt: home.yearBuilt?.value ?? 0,
      propertyType: 'SFR' as const,
      daysOnMarket: home.dom?.value ?? 0,
      priceReductions: 0,
      source: 'redfin' as const,
      distressSignals: [],
    }));
  } catch {
    return [];
  }
}
