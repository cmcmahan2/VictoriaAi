import type { RawProperty, DistressSignal, PropertyType } from './types';

const MARKETS: Record<string, { city: string; state: string; zips: string[]; medianPrice: number }> = {
  'Memphis, TN':    { city: 'Memphis',     state: 'TN', zips: ['38103','38104','38105','38106','38109'], medianPrice: 145000 },
  'Detroit, MI':    { city: 'Detroit',     state: 'MI', zips: ['48201','48202','48206','48207','48210'], medianPrice: 90000  },
  'Cleveland, OH':  { city: 'Cleveland',   state: 'OH', zips: ['44101','44102','44103','44104','44105'], medianPrice: 110000 },
  'Baltimore, MD':  { city: 'Baltimore',   state: 'MD', zips: ['21201','21202','21205','21213','21215'], medianPrice: 155000 },
  'Kansas City, MO':{ city: 'Kansas City', state: 'MO', zips: ['64101','64108','64110','64111','64120'], medianPrice: 175000 },
  'Indianapolis, IN':{ city: 'Indianapolis',state: 'IN', zips: ['46201','46202','46203','46218','46219'], medianPrice: 195000 },
  'Birmingham, AL': { city: 'Birmingham',  state: 'AL', zips: ['35201','35203','35204','35205','35212'], medianPrice: 125000 },
  'St. Louis, MO':  { city: 'St. Louis',   state: 'MO', zips: ['63101','63103','63104','63107','63113'], medianPrice: 135000 },
};

const STREET_NAMES = [
  'Oak','Maple','Pine','Cedar','Elm','Walnut','Birch','Cherry','Spruce','Willow',
  'Lincoln','Jefferson','Madison','Jackson','Adams','Monroe','Grant','Sherman',
  'Main','Market','Church','Park','Lake','Hill','Ridge','Valley','Creek','Brook',
];
const STREET_TYPES = ['St','Ave','Blvd','Dr','Ln','Way','Ct','Pl','Rd','Ter'];
const DISTRESS_POOL: DistressSignal[] = [
  'pre-foreclosure','tax-lien','high-dom','price-reduction','vacant',
  'estate-sale','divorce','absentee-owner','out-of-state-owner','deferred-maintenance','below-market',
];

function rng(seed: number, max: number): number {
  const x = Math.sin(seed) * 10000;
  return Math.floor((x - Math.floor(x)) * max);
}

function generateAddress(idx: number): string {
  const num = 100 + rng(idx * 7, 9900);
  const street = STREET_NAMES[rng(idx * 3, STREET_NAMES.length)];
  const type = STREET_TYPES[rng(idx * 11, STREET_TYPES.length)];
  return `${num} ${street} ${type}`;
}

function pickDistressSignals(idx: number, forceHigh: boolean): DistressSignal[] {
  const count = forceHigh ? 2 + rng(idx, 3) : rng(idx * 2, 3);
  const signals: DistressSignal[] = [];
  const used = new Set<number>();
  for (let i = 0; i < count; i++) {
    let pick = rng(idx * (i + 1) * 13, DISTRESS_POOL.length);
    while (used.has(pick)) pick = (pick + 1) % DISTRESS_POOL.length;
    used.add(pick);
    signals.push(DISTRESS_POOL[pick]);
  }
  return signals;
}

export function generateMockProperties(query: {
  market?: string;
  zipCodes?: string[];
}, count = 20): RawProperty[] {
  const marketKey = query.market
    ? Object.keys(MARKETS).find(k => k.toLowerCase().includes(query.market!.toLowerCase()))
    : null;

  const market = marketKey ? MARKETS[marketKey] : MARKETS['Memphis, TN'];
  const zips = (query.zipCodes && query.zipCodes.length > 0)
    ? query.zipCodes
    : market.zips;

  const propertyTypes: PropertyType[] = ['SFR','SFR','SFR','MFR','Condo','Townhouse'];
  const properties: RawProperty[] = [];

  for (let i = 0; i < count; i++) {
    const seed = i + 1;
    const zip = zips[rng(seed * 5, zips.length)];
    const basePrice = market.medianPrice;
    const priceVariance = (rng(seed * 17, 60) - 20) / 100;
    const price = Math.round(basePrice * (1 + priceVariance) / 1000) * 1000;

    const bedrooms = 2 + rng(seed * 3, 4);
    const bathrooms = 1 + rng(seed * 7, 3) * 0.5;
    const sqft = 800 + rng(seed * 11, 1600);
    const yearBuilt = 1945 + rng(seed * 13, 65);
    const dom = rng(seed * 19, 180);
    const priceReductions = rng(seed * 23, 4);
    const forceHigh = i % 4 === 0;
    const distressSignals = pickDistressSignals(seed, forceHigh);

    const propType = propertyTypes[rng(seed * 29, propertyTypes.length)];
    const ownerTypes = ['owner-occupied', 'absentee', 'corporate', 'estate'] as const;
    const ownerType = ownerTypes[rng(seed * 37, ownerTypes.length)];

    const lastSoldYearsAgo = 1 + rng(seed * 41, 15);
    const lastSoldYear = new Date().getFullYear() - lastSoldYearsAgo;
    const lastSoldPrice = Math.round(price * (0.6 + rng(seed * 43, 50) / 100) / 1000) * 1000;

    properties.push({
      id: `mock-${market.state}-${zip}-${i}`,
      address: generateAddress(seed),
      city: market.city,
      state: market.state,
      zip,
      price,
      bedrooms,
      bathrooms,
      sqft,
      yearBuilt,
      propertyType: propType,
      daysOnMarket: dom,
      priceReductions,
      source: 'mock',
      distressSignals,
      estimatedRent: Math.round((price * 0.008 + rng(seed * 47, 200)) / 50) * 50,
      lastSoldDate: `${lastSoldYear}-${String(1 + rng(seed * 53, 12)).padStart(2, '0')}-15`,
      lastSoldPrice,
      ownerType,
      taxAssessedValue: Math.round(price * (0.7 + rng(seed * 59, 30) / 100) / 1000) * 1000,
    });
  }

  return properties;
}

export function getMockMarkets(): string[] {
  return Object.keys(MARKETS);
}
