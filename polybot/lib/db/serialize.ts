import type { BetRow } from "./schema";
import type { TrackedBet } from "@/lib/types";

/** Map a DB row to the client-facing shape (JSON legs, ISO timestamps). */
export function toClientBet(r: BetRow): TrackedBet {
  return {
    id: r.id,
    marketId: r.marketId,
    question: r.question,
    type: r.type as TrackedBet["type"],
    auto: !!r.auto,
    legs: safeParse(r.legs),
    stake: r.stake,
    expectedReturn: r.expectedReturn,
    expectedProfit: r.expectedProfit,
    status: r.status as TrackedBet["status"],
    actualProfit: r.actualProfit ?? undefined,
    placedAt: new Date(r.placedAt).toISOString(),
    resolvedAt: r.resolvedAt ? new Date(r.resolvedAt).toISOString() : undefined,
    note: r.note ?? undefined,
  };
}

function safeParse(s: string): TrackedBet["legs"] {
  try {
    return JSON.parse(s);
  } catch {
    return [];
  }
}
