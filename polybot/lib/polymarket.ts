import type { OutcomeLeg, RawMarket } from "./types";

/**
 * Data layer for the finder.
 *
 * LIVE mode (POLYMARKET_LIVE=true) pulls from Polymarket's public, keyless
 * APIs: the Gamma API for the market list and the CLOB API for order-book
 * best-ask + depth. No account, no API key, read-only.
 *
 * DEMO mode (default) returns hand-built markets so the UI and the math work
 * with zero network access — useful for development and for environments
 * with a restrictive network policy.
 */

const GAMMA = "https://gamma-api.polymarket.com";
const CLOB = "https://clob.polymarket.com";

export async function getMarkets(): Promise<{ markets: RawMarket[]; source: "live" | "demo" }> {
  if (process.env.POLYMARKET_LIVE === "true") {
    try {
      const markets = await fetchLiveMarkets();
      if (markets.length) return { markets, source: "live" };
    } catch (err) {
      console.error("[polybot] live fetch failed, falling back to demo:", err);
    }
  }
  return { markets: DEMO_MARKETS, source: "demo" };
}

async function fetchLiveMarkets(limit = 60): Promise<RawMarket[]> {
  const res = await fetchWithTimeout(
    `${GAMMA}/markets?active=true&closed=false&liquidity_num_min=500&limit=${limit}`,
    8000,
  );
  if (!res.ok) throw new Error(`gamma ${res.status}`);
  const rows: any[] = await res.json();

  const out: RawMarket[] = [];
  for (const m of rows) {
    const tokenIds: string[] = safeJson(m.clobTokenIds) ?? [];
    const labels: string[] = safeJson(m.outcomes) ?? [];
    if (tokenIds.length < 2 || tokenIds.length !== labels.length) continue;

    const legs = await Promise.all(
      tokenIds.map(async (tid, i): Promise<OutcomeLeg | null> => {
        const book = await getBestAsk(tid);
        if (!book) return null;
        return { label: labels[i], tokenId: tid, askPrice: book.price, askSize: book.size };
      }),
    );
    if (legs.some((l) => l === null)) continue;

    out.push({
      id: String(m.id ?? m.conditionId ?? m.slug),
      type: tokenIds.length === 2 ? "binary" : "multi",
      question: m.question ?? m.title ?? "Untitled market",
      slug: m.slug,
      category: m.category,
      endDate: m.endDate,
      outcomes: legs as OutcomeLeg[],
    });
  }
  return out;
}

async function getBestAsk(tokenId: string): Promise<{ price: number; size: number } | null> {
  try {
    const res = await fetchWithTimeout(`${CLOB}/book?token_id=${tokenId}`, 6000);
    if (!res.ok) return null;
    const book = await res.json();
    const asks: { price: string; size: string }[] = book.asks ?? [];
    if (!asks.length) return null;
    // Polymarket returns asks ascending elsewhere, but sort defensively.
    const best = asks
      .map((a) => ({ price: parseFloat(a.price), size: parseFloat(a.size) }))
      .sort((a, b) => a.price - b.price)[0];
    return best;
  } catch {
    return null;
  }
}

async function fetchWithTimeout(url: string, ms: number): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { signal: ctrl.signal, headers: { Accept: "application/json" } });
  } finally {
    clearTimeout(t);
  }
}

function safeJson<T = any>(v: unknown): T | null {
  if (Array.isArray(v)) return v as T;
  if (typeof v !== "string") return null;
  try {
    return JSON.parse(v) as T;
  } catch {
    return null;
  }
}

// --------------------------------------------------------------------------
// Demo data. A few markets show real (sub-$1) arbs; others are efficiently
// priced (sum >= $1) and get filtered out, so the finder's filtering is
// visible. Numbers are illustrative, in the same shape as live data.
// --------------------------------------------------------------------------
export const DEMO_MARKETS: RawMarket[] = [
  {
    id: "demo-btc-eod",
    type: "binary",
    question: "Will BTC close above $90k on June 30?",
    slug: "btc-above-90k-june-30",
    category: "Crypto",
    endDate: "2026-06-30T23:59:00Z",
    outcomes: [
      { label: "Yes", tokenId: "t-btc-yes", askPrice: 0.61, askSize: 420 },
      { label: "No", tokenId: "t-btc-no", askPrice: 0.37, askSize: 510 },
    ], // sum 0.98 -> 2.04% arb
  },
  {
    id: "demo-cpi",
    type: "binary",
    question: "Will US CPI come in above 3.0% for June?",
    slug: "us-cpi-above-3-june",
    category: "Economics",
    endDate: "2026-07-10T12:30:00Z",
    outcomes: [
      { label: "Yes", tokenId: "t-cpi-yes", askPrice: 0.44, askSize: 300 },
      { label: "No", tokenId: "t-cpi-no", askPrice: 0.52, askSize: 290 },
    ], // sum 0.96 -> 4.17% arb (thin-ish depth)
  },
  {
    id: "demo-fed",
    type: "multi",
    question: "Fed decision at the July FOMC meeting?",
    slug: "fed-july-fomc",
    category: "Economics",
    endDate: "2026-07-29T18:00:00Z",
    outcomes: [
      { label: "Cut 25bps", tokenId: "t-fed-cut25", askPrice: 0.18, askSize: 800 },
      { label: "Hold", tokenId: "t-fed-hold", askPrice: 0.70, askSize: 650 },
      { label: "Hike 25bps", tokenId: "t-fed-hike25", askPrice: 0.07, askSize: 900 },
      { label: "Cut 50bps", tokenId: "t-fed-cut50", askPrice: 0.02, askSize: 950 },
    ], // sum 0.97 -> 3.09% multi-outcome (negRisk) arb
  },
  {
    id: "demo-election-eff",
    type: "binary",
    question: "Will the incumbent win the special election?",
    slug: "incumbent-special-election",
    category: "Politics",
    endDate: "2026-08-15T23:59:00Z",
    outcomes: [
      { label: "Yes", tokenId: "t-inc-yes", askPrice: 0.56, askSize: 1200 },
      { label: "No", tokenId: "t-inc-no", askPrice: 0.46, askSize: 1100 },
    ], // sum 1.02 -> NO arb, filtered out (efficiently priced)
  },
  {
    id: "demo-sports",
    type: "binary",
    question: "Will Panama beat England in the World Cup group stage?",
    slug: "panama-beat-england-wc",
    category: "Sports",
    endDate: "2026-06-27T14:00:00Z",
    outcomes: [
      { label: "Yes", tokenId: "t-pan-yes", askPrice: 0.255, askSize: 240 },
      { label: "No", tokenId: "t-pan-no", askPrice: 0.73, askSize: 260 },
    ], // sum 0.985 -> 1.52% arb
  },
];
