import { NextResponse } from "next/server";
import { getMarkets } from "@/lib/polymarket";
import { findArbs } from "@/lib/arbitrage";

// Always run fresh; arbs are time-sensitive and must not be cached.
export const dynamic = "force-dynamic";

/**
 * GET /api/arbs?bankroll=100&minRoi=0.5
 * Scans Polymarket (live or demo) for internal arbitrage and returns the
 * profitable opportunities, best net-ROI first.
 */
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const bankroll = clampNum(searchParams.get("bankroll"), 0, 0, 1_000_000);
  const minRoi = clampNum(searchParams.get("minRoi"), 0, 0, 100);
  const feePct = clampNum(
    searchParams.get("fee") ?? process.env.POLYMARKET_FEE,
    0,
    0,
    0.2,
  );

  try {
    const { markets, source } = await getMarkets();
    const arbs = findArbs(markets, { feePct, bankroll, minRoiPct: minRoi });
    return NextResponse.json({
      source,
      scanned: markets.length,
      found: arbs.length,
      feePct,
      asOf: new Date().toISOString(),
      arbs,
    });
  } catch (err) {
    console.error("[polybot] /api/arbs error:", err);
    return NextResponse.json({ error: "scan failed" }, { status: 500 });
  }
}

function clampNum(v: string | null | undefined, dflt: number, min: number, max: number) {
  const n = v == null ? NaN : parseFloat(v);
  if (Number.isNaN(n)) return dflt;
  return Math.min(max, Math.max(min, n));
}
