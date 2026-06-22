import type { RawMarket } from "./types";

/**
 * Price-history candles for the chart view.
 *
 * LIVE mode pulls Polymarket's keyless CLOB prices-history endpoint (a series
 * of {t, p} points for an outcome token) and buckets it into OHLC candles.
 * DEMO mode synthesizes a believable random walk ending near the token's
 * current ask, so the chart renders with zero network access.
 */

export interface Candle {
  time: number; // UNIX seconds (Lightweight Charts UTCTimestamp)
  open: number;
  high: number;
  low: number;
  close: number;
}

const CLOB = "https://clob.polymarket.com";

export async function getCandles(
  tokenId: string,
  currentPrice: number,
  bars = 72,
): Promise<{ candles: Candle[]; source: "live" | "demo" }> {
  if (process.env.POLYMARKET_LIVE === "true") {
    try {
      const candles = await fetchLiveCandles(tokenId, bars);
      if (candles.length) return { candles, source: "live" };
    } catch (err) {
      console.error("[polybot] prices-history fetch failed, using demo:", err);
    }
  }
  return { candles: synthCandles(currentPrice, bars), source: "demo" };
}

async function fetchLiveCandles(tokenId: string, bars: number): Promise<Candle[]> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 7000);
  try {
    // fidelity is the resolution in minutes; 60 = hourly buckets.
    const res = await fetch(`${CLOB}/prices-history?market=${tokenId}&interval=1w&fidelity=60`, {
      signal: ctrl.signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`prices-history ${res.status}`);
    const json = await res.json();
    const points: { t: number; p: number }[] = json.history ?? [];
    return bucketToCandles(points, bars);
  } finally {
    clearTimeout(t);
  }
}

/** Group raw price points into `bars` OHLC candles. */
function bucketToCandles(points: { t: number; p: number }[], bars: number): Candle[] {
  if (points.length === 0) return [];
  const size = Math.max(1, Math.ceil(points.length / bars));
  const out: Candle[] = [];
  for (let i = 0; i < points.length; i += size) {
    const slice = points.slice(i, i + size);
    const prices = slice.map((s) => s.p);
    out.push({
      time: slice[0].t,
      open: prices[0],
      high: Math.max(...prices),
      low: Math.min(...prices),
      close: prices[prices.length - 1],
    });
  }
  return out;
}

/** Deterministic-ish synthetic walk ending near `end`, for demo mode. */
function synthCandles(end: number, bars: number): Candle[] {
  const out: Candle[] = [];
  const now = Math.floor(Date.now() / 1000);
  const step = 3600; // hourly
  let price = clamp(end + (Math.random() - 0.5) * 0.12);
  for (let i = bars - 1; i >= 0; i--) {
    const time = now - i * step;
    // Drift the close toward `end` as we approach now, plus noise.
    const pull = (end - price) * 0.15;
    const open = price;
    const close = clamp(open + pull + (Math.random() - 0.5) * 0.03);
    const high = clamp(Math.max(open, close) + Math.random() * 0.015);
    const low = clamp(Math.min(open, close) - Math.random() * 0.015);
    out.push({ time, open, high, low, close });
    price = close;
  }
  // Snap the final close exactly to the current ask.
  if (out.length) out[out.length - 1].close = end;
  return out;
}

function clamp(n: number) {
  return Math.min(0.99, Math.max(0.01, n));
}

/** Convenience: which token to chart for a market (first outcome by default). */
export function primaryToken(market: RawMarket) {
  return market.outcomes[0];
}
