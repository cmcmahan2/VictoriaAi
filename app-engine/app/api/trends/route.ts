import { NextResponse } from 'next/server';
import { runTrendIntelligence } from '@/modules/trends';
import { getDb } from '@/lib/db';
import { trends } from '@/lib/db/schema';
import { unixNow } from '@/lib/utils';
import { loadEnv } from '@/lib/env';

export const maxDuration = 120; // Vercel: 2 min timeout

export async function POST() {
  try {
    const env = loadEnv();
    const result = await runTrendIntelligence({
      ANTHROPIC_API_KEY: env.ANTHROPIC_API_KEY,
      REDDIT_CLIENT_ID: env.REDDIT_CLIENT_ID,
      REDDIT_CLIENT_SECRET: env.REDDIT_CLIENT_SECRET,
      PRODUCT_HUNT_TOKEN: env.PRODUCT_HUNT_TOKEN,
    });

    // Persist to DB
    const db = getDb();
    const now = unixNow();
    const insertedIds: number[] = [];

    for (const trend of result.trends) {
      const inserted = db
        .insert(trends)
        .values({
          name: trend.name,
          velocity: trend.velocity,
          commercialScore: trend.commercialScore,
          sources: JSON.stringify(trend.sources),
          keywords: JSON.stringify(trend.keywords),
          discoveredAt: now,
        })
        .run();
      if (inserted.lastInsertRowid) {
        insertedIds.push(Number(inserted.lastInsertRowid));
      }
    }

    return NextResponse.json({
      ok: true,
      trends: result.trends,
      meta: {
        signalCount: result.signalCount,
        sourceBreakdown: result.sourceBreakdown,
        durationMs: result.durationMs,
        savedTrends: insertedIds.length,
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/trends] Error:', message);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

export async function GET() {
  try {
    const db = getDb();
    const allTrends = db.select().from(trends).all();
    return NextResponse.json({
      ok: true,
      trends: allTrends.map((t) => ({
        ...t,
        sources: JSON.parse(t.sources),
        keywords: JSON.parse(t.keywords),
      })),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
