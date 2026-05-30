import type { RawProperty, DistressSignal, PropertyType } from './types';

const MARKETS: Record<string, { city: string; state: string; zips: string[]; medianPrice: number }> = {
  'Memphis, TN':      { city: 'Memphis',      state: 'TN', zips: ['38103','38104','38105','38106','38109'], medianPrice: 145000 },
  'Detroit, MI':      { city: 'Detroit',      state: 'MI', zips: ['48201','48202','48206','48207','48210'], medianPrice: 90000  },
  'Cleveland, OH':    { city: 'Cleveland',    state: 'OH', zips: ['44101','44102','44103','44104','44105'], medianPrice: 110000 },
  'Baltimore, MD':    { city: 'Baltimore',    state: 'MD', zips: ['21201','21202','21205','21213','21215'], medianPrice: 155000 },
  'Kansas City, MO':  { city: 'Kansas City',  state: 'MO', zips: ['64101','64108','64110','64111','64120'], medianPrice: 175000 },
  'Indianapolis, IN': { city: 'Indianapolis', state: 'IN', zips: ['46201','46202','46203','46218','46219'], medianPrice: 195000 },
  'Birmingham, AL':   { city: 'Birmingham',   state: 'AL', zips: ['35201','35203','35204','35205','35212'], medianPrice: 125000 },
  'St. Louis, MO':    { city: 'St. Louis',    state: 'MO', zips: ['63101','63103','63104','63107','63113'], medianPrice: 135000 },
  'Austin, TX':       { city: 'Austin',       state: 'TX', zips: ['78701','78702','78703','78721','78741'], medianPrice: 420000 },
  'Houston, TX':      { city: 'Houston',      state: 'TX', zips: ['77001','77002','77003','77004','77051'], medianPrice: 230000 },
  'Dallas, TX':       { city: 'Dallas',       state: 'TX', zips: ['75201','75202','75203','75210','75215'], medianPrice: 285000 },
  'Atlanta, GA':      { city: 'Atlanta',      state: 'GA', zips: ['30301','30303','30310','30311','30318'], medianPrice: 310000 },
  'Phoenix, AZ':      { city: 'Phoenix',      state: 'AZ', zips: ['85001','85003','85007','85008','85040'], medianPrice: 350000 },
  'Tampa, FL':        { city: 'Tampa',        state: 'FL', zips: ['33601','33602','33603','33605','33610'], medianPrice: 320000 },
  'Charlotte, NC':    { city: 'Charlotte',    state: 'NC', zips: ['28201','28202','28203','28204','28208'], medianPrice: 295000 },
  'Columbus, OH':     { city: 'Columbus',     state: 'OH', zips: ['43201','43202','43203','43204','43205'], medianPrice: 210000 },
  'Jacksonville, FL': { city: 'Jacksonville', state: 'FL', zips: ['32201','32202','32204','32205','32209'], medianPrice: 255000 },
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

function generateAddress(idx: number, marketSeed: number): string {
  // Mix the market into the seed so the same row index produces a different
  // street address in each city (otherwise "7986 Jackson Rd" shows up in every
  // market's results).
  const s = idx * 7 + marketSeed;
  const num = 100 + rng(s * 7, 9900);
  const street = STREET_NAMES[rng(s * 3, STREET_NAMES.length)];
  const type = STREET_TYPES[rng(s * 11, STREET_TYPES.length)];
  return `${num} ${street} ${type}`;
}

// Stable per-market integer so each city's addresses diverge.
function marketSeedFor(city: string, state: string): number {
  const key = `${city}, ${state}`;
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) | 0;
  return Math.abs(h) % 100000;
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
  // Special "Browse All Markets" mode — sample 4 properties from 6 top markets
  if (query.market?.toLowerCase() === 'any') {
    const topMarkets = ['Memphis, TN', 'Detroit, MI', 'Houston, TX', 'Atlanta, GA', 'Indianapolis, IN', 'Birmingham, AL'];
    const results: RawProperty[] = [];
    for (const mkt of topMarkets) {
      results.push(...generateMockProperties({ market: mkt }, 4));
    }
    return results.slice(0, count);
  }

  const marketKey = query.market
    ? Object.keys(MARKETS).find(k => k.toLowerCase().includes(query.market!.toLowerCase()))
    : null;

  const market = marketKey ? MARKETS[marketKey] : MARKETS['Memphis, TN'];
  const zips = (query.zipCodes && query.zipCodes.length > 0)
    ? query.zipCodes
    : market.zips;

  const propertyTypes: PropertyType[] = ['SFR','SFR','SFR','MFR','Condo','Townhouse'];
  const properties: RawProperty[] = [];
  const marketSeed = marketSeedFor(market.city, market.state);

  for (let i = 0; i < count; i++) {
    const seed = i + 1;
    const zip = zips[rng(seed * 5, zips.length)];

    const bedrooms = 2 + rng(seed * 3, 4);
    const bathrooms = 1 + rng(seed * 7, 3) * 0.5;
    const sqft = 800 + rng(seed * 11, 1600);
    const yearBuilt = 1945 + rng(seed * 13, 65);

    // "Base value" ≈ what the home is worth in its current condition for the
    // neighborhood, scaled by size around the market median.
    const sizeFactor = 0.75 + (sqft / 2400) * 0.6;          // 0.75–1.35 by sqft
    const valueVariance = (rng(seed * 17, 40) - 20) / 100;  // ±20%
    const baseValue = Math.round(market.medianPrice * sizeFactor * (1 + valueVariance) / 1000) * 1000;

    // Roughly 45% of listings are genuine wholesale opportunities: distressed
    // and priced well below value. The rest are retail-priced (won't pencil out).
    const isDeal = rng(seed * 61, 100) < 45;
    const distressSignals = pickDistressSignals(seed, isDeal);

    let price: number;
    if (isDeal) {
      // Motivated seller: 15–40% below value (60%–85% of baseValue) — realistic
      // wholesale discount range; still leaves margin after repairs and assignment fee
      const discount = 0.60 + rng(seed * 67, 25) / 100;
      price = Math.round(baseValue * discount / 1000) * 1000;
    } else {
      // Retail: 92%–115% of value → little to no wholesale margin
      const markup = 0.92 + rng(seed * 71, 23) / 100;
      price = Math.round(baseValue * markup / 1000) * 1000;
    }

    // Distressed deals tend to sit longer; retail listings move faster.
    const dom = isDeal ? 45 + rng(seed * 19, 150) : rng(seed * 19, 70);
    const priceReductions = isDeal ? 1 + rng(seed * 23, 3) : rng(seed * 23, 2);

    const propType = propertyTypes[rng(seed * 29, propertyTypes.length)];
    const ownerTypes = isDeal
      ? (['absentee', 'estate', 'corporate', 'absentee'] as const)
      : (['owner-occupied', 'owner-occupied', 'absentee', 'owner-occupied'] as const);
    const ownerType = ownerTypes[rng(seed * 37, ownerTypes.length)];

    const lastSoldYearsAgo = 1 + rng(seed * 41, 15);
    const lastSoldYear = new Date().getFullYear() - lastSoldYearsAgo;
    const lastSoldPrice = Math.round(baseValue * (0.55 + rng(seed * 43, 40) / 100) / 1000) * 1000;

    properties.push({
      id: `mock-${market.state}-${zip}-${i}`,
      address: generateAddress(seed, marketSeed),
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
      estimatedRent: Math.round((baseValue * 0.008 + rng(seed * 47, 200)) / 50) * 50,
      lastSoldDate: `${lastSoldYear}-${String(1 + rng(seed * 53, 12)).padStart(2, '0')}-15`,
      lastSoldPrice,
      ownerType,
      // Assessed value tracks the home's real value, not the (discounted) list price,
      // so distressed deals show strong ARV / equity.
      taxAssessedValue: Math.round(baseValue * (0.9 + rng(seed * 59, 20) / 100) / 1000) * 1000,
    });
  }

  return properties;
}

export function getMockMarkets(): string[] {
  return Object.keys(MARKETS);
}
