import { NextResponse } from 'next/server';
import { searchProperties } from '@/modules/properties/search';
import { scorePropertiesWithClaude } from '@/modules/scoring/claude-scorer';
import { buildDealAnalysis, buildMarketSummary } from '@/modules/deals/analysis';
import { getDb } from '@/lib/db';
import { searchSessions, properties as propertiesTable } from '@/lib/db/schema';
import { loadEnv } from '@/lib/env';
import { unixNow } from '@/lib/utils';
import type { SearchQuery } from '@/modules/properties/types';

export const maxDuration = 60;
const TIMEOUT_MS = 30_000;

export async function POST(req: Request) {
  try {
    const env = loadEnv();
    const body = (await req.json().catch(() => ({}))) as SearchQuery;

    if (!body.market && (!body.zipCodes || body.zipCodes.length === 0)) {
      return NextResponse.json(
        { ok: false, error: 'Provide a market (e.g. "Memphis, TN") or zip codes.' },
        { status: 400 },
      );
    }

    // Normalize maoPercentage at the boundary
    if (body.filters?.maoPercentage !== undefined && body.filters.maoPercentage > 1) {
      body.filters.maoPercentage = body.filters.maoPercentage / 100;
    }

    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Property search timed out — try again')), TIMEOUT_MS),
    );

    const result = await Promise.race([
      runPipeline(body, env),
      timeoutPromise,
    ]);

    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/properties] Error:', message);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

async function runPipeline(query: SearchQuery, env: ReturnType<typeof loadEnv>) {
  const t0 = Date.now();

  // Stage 1: Search
  const { properties, sources, usedMock } = await searchProperties(query, {
    ZILLOW_API_KEY: env.ZILLOW_API_KEY,
    ATTOM_API_KEY: env.ATTOM_API_KEY,
    RENTCAST_API_KEY: env.RENTCAST_API_KEY,
  });

  // Stage 2: Score with Claude (or mock scores if no API key)
  const { scores, usage } = await scorePropertiesWithClaude(properties, env.ANTHROPIC_API_KEY);

  // Stage 3: Build deal analyses
  const maoPercentage = query.filters?.maoPercentage ?? 0.70;
  const analyses = properties.map(p => buildDealAnalysis(p, scores.get(p.id) ?? {}, maoPercentage));
  const marketSummary = buildMarketSummary(analyses);

  // Stage 4: Persist to DB (best-effort)
  try {
    const db = await getDb();
    if (db) {
      const [session] = await db.insert(searchSessions).values({
        market: query.market ?? query.zipCodes?.join(',') ?? '',
        zipCodes: query.zipCodes?.join(','),
        filters: JSON.stringify(query.filters ?? {}),
        propertyCount: analyses.length,
        createdAt: unixNow(),
      }).returning({ id: searchSessions.id });

      const sessionId = session?.id;
      if (sessionId) {
        for (const a of analyses) {
          await db.insert(propertiesTable).values({
            sessionId,
            externalId: a.property.id,
            address: a.property.address,
            city: a.property.city,
            state: a.property.state,
            zip: a.property.zip,
            price: a.property.price,
            bedrooms: a.property.bedrooms,
            bathrooms: a.property.bathrooms,
            sqft: a.property.sqft,
            yearBuilt: a.property.yearBuilt,
            propertyType: a.property.propertyType,
            daysOnMarket: a.property.daysOnMarket,
            priceReductions: a.property.priceReductions,
            source: a.property.source,
            distressSignals: JSON.stringify(a.property.distressSignals),
            wholesaleScore: a.wholesaleScore,
            arvEstimate: a.arvEstimate,
            repairEstimate: a.repairEstimate,
            mao: a.mao,
            projectedProfit: a.projectedProfit,
            equitySpread: a.equitySpread,
            scoreSummary: a.scoreSummary,
            scoredAt: unixNow(),
            discoveredAt: unixNow(),
          });
        }
      }
    }
  } catch (dbErr) {
    console.warn('[api/properties] DB persist skipped:', dbErr instanceof Error ? dbErr.message : dbErr);
  }

  return {
    analyses,
    marketSummary,
    meta: {
      market: query.market ?? query.zipCodes?.join(', ') ?? '',
      propertyCount: analyses.length,
      sources,
      usedMock,
      hasClaude: !!env.ANTHROPIC_API_KEY,
      durationMs: Date.now() - t0,
      usage,
    },
  };
}

export async function GET() {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: true, sessions: [] });

    const sessions = await db.select().from(searchSessions);
    return NextResponse.json({ ok: true, sessions });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
