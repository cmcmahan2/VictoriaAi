import { NextResponse } from 'next/server';
import { getDb } from '@/lib/db';
import { savedSearches } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { unixNow } from '@/lib/utils';

export async function GET() {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: true, searches: [] });
    const rows = await db.select().from(savedSearches).orderBy(savedSearches.createdAt);
    return NextResponse.json({ ok: true, searches: rows });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: false, error: 'Database not configured' }, { status: 503 });

    const body = (await req.json()) as { name: string; market: string; zipCodes?: string[]; filters?: object };
    if (!body.name || !body.market) {
      return NextResponse.json({ ok: false, error: 'name and market are required' }, { status: 400 });
    }

    const [row] = await db.insert(savedSearches).values({
      name: body.name,
      market: body.market,
      zipCodes: body.zipCodes?.join(',') ?? null,
      filters: JSON.stringify(body.filters ?? {}),
      createdAt: unixNow(),
    }).returning();

    return NextResponse.json({ ok: true, search: row });
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

    await db.delete(savedSearches).where(eq(savedSearches.id, id));
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
