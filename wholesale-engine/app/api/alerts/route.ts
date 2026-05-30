import { NextResponse } from 'next/server';
import { getDb } from '@/lib/db';
import { alerts } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { unixNow } from '@/lib/utils';

export async function GET() {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: true, alerts: [] });
    const rows = await db.select().from(alerts).orderBy(alerts.createdAt);
    return NextResponse.json({ ok: true, alerts: rows });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const db = await getDb();
    if (!db) return NextResponse.json({ ok: false, error: 'Database not configured — set DB_PATH or TURSO_DATABASE_URL' }, { status: 503 });

    const body = (await req.json()) as {
      email: string; market: string; minScore?: number;
      maxPrice?: number; frequency?: string;
    };
    if (!body.email || !body.market) {
      return NextResponse.json({ ok: false, error: 'email and market are required' }, { status: 400 });
    }

    const [row] = await db.insert(alerts).values({
      email: body.email,
      market: body.market,
      minScore: body.minScore ?? 75,
      maxPrice: body.maxPrice ?? null,
      frequency: body.frequency ?? 'daily',
      active: true,
      createdAt: unixNow(),
    }).returning();

    return NextResponse.json({ ok: true, alert: row });
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

    await db.delete(alerts).where(eq(alerts.id, id));
    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
