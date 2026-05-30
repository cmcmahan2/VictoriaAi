import { NextResponse } from 'next/server';
import { fetchRentcastAvm } from '@/modules/properties/rentcast';
import { loadEnv } from '@/lib/env';
import type { PropertyType } from '@/modules/properties/types';

// On-demand comp-based ARV for a single property. Each call costs 1 RentCast
// request, so this is user-initiated (a button), never run over a search result.
export async function POST(req: Request) {
  try {
    const env = loadEnv();
    if (!env.RENTCAST_API_KEY) {
      return NextResponse.json(
        { ok: false, error: 'Real ARV needs a RentCast API key (set RENTCAST_API_KEY).' },
        { status: 503 },
      );
    }

    const body = (await req.json()) as {
      address: string; city?: string; state?: string; zip?: string;
      propertyType?: PropertyType; bedrooms?: number; bathrooms?: number; sqft?: number;
      price: number; repairEstimate?: number; maoPercentage?: number;
    };
    if (!body.address) {
      return NextResponse.json({ ok: false, error: 'address is required' }, { status: 400 });
    }

    const fullAddress = [body.address, body.city, body.state, body.zip].filter(Boolean).join(', ');
    const avm = await fetchRentcastAvm(
      {
        address: fullAddress,
        propertyType: body.propertyType,
        bedrooms: body.bedrooms,
        bathrooms: body.bathrooms,
        sqft: body.sqft,
      },
      env.RENTCAST_API_KEY,
    );

    if (!avm) {
      return NextResponse.json(
        { ok: false, error: 'No comp-based value available for this address.' },
        { status: 404 },
      );
    }

    const pct = body.maoPercentage && body.maoPercentage <= 1 ? body.maoPercentage : 0.70;
    const repair = body.repairEstimate ?? 0;
    const arv = avm.value;
    const mao = Math.max(0, Math.round(arv * pct - repair));
    const equitySpread = Math.round(arv - body.price);
    const projectedProfit = Math.round(mao - body.price);

    return NextResponse.json({
      ok: true,
      arv,
      rangeLow: avm.rangeLow,
      rangeHigh: avm.rangeHigh,
      comparables: avm.comparables,
      compCount: avm.comparables.length,
      mao,
      equitySpread,
      projectedProfit,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
