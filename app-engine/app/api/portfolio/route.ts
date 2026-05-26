import { NextResponse } from 'next/server';
import { eq } from 'drizzle-orm';
import { getDb } from '@/lib/db';
import { ownedDomains } from '@/lib/db/schema';
import { unixNow } from '@/lib/utils';

const ONE_YEAR = 365 * 24 * 3600;

const NO_DB = {
  ok: false,
  error: 'Database not configured. Add TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in Vercel to enable the portfolio.',
} as const;

// List owned domains with summary stats.
export async function GET() {
  try {
    const db = await getDb();
    if (!db) {
      return NextResponse.json({ ok: true, dbConfigured: false, domains: [], summary: null });
    }

    const rows = await db.select().from(ownedDomains);

    const summary = {
      count: rows.length,
      invested: rows.reduce((s, r) => s + (r.costBasis || 0), 0),
      estValue: rows.reduce((s, r) => s + (r.currentValuation || 0), 0),
      realizedProfit: rows
        .filter((r) => r.listingStatus === 'sold')
        .reduce((s, r) => s + (r.netProfit || 0), 0),
    };

    return NextResponse.json({ ok: true, dbConfigured: true, domains: rows, summary });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

// Add a domain to the portfolio.
export async function POST(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json(NO_DB, { status: 400 });

    const body = (await req.json()) as {
      domain?: string;
      registrar?: string;
      costBasis?: number;
      currentValuation?: number;
      renewalCost?: number;
    };

    if (!body.domain) {
      return NextResponse.json({ ok: false, error: 'domain is required' }, { status: 400 });
    }

    const now = unixNow();
    const inserted = await db
      .insert(ownedDomains)
      .values({
        domain: body.domain.toLowerCase(),
        registrar: body.registrar || 'unknown',
        registeredAt: now,
        costBasis: body.costBasis ?? 0,
        currentValuation: body.currentValuation ?? null,
        renewalDate: now + ONE_YEAR,
        renewalCost: body.renewalCost ?? body.costBasis ?? null,
        listingStatus: 'unlisted',
      })
      .onConflictDoNothing()
      .returning();

    if (inserted.length === 0) {
      return NextResponse.json({ ok: false, error: 'Domain is already in your portfolio.' }, { status: 409 });
    }

    return NextResponse.json({ ok: true, domain: inserted[0] });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

// Update a domain: list / unlist / mark sold / update valuation.
export async function PATCH(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json(NO_DB, { status: 400 });

    const body = (await req.json()) as {
      id?: number;
      action?: 'list' | 'unlist' | 'sold' | 'valuation';
      salePrice?: number;
      currentValuation?: number;
    };

    if (!body.id || !body.action) {
      return NextResponse.json({ ok: false, error: 'id and action are required' }, { status: 400 });
    }

    const existing = await db.select().from(ownedDomains).where(eq(ownedDomains.id, body.id));
    if (existing.length === 0) {
      return NextResponse.json({ ok: false, error: 'Domain not found' }, { status: 404 });
    }
    const row = existing[0];

    let patch: Partial<typeof ownedDomains.$inferInsert> = {};
    if (body.action === 'list') {
      patch = { listingStatus: 'listed' };
    } else if (body.action === 'unlist') {
      patch = { listingStatus: 'unlisted' };
    } else if (body.action === 'sold') {
      const salePrice = body.salePrice ?? 0;
      patch = {
        listingStatus: 'sold',
        soldAt: unixNow(),
        salePrice,
        netProfit: salePrice - (row.costBasis || 0),
      };
    } else if (body.action === 'valuation') {
      patch = { currentValuation: body.currentValuation ?? row.currentValuation };
    }

    const updated = await db
      .update(ownedDomains)
      .set(patch)
      .where(eq(ownedDomains.id, body.id))
      .returning();

    return NextResponse.json({ ok: true, domain: updated[0] });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

// Remove a domain from the portfolio.
export async function DELETE(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json(NO_DB, { status: 400 });

    const body = (await req.json()) as { id?: number };
    if (!body.id) {
      return NextResponse.json({ ok: false, error: 'id is required' }, { status: 400 });
    }

    await db.delete(ownedDomains).where(eq(ownedDomains.id, body.id));
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
