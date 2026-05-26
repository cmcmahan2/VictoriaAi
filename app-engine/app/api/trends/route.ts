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

    // Persist to DB. Best-effort: on read-only/serverless filesystems the
    // write can fail, but a successful scan should still return its trends.
    const insertedIds: number[] = [];
    try {
      const db = await getDb();
      const now = unixNow();

      if (db) {
        for (const trend of result.trends) {
          const inserted = await db
            .insert(trends)
            .values({
              name: trend.name,
              velocity: trend.velocity,
              commercialScore: trend.commercialScore,
              sources: JSON.stringify(trend.sources),
              keywords: JSON.stringify(trend.keywords),
              discoveredAt: now,
            })
            .returning({ id: trends.id });
          if (inserted[0]?.id) {
            insertedIds.push(inserted[0].id);
          }
        }
      }
    } catch (dbErr) {
      const m = dbErr instanceof Error ? dbErr.message : 'Unknown DB error';
      console.warn('[api/trends] Persist skipped:', m);
    }

    return NextResponse.json({
      ok: true,
      trends: result.trends,
      meta: {
        signalCount: result.signalCount,
        sourceBreakdown: result.sourceBreakdown,
        durationMs: result.durationMs,
        savedTrends: insertedIds.length,
        usage: result.usage,
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
    const db = await getDb();
    if (!db) {
      return NextResponse.json({ ok: true, trends: [] });
    }
    const allTrends = await db.select().from(trends);
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
