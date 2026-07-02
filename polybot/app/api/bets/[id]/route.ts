import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { getDb } from "@/lib/db";
import { bets } from "@/lib/db/schema";
import { toClientBet } from "@/lib/db/serialize";

export const dynamic = "force-dynamic";

/**
 * PATCH /api/bets/:id — resolve a bet ({ status: "won" | "lost" }).
 * A true arb wins regardless of outcome; "lost" records a busted leg (one
 * side didn't fill), which costs the unmatched stake.
 */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  try {
    const body = await req.json();
    const status = body?.status;
    if (status !== "won" && status !== "lost") {
      return NextResponse.json({ error: "status must be won|lost" }, { status: 400 });
    }

    const db = await getDb();
    const existing = (await db.select().from(bets).where(eq(bets.id, params.id)))[0];
    if (!existing) return NextResponse.json({ error: "not found" }, { status: 404 });

    const actualProfit = status === "won" ? existing.expectedProfit : -existing.stake;
    await db
      .update(bets)
      .set({ status, actualProfit, resolvedAt: Date.now() })
      .where(eq(bets.id, params.id));

    const updated = (await db.select().from(bets).where(eq(bets.id, params.id)))[0];
    return NextResponse.json({ bet: toClientBet(updated) });
  } catch (err) {
    console.error("[polybot] PATCH /api/bets/:id error:", err);
    return NextResponse.json({ error: "update failed" }, { status: 500 });
  }
}

/** DELETE /api/bets/:id — remove a bet from the record. */
export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  try {
    const db = await getDb();
    await db.delete(bets).where(eq(bets.id, params.id));
    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error("[polybot] DELETE /api/bets/:id error:", err);
    return NextResponse.json({ error: "delete failed" }, { status: 500 });
  }
}
