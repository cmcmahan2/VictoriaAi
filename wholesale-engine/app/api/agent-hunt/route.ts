import { NextResponse } from 'next/server';
import { searchProperties } from '@/modules/properties/search';
import { scorePropertiesWithClaude, type ScoredProperty } from '@/modules/scoring/claude-scorer';
import { buildDealAnalysis, buildMarketSummary } from '@/modules/deals/analysis';
import { parseBuyBox } from '@/modules/agent/parse';
import { getMockMarkets } from '@/modules/properties/mock';
import { loadEnv } from '@/lib/env';
import type { DealAnalysis } from '@/modules/deals/analysis';
import type { RawProperty, SearchFilters } from '@/modules/properties/types';

export const maxDuration = 60;
const TIMEOUT_MS = 55_000;
// Cap per-market property volume so multi-market scoring stays within budget.
const PER_MARKET_LIMIT = 12;
// Each scanned market with a live key = 1 RentCast request. Cap the sweep so a
// single agent run doesn't burn the free-tier monthly quota (~50 requests).
const MAX_LIVE_MARKETS = 6;
// Total properties sent to Claude per agent run, scored in sequential batches.
const AGENT_SCORE_LIMIT = 36;
const SCORE_BATCH = 12;

// Score a large set in sequential batches. Claude limits concurrent connections,
// so firing one call per market in parallel trips a 429 — batching serially
// keeps us under that limit while staying within each call's token budget.
async function scoreInBatches(
  props: RawProperty[],
  apiKey: string | undefined,
): Promise<{ scores: Map<string, Partial<ScoredProperty>>; inputTokens: number }> {
  const merged = new Map<string, Partial<ScoredProperty>>();
  let inputTokens = 0;
  for (let i = 0; i < props.length; i += SCORE_BATCH) {
    const batch = props.slice(i, i + SCORE_BATCH);
    const { scores, usage } = await scorePropertiesWithClaude(batch, apiKey);
    for (const [k, v] of scores) merged.set(k, v);
    inputTokens += usage.inputTokens;
  }
  return { scores: merged, inputTokens };
}

type AgentResult = {
  analyses: DealAnalysis[];
  marketSummary: ReturnType<typeof buildMarketSummary>;
  meta: {
    market: string;
    propertyCount: number;
    sources: Record<string, number>;
    usedMock: boolean;
    hasClaude: boolean;
    durationMs: number;
    agent: {
      summary: string;
      usedAi: boolean;
      marketsScanned: number;
      totalScanned: number;
      profitableFound: number;
      minProfit: number | null;
      topMarkets: { market: string; count: number }[];
    };
  };
};

export async function POST(req: Request) {
  try {
    const { text } = (await req.json().catch(() => ({}))) as { text?: string };
    if (!text || !text.trim()) {
      return NextResponse.json({ ok: false, error: 'Describe the kind of deals you want.' }, { status: 400 });
    }

    const env = loadEnv();
    const result = await Promise.race([
      runAgent(text, env),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('Agent hunt timed out — try narrower criteria')), TIMEOUT_MS),
      ),
    ]);

    return NextResponse.json({ ok: true, ...result });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/agent-hunt] Error:', message);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

async function runAgent(text: string, env: ReturnType<typeof loadEnv>): Promise<AgentResult> {
  const t0 = Date.now();

  // 1. Understand the buy box
  const { parsed, usedAi } = await parseBuyBox(text, env.ANTHROPIC_API_KEY);
  const minProfit = parsed.minProfit ?? null;

  // 2. Decide which markets to scan. If the buyer named one, lead with it but
  // still sweep the other strong markets so the agent surfaces the best deals
  // wherever they are.
  const allMarkets = getMockMarkets();
  const markets = parsed.market
    ? [parsed.market, ...allMarkets.filter(m => m !== parsed.market)]
    : allMarkets;

  const serverFilters: SearchFilters = {
    minPrice: parsed.minPrice ?? undefined,
    maxPrice: parsed.maxPrice ?? undefined,
    minBedrooms: parsed.minBedrooms ?? undefined,
    propertyTypes: parsed.propertyTypes.length ? parsed.propertyTypes : undefined,
    maxDaysOnMarket: parsed.maxDaysOnMarket ?? undefined,
    requireDistressSignals: parsed.requireDistressSignals || undefined,
  };

  // 3a. Search markets in parallel (network fetches are safe concurrently). When
  // a live data key is present, limit the sweep to protect the RentCast quota.
  const hasLiveKey = !!(env.RENTCAST_API_KEY || env.ZILLOW_API_KEY || env.ATTOM_API_KEY);
  const scanMarkets = hasLiveKey ? markets.slice(0, MAX_LIVE_MARKETS) : markets;

  const sources: Record<string, number> = {};
  let usedMock = false;

  const perMarketProps = await Promise.all(
    scanMarkets.map(async (market) => {
      const { properties, sources: src, usedMock: mock } = await searchProperties(
        { market, filters: serverFilters },
        { ZILLOW_API_KEY: env.ZILLOW_API_KEY, ATTOM_API_KEY: env.ATTOM_API_KEY, RENTCAST_API_KEY: env.RENTCAST_API_KEY },
      );
      if (mock) usedMock = true;
      for (const [k, v] of Object.entries(src)) sources[k] = (sources[k] ?? 0) + v;
      return properties.slice(0, PER_MARKET_LIMIT);
    }),
  );

  // 3b. Flatten, cap the total, and score in sequential batches (one Claude call
  // at a time) so we never trip the concurrent-connection rate limit.
  const allProps = perMarketProps.flat().slice(0, AGENT_SCORE_LIMIT);
  const { scores, inputTokens } = await scoreInBatches(allProps, env.ANTHROPIC_API_KEY);
  const allAnalyses = allProps.map(p => buildDealAnalysis(p, scores.get(p.id) ?? {}, 0.70));
  const totalScanned = allAnalyses.length;

  // 4. Keep only deals worth pursuing: viable (profitable at list, or strong
  // score with equity) and clearing the buyer's profit floor + score floor.
  const winners = allAnalyses.filter(a => {
    if (!a.isViableDeal) return false;
    if (minProfit != null && a.projectedProfit < minProfit) return false;
    if (parsed.minScore != null && a.wholesaleScore < parsed.minScore) return false;
    return true;
  });

  // 5. Rank: highest projected profit first, then score
  winners.sort((a, b) => b.projectedProfit - a.projectedProfit || b.wholesaleScore - a.wholesaleScore);
  const top = winners.slice(0, 60);

  // Which markets produced the most winners
  const marketCounts = new Map<string, number>();
  for (const a of top) {
    const key = `${a.property.city}, ${a.property.state}`;
    marketCounts.set(key, (marketCounts.get(key) ?? 0) + 1);
  }
  const topMarkets = [...marketCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([market, count]) => ({ market, count }));

  return {
    analyses: top,
    marketSummary: buildMarketSummary(top),
    meta: {
      market: parsed.market ? `Agent · ${scanMarkets.length} markets (lead: ${parsed.market})` : `Agent · ${scanMarkets.length} markets`,
      propertyCount: top.length,
      sources,
      usedMock,
      hasClaude: inputTokens > 0,
      durationMs: Date.now() - t0,
      agent: {
        summary: parsed.summary,
        usedAi,
        marketsScanned: scanMarkets.length,
        totalScanned,
        profitableFound: winners.length,
        minProfit,
        topMarkets,
      },
    },
  };
}
