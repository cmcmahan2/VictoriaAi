import type { RawProperty } from './types';

export async function fetchZillowProperties(
  query: { market?: string; zipCodes?: string[] },
  apiKey: string,
): Promise<RawProperty[]> {
  // Zillow's official API (Bridge Interactive) requires MLS data partner approval.
  // RapidAPI hosts an unofficial Zillow scraper; structure shown below for when
  // the user obtains a key. Falls through to [] so the mock layer takes over.
  try {
    const location = query.zipCodes?.join(',') ?? query.market ?? '';
    const res = await fetch(
      `https://zillow-com1.p.rapidapi.com/propertyExtendedSearch?location=${encodeURIComponent(location)}&status_type=ForSale&home_type=Houses`,
      {
        headers: {
          'X-RapidAPI-Key': apiKey,
          'X-RapidAPI-Host': 'zillow-com1.p.rapidapi.com',
        },
        cache: 'no-store',
      },
    );
    if (!res.ok) return [];

    const data = (await res.json()) as { props?: unknown[] };
    const props = Array.isArray(data.props) ? data.props : [];

    return props.slice(0, 30).map((p: unknown, i) => {
      const prop = p as Record<string, unknown>;
      return {
        id: `zillow-${String(prop.zpid ?? i)}`,
        address: String(prop.address ?? ''),
        city: String(prop.city ?? ''),
        state: String(prop.state ?? ''),
        zip: String(prop.zipcode ?? ''),
        price: Number(prop.price ?? 0),
        bedrooms: Number(prop.bedrooms ?? 0),
        bathrooms: Number(prop.bathrooms ?? 0),
        sqft: Number(prop.livingArea ?? 0),
        yearBuilt: Number(prop.yearBuilt ?? 0),
        propertyType: 'SFR' as const,
        daysOnMarket: Number(prop.daysOnZillow ?? 0),
        priceReductions: Number(prop.priceReduction ?? 0) > 0 ? 1 : 0,
        source: 'zillow' as const,
        distressSignals: [],
        estimatedRent: Number(prop.rentZestimate ?? 0),
        lastSoldDate: String(prop.lastSoldDate ?? ''),
        lastSoldPrice: Number(prop.lastSoldPrice ?? 0),
      };
    });
  } catch {
    return [];
  }
}
