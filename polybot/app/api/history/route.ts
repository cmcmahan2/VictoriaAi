import { NextResponse } from "next/server";
import { getCandles } from "@/lib/priceHistory";

export const dynamic = "force-dynamic";

/**
 * GET /api/history?token=<tokenId>&price=<currentAsk>
 * Returns OHLC candles for one outcome token (live or demo).
 */
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const token = searchParams.get("token");
  const price = parseFloat(searchParams.get("price") ?? "0.5");
  if (!token) return NextResponse.json({ error: "token required" }, { status: 400 });

  try {
    const { candles, source } = await getCandles(token, Number.isFinite(price) ? price : 0.5);
    return NextResponse.json({ source, candles });
  } catch (err) {
    console.error("[polybot] /api/history error:", err);
    return NextResponse.json({ error: "history failed" }, { status: 500 });
  }
}
