import { NextResponse } from 'next/server';
import { getDb } from '@/lib/db';
import { buyers } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { unixNow } from '@/lib/utils';

export async function GET() {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: true, buyers: [] });
    const rows = await db.select().from(buyers).orderBy(buyers.createdAt);
    return NextResponse.json({ ok: true, buyers: rows });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: false, error: 'Database not configured' }, { status: 503 });

    const body = (await req.json()) as {
      name: string; email?: string; phone?: string;
      markets?: string[]; maxPrice?: number; propertyTypes?: string[]; notes?: string;
    };
    if (!body.name) return NextResponse.json({ ok: false, error: 'name is required' }, { status: 400 });

    const [row] = await db.insert(buyers).values({
      name: body.name,
      email: body.email ?? null,
      phone: body.phone ?? null,
      markets: JSON.stringify(body.markets ?? []),
      maxPrice: body.maxPrice ?? null,
      propertyTypes: JSON.stringify(body.propertyTypes ?? []),
      notes: body.notes ?? null,
      createdAt: unixNow(),
    }).returning();

    return NextResponse.json({ ok: true, buyer: row });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: false, error: 'Database not configured' }, { status: 503 });

    const body = (await req.json()) as {
      id: number; name?: string; email?: string; phone?: string;
      markets?: string[]; maxPrice?: number; propertyTypes?: string[]; notes?: string;
    };
    if (!body.id) return NextResponse.json({ ok: false, error: 'id is required' }, { status: 400 });

    const updates: Partial<typeof buyers.$inferInsert> = {};
    if (body.name !== undefined) updates.name = body.name;
    if (body.email !== undefined) updates.email = body.email;
    if (body.phone !== undefined) updates.phone = body.phone;
    if (body.markets !== undefined) updates.markets = JSON.stringify(body.markets);
    if (body.maxPrice !== undefined) updates.maxPrice = body.maxPrice;
    if (body.propertyTypes !== undefined) updates.propertyTypes = JSON.stringify(body.propertyTypes);
    if (body.notes !== undefined) updates.notes = body.notes;

    await db.update(buyers).set(updates).where(eq(buyers.id, body.id));
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

    await db.delete(buyers).where(eq(buyers.id, id));
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
