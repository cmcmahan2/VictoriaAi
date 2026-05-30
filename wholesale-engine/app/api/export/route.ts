import { NextResponse } from 'next/server';
import type { DealAnalysis } from '@/modules/deals/analysis';

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { analyses: DealAnalysis[] };
    const analyses = Array.isArray(body.analyses) ? body.analyses : [];

    const headers = [
      'Address', 'City', 'State', 'Zip', 'List Price', 'ARV Estimate',
      'MAO', 'Equity Spread', 'Profit @ List', 'Wholesale Score',
      'Distress Signals', 'Days on Market', 'Bedrooms', 'Bathrooms',
      'Sqft', 'Year Built', 'Source',
    ];

    const rows = analyses.map(a => {
      const p = a.property;
      return [
        `"${p.address}"`, `"${p.city}"`, p.state, p.zip,
        p.price, a.arvEstimate, a.mao, a.equitySpread, a.projectedProfit,
        a.wholesaleScore, `"${p.distressSignals.join('; ')}"`,
        p.daysOnMarket, p.bedrooms, p.bathrooms, p.sqft, p.yearBuilt, p.source,
      ].join(',');
    });

    const csv = [headers.join(','), ...rows].join('\n');

    return new NextResponse(csv, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename="wholesale-deals.csv"',
      },
    });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
