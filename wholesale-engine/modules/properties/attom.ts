import type { RawProperty, DistressSignal } from './types';

type AttomAddress = { line1?: string; locality?: string; countrySubd?: string; postal1?: string };
type AttomBuilding = {
  rooms?: { bedroomsTotal?: number; bathsFull?: number };
  size?: { livingSize?: number };
  construction?: { yearBuilt?: number };
};
type AttomSale = { amount?: { saleAmt?: number } };
type AttomAssessment = { assessed?: { assdTtlValue?: number } };
type AttomProperty = {
  identifier?: string | number;
  address?: AttomAddress;
  building?: AttomBuilding;
  sale?: AttomSale;
  assessment?: AttomAssessment;
  preforeclosure?: { recordingDate?: string };
  taxlien?: { recordingDate?: string };
};

export async function fetchAttomProperties(
  query: { market?: string; zipCodes?: string[] },
  apiKey: string,
): Promise<RawProperty[]> {
  try {
    const zip = query.zipCodes?.[0] ?? '';
    if (!zip) return [];

    const res = await fetch(
      `https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/snapshot?postalcode=${zip}&propertytype=SFR&pagesize=25`,
      {
        headers: { apikey: apiKey, accept: 'application/json' },
        signal: AbortSignal.timeout(8000),
        cache: 'no-store',
      },
    );
    if (!res.ok) return [];

    const data = (await res.json()) as { property?: AttomProperty[] };
    const props = Array.isArray(data.property) ? data.property : [];

    return props.map((prop, i) => {
      const distressSignals: DistressSignal[] = [];
      if (prop.preforeclosure?.recordingDate) distressSignals.push('pre-foreclosure');
      if (prop.taxlien?.recordingDate) distressSignals.push('tax-lien');

      return {
        id: `attom-${String(prop.identifier ?? i)}`,
        address: prop.address?.line1 ?? '',
        city: prop.address?.locality ?? '',
        state: prop.address?.countrySubd ?? '',
        zip: prop.address?.postal1 ?? zip,
        price: prop.sale?.amount?.saleAmt ?? 0,
        bedrooms: prop.building?.rooms?.bedroomsTotal ?? 0,
        bathrooms: prop.building?.rooms?.bathsFull ?? 0,
        sqft: prop.building?.size?.livingSize ?? 0,
        yearBuilt: prop.building?.construction?.yearBuilt ?? 0,
        propertyType: 'SFR' as const,
        daysOnMarket: 0,
        priceReductions: 0,
        source: 'attom' as const,
        distressSignals,
        taxAssessedValue: prop.assessment?.assessed?.assdTtlValue ?? 0,
      };
    });
  } catch {
    return [];
  }
}
