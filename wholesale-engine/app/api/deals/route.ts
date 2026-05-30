import { NextResponse } from 'next/server';
import { getDb } from '@/lib/db';
import { deals } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { unixNow } from '@/lib/utils';

const VALID_STATUSES = [
  'lead', 'contacted', 'offer-sent', 'under-contract', 'assigned', 'closed', 'dead',
] as const;

export async function GET() {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: true, deals: [] });
    const rows = await db.select().from(deals).orderBy(deals.updatedAt);
    return NextResponse.json({ ok: true, deals: rows });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: false, error: 'Database not configured' }, { status: 503 });

    const body = (await req.json()) as {
      externalId: string; address: string; city: string; state: string; zip: string;
      price: number; propertyType?: string; wholesaleScore?: number; arvEstimate?: number;
      mao?: number; projectedProfit?: number; source?: string; listingUrl?: string;
    };
    if (!body.externalId || !body.address) {
      return NextResponse.json({ ok: false, error: 'externalId and address are required' }, { status: 400 });
    }

    // Don't duplicate a property that's already in the pipeline — return the existing row.
    const existing = await db.select().from(deals).where(eq(deals.externalId, body.externalId));
    if (existing.length > 0) {
      return NextResponse.json({ ok: true, deal: existing[0], alreadyTracked: true });
    }

    const now = unixNow();
    const [row] = await db.insert(deals).values({
      externalId: body.externalId,
      address: body.address,
      city: body.city ?? '',
      state: body.state ?? '',
      zip: body.zip ?? '',
      price: body.price ?? 0,
      propertyType: body.propertyType ?? null,
      wholesaleScore: body.wholesaleScore ?? null,
      arvEstimate: body.arvEstimate ?? null,
      mao: body.mao ?? null,
      projectedProfit: body.projectedProfit ?? null,
      source: body.source ?? null,
      listingUrl: body.listingUrl ?? null,
      status: 'lead',
      notes: null,
      createdAt: now,
      updatedAt: now,
    }).returning();

    return NextResponse.json({ ok: true, deal: row });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: false, error: 'Database not configured' }, { status: 503 });

    const body = (await req.json()) as { id: number; status?: string; notes?: string };
    if (!body.id) return NextResponse.json({ ok: false, error: 'id is required' }, { status: 400 });

    const updates: Partial<typeof deals.$inferInsert> = { updatedAt: unixNow() };
    if (body.status !== undefined) {
      if (!(VALID_STATUSES as readonly string[]).includes(body.status)) {
        return NextResponse.json({ ok: false, error: 'invalid status' }, { status: 400 });
      }
      updates.status = body.status;
    }
    if (body.notes !== undefined) updates.notes = body.notes;

    await db.update(deals).set(updates).where(eq(deals.id, body.id));
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: false, error: 'Database not configured' }, { status: 503 });

    const { searchParams } = new URL(req.url);
    const id = Number(searchParams.get('id'));
    if (!id) return NextResponse.json({ ok: false, error: 'id required' }, { status: 400 });

    await db.delete(deals).where(eq(deals.id, id));
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
