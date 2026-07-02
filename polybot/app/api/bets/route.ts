import { NextResponse } from "next/server";
import { randomUUID } from "crypto";
import { desc } from "drizzle-orm";
import { getDb } from "@/lib/db";
import { bets } from "@/lib/db/schema";
import { toClientBet } from "@/lib/db/serialize";

export const dynamic = "force-dynamic";

/** GET /api/bets — full track record, newest first. */
export async function GET() {
  try {
    const db = await getDb();
    const rows = await db.select().from(bets).orderBy(desc(bets.placedAt));
    return NextResponse.json({ bets: rows.map(toClientBet) });
  } catch (err) {
    console.error("[polybot] GET /api/bets error:", err);
    return NextResponse.json({ error: "load failed" }, { status: 500 });
  }
}

/** POST /api/bets — record a new (paper or manual) bet. */
export async function POST(req: Request) {
  try {
    const body = await req.json();
    const err = validate(body);
    if (err) return NextResponse.json({ error: err }, { status: 400 });

    const db = await getDb();
    const row = {
      id: randomUUID(),
      marketId: String(body.marketId),
      question: String(body.question),
      type: String(body.type),
      auto: Boolean(body.auto),
      legs: JSON.stringify(body.legs),
      stake: Number(body.stake),
      expectedReturn: Number(body.expectedReturn),
      expectedProfit: Number(body.expectedProfit),
      status: "open" as const,
      actualProfit: null,
      placedAt: Date.now(),
      resolvedAt: null,
      note: body.note ? String(body.note) : null,
    };
    await db.insert(bets).values(row);
    return NextResponse.json({ bet: toClientBet(row) }, { status: 201 });
  } catch (err) {
    console.error("[polybot] POST /api/bets error:", err);
    return NextResponse.json({ error: "create failed" }, { status: 500 });
  }
}

function validate(b: any): string | null {
  if (!b || typeof b !== "object") return "body required";
  if (!b.marketId || !b.question || !b.type) return "marketId, question, type required";
  if (!Array.isArray(b.legs) || b.legs.length === 0) return "legs required";
  for (const k of ["stake", "expectedReturn", "expectedProfit"]) {
    if (!Number.isFinite(Number(b[k]))) return `${k} must be a number`;
  }
  return null;
}
