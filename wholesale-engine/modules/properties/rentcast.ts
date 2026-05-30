import type { RawProperty, DistressSignal, PropertyType } from './types';

const RENTCAST_PROPERTY_TYPE: Record<string, PropertyType> = {
  'Single Family': 'SFR',
  'Multi-Family': 'MFR',
  'Condo': 'Condo',
  'Townhouse': 'Townhouse',
  'Land': 'Land',
  'Manufactured': 'SFR',
  'Apartment': 'MFR',
};

/**
 * Fetches real for-sale listings from RentCast. Returns [] on any failure so the
 * caller can fall back to mock data — but logs *why* it failed (bad key, quota,
 * no results) so the dev terminal makes the cause obvious instead of silently
 * showing demo data.
 */
export async function fetchRentcastProperties(
  query: { market?: string; zipCodes?: string[] },
  apiKey: string,
): Promise<RawProperty[]> {
  const zip = query.zipCodes?.[0] ?? '';
  const cityState = query.market ?? '';
  const [city, state] = cityState.split(',').map((s) => s.trim());

  const params = new URLSearchParams({ limit: '50', status: 'Active' });
  if (zip) params.set('zipCode', zip);
  else if (city && state) {
    params.set('city', city);
    params.set('state', state);
  } else {
    console.warn('[rentcast] No zip or city/state in query — skipping');
    return [];
  }

  const url = `https://api.rentcast.io/v1/listings/sale?${params}`;

  try {
    const res = await fetch(url, {
      headers: { 'X-Api-Key': apiKey, Accept: 'application/json' },
      cache: 'no-store',
      // Never let a slow RentCast response hang the whole search.
      signal: AbortSignal.timeout(12_000),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      const hint =
        res.status === 401 ? ' (invalid or missing API key)' :
        res.status === 429 ? ' (rate limit / monthly quota exceeded — free tier is 50 req/mo)' :
        '';
      console.error(`[rentcast] ${res.status} ${res.statusText}${hint} for ${cityState || zip}. ${body.slice(0, 200)}`);
      return [];
    }

    const data = (await res.json()) as unknown[];
    if (!Array.isArray(data) || data.length === 0) {
      console.warn(`[rentcast] 0 listings returned for ${cityState || zip}`);
      return [];
    }

    const properties = data.map((p: unknown, i): RawProperty => {
      const prop = p as Record<string, unknown>;
      const price = Number(prop.price ?? 0);
      const daysOnMarket = Number(prop.daysOnMarket ?? 0);
      const lastSalePrice = Number(prop.lastSalePrice ?? 0);
      const formattedAddress = String(prop.formattedAddress ?? '');

      // Derive honest distress signals from real listing data only.
      const distressSignals: DistressSignal[] = [];
      if (daysOnMarket > 90) distressSignals.push('high-dom');
      if (lastSalePrice > 0 && price > 0 && price < lastSalePrice) distressSignals.push('below-market');

      const propertyType =
        RENTCAST_PROPERTY_TYPE[String(prop.propertyType ?? '')] ?? 'SFR';

      return {
        id: `rentcast-${String(prop.id ?? i)}`,
        address: formattedAddress,
        city: String(prop.city ?? city ?? ''),
        state: String(prop.state ?? state ?? ''),
        zip: String(prop.zipCode ?? zip ?? ''),
        price,
        bedrooms: Number(prop.bedrooms ?? 0),
        bathrooms: Number(prop.bathrooms ?? 0),
        sqft: Number(prop.squareFootage ?? 0),
        yearBuilt: Number(prop.yearBuilt ?? 0),
        propertyType,
        daysOnMarket,
        priceReductions: 0,
        source: 'rentcast' as const,
        distressSignals,
        estimatedRent: Number(prop.rentEstimate ?? 0),
        lastSoldDate: String(prop.lastSaleDate ?? ''),
        lastSoldPrice: lastSalePrice,
        // RentCast has no tax-assessed field on listings; use last sale as a
        // rough value anchor so the scorer can estimate ARV/equity.
        taxAssessedValue: lastSalePrice > 0 ? lastSalePrice : undefined,
        // RentCast doesn't return a listing page URL — let the UI build a Zillow
        // address search from the real address (listingUrl helper handles this).
      };
    });

    console.log(`[rentcast] ✓ ${properties.length} live listings for ${cityState || zip}`);
    return properties;
  } catch (err) {
    console.error(`[rentcast] Request failed for ${cityState || zip}:`, err instanceof Error ? err.message : err);
    return [];
  }
}

// Map our internal property types back to RentCast's AVM vocabulary.
const INTERNAL_TO_RENTCAST_TYPE: Record<PropertyType, string> = {
  SFR: 'Single Family',
  MFR: 'Multi-Family',
  Condo: 'Condo',
  Townhouse: 'Townhouse',
  Land: 'Land',
};

export type AvmComparable = {
  address: string;
  price: number;
  bedrooms: number;
  bathrooms: number;
  sqft: number;
  distance: number;
  daysOld: number;
};

export type AvmResult = {
  value: number;
  rangeLow: number;
  rangeHigh: number;
  comparables: AvmComparable[];
};

/**
 * Fetches a comp-based value estimate (AVM) and comparable sales for a single
 * address from RentCast. COSTS 1 REQUEST against the monthly quota — call this
 * on-demand for a specific property, never in a loop over a search result.
 * Returns null on any failure so the caller can fall back to the estimate.
 */
export async function fetchRentcastAvm(
  input: { address: string; propertyType?: PropertyType; bedrooms?: number; bathrooms?: number; sqft?: number },
  apiKey: string,
): Promise<AvmResult | null> {
  const params = new URLSearchParams({ address: input.address, compCount: '5' });
  const mapped = input.propertyType ? INTERNAL_TO_RENTCAST_TYPE[input.propertyType] : undefined;
  if (mapped) params.set('propertyType', mapped);
  if (input.bedrooms) params.set('bedrooms', String(input.bedrooms));
  if (input.bathrooms) params.set('bathrooms', String(input.bathrooms));
  if (input.sqft) params.set('squareFootage', String(input.sqft));

  const url = `https://api.rentcast.io/v1/avm/value?${params}`;

  try {
    const res = await fetch(url, {
      headers: { 'X-Api-Key': apiKey, Accept: 'application/json' },
      cache: 'no-store',
      signal: AbortSignal.timeout(12_000),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      console.error(`[rentcast-avm] ${res.status} ${res.statusText} for ${input.address}. ${body.slice(0, 200)}`);
      return null;
    }

    const data = (await res.json()) as Record<string, unknown>;
    const value = Number(data.price ?? 0);
    if (!value) {
      console.warn(`[rentcast-avm] No value returned for ${input.address}`);
      return null;
    }

    const compsRaw = Array.isArray(data.comparables) ? data.comparables : [];
    const comparables: AvmComparable[] = compsRaw.slice(0, 5).map((c): AvmComparable => {
      const comp = c as Record<string, unknown>;
      return {
        address: String(comp.formattedAddress ?? ''),
        price: Number(comp.price ?? 0),
        bedrooms: Number(comp.bedrooms ?? 0),
        bathrooms: Number(comp.bathrooms ?? 0),
        sqft: Number(comp.squareFootage ?? 0),
        distance: Number(comp.distance ?? 0),
        daysOld: Number(comp.daysOld ?? 0),
      };
    });

    console.log(`[rentcast-avm] ✓ $${value.toLocaleString()} from ${comparables.length} comps for ${input.address}`);
    return {
      value,
      rangeLow: Number(data.priceRangeLow ?? 0),
      rangeHigh: Number(data.priceRangeHigh ?? 0),
      comparables,
    };
  } catch (err) {
    console.error(`[rentcast-avm] Request failed for ${input.address}:`, err instanceof Error ? err.message : err);
    return null;
  }
}
