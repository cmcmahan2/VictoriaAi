export type PropertyType = 'SFR' | 'MFR' | 'Condo' | 'Townhouse' | 'Land';

export type DistressSignal =
  | 'pre-foreclosure'
  | 'tax-lien'
  | 'high-dom'
  | 'price-reduction'
  | 'vacant'
  | 'estate-sale'
  | 'divorce'
  | 'absentee-owner'
  | 'out-of-state-owner'
  | 'corporate-owned'
  | 'deferred-maintenance'
  | 'below-market';

export type RawProperty = {
  id: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  price: number;
  bedrooms: number;
  bathrooms: number;
  sqft: number;
  yearBuilt: number;
  propertyType: PropertyType;
  daysOnMarket: number;
  priceReductions: number;
  source: 'zillow' | 'attom' | 'rentcast' | 'redfin' | 'mock';
  distressSignals: DistressSignal[];
  estimatedRent?: number;
  lastSoldDate?: string;
  lastSoldPrice?: number;
  ownerType?: 'owner-occupied' | 'absentee' | 'corporate' | 'estate';
  foreclosureStatus?: string;
  taxAssessedValue?: number;
  hoaFee?: number;
};

export type SearchFilters = {
  minPrice?: number;
  maxPrice?: number;
  minBedrooms?: number;
  propertyTypes?: PropertyType[];
  maxDaysOnMarket?: number;
  requireDistressSignals?: boolean;
  /** Decimal between 0 and 1, e.g. 0.70 for the standard 70% rule */
  maoPercentage?: number;
};

export type SearchQuery = {
  market?: string;
  zipCodes?: string[];
  filters?: SearchFilters;
};
