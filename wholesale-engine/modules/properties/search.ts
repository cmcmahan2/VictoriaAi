import type { RawProperty, SearchQuery } from './types';
import { fetchZillowProperties } from './zillow';
import { fetchAttomProperties } from './attom';
import { fetchRentcastProperties } from './rentcast';
import { fetchRedfinProperties } from './redfin';
import { generateMockProperties } from './mock';

export type PropertySearchResult = {
  properties: RawProperty[];
  sources: Record<string, number>;
  usedMock: boolean;
};

export async function searchProperties(
  query: SearchQuery,
  env: {
    ZILLOW_API_KEY?: string;
    ATTOM_API_KEY?: string;
    RENTCAST_API_KEY?: string;
  },
): Promise<PropertySearchResult> {
  const sources: Record<string, number> = {};

  // Fetch all live sources in parallel; each returns [] on failure/missing key
  const [zillow, attom, rentcast, redfin] = await Promise.all([
    env.ZILLOW_API_KEY
      ? fetchZillowProperties(query, env.ZILLOW_API_KEY)
      : Promise.resolve<RawProperty[]>([]),
    env.ATTOM_API_KEY
      ? fetchAttomProperties(query, env.ATTOM_API_KEY)
      : Promise.resolve<RawProperty[]>([]),
    env.RENTCAST_API_KEY
      ? fetchRentcastProperties(query, env.RENTCAST_API_KEY)
      : Promise.resolve<RawProperty[]>([]),
    fetchRedfinProperties(query),
  ]);

  if (zillow.length)  sources.zillow  = zillow.length;
  if (attom.length)   sources.attom   = attom.length;
  if (rentcast.length) sources.rentcast = rentcast.length;
  if (redfin.length)  sources.redfin  = redfin.length;

  let allProperties = [...zillow, ...attom, ...rentcast, ...redfin];
  let usedMock = false;

  // Fall back to realistic mock data so the UI always works during dev
  if (allProperties.length === 0) {
    allProperties = generateMockProperties(query, 24);
    sources.mock = allProperties.length;
    usedMock = true;
  }

  // Deduplicate by address
  const seen = new Set<string>();
  const deduped = allProperties.filter(p => {
    const key = `${p.address}-${p.zip}`.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  // Apply filters
  const f = query.filters ?? {};
  const filtered = deduped.filter(p => {
    if (f.minPrice && p.price < f.minPrice) return false;
    if (f.maxPrice && p.price > f.maxPrice) return false;
    if (f.minBedrooms && p.bedrooms < f.minBedrooms) return false;
    if (f.propertyTypes?.length && !f.propertyTypes.includes(p.propertyType)) return false;
    if (f.maxDaysOnMarket && p.daysOnMarket > f.maxDaysOnMarket) return false;
    if (f.requireDistressSignals && p.distressSignals.length === 0) return false;
    return true;
  });

  return { properties: filtered.slice(0, 50), sources, usedMock };
}
