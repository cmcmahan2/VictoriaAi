import { fetchHackerNews } from './sources/hackernews';
import { fetchReddit } from './sources/reddit';
import { fetchProductHunt } from './sources/producthunt';
import { fetchGoogleTrends } from './sources/googletrends';
import { fetchGithubTrending } from './sources/github';
import { fetchYCombinator } from './sources/ycombinator';
import { fetchCrunchbase } from './sources/crunchbase';
import { scoreTrendsWithClaude, type ScoredTrend } from './claude-scorer';
import type { RawSignal } from './sources/hackernews';

export type TrendRunResult = {
  trends: ScoredTrend[];
  signalCount: number;
  sourceBreakdown: Record<string, number>;
  durationMs: number;
};

export async function runTrendIntelligence(env: {
  ANTHROPIC_API_KEY: string;
  REDDIT_CLIENT_ID?: string;
  REDDIT_CLIENT_SECRET?: string;
  PRODUCT_HUNT_TOKEN?: string;
}): Promise<TrendRunResult> {
  const t0 = Date.now();
  console.log('[trends] Starting multi-source intelligence run...');

  // Fetch all sources in parallel — each gracefully returns [] on failure
  const [hn, reddit, ph, gtrends, github, yc, cb] = await Promise.all([
    fetchHackerNews(),
    fetchReddit(env.REDDIT_CLIENT_ID, env.REDDIT_CLIENT_SECRET),
    fetchProductHunt(env.PRODUCT_HUNT_TOKEN),
    fetchGoogleTrends(),
    fetchGithubTrending(),
    fetchYCombinator(),
    fetchCrunchbase(),
  ]);

  const allSignals: RawSignal[] = [...hn, ...reddit, ...ph, ...gtrends, ...github, ...yc, ...cb];

  const sourceBreakdown: Record<string, number> = {};
  for (const s of allSignals) {
    const key = s.source.split('/')[0];
    sourceBreakdown[key] = (sourceBreakdown[key] || 0) + 1;
  }

  console.log(
    `[trends] Collected ${allSignals.length} signals from ${Object.keys(sourceBreakdown).length} sources`,
  );
  console.log('[trends] Source breakdown:', sourceBreakdown);
  console.log('[trends] Sending to Claude for scoring...');

  const trends = await scoreTrendsWithClaude(allSignals, env.ANTHROPIC_API_KEY);

  const durationMs = Date.now() - t0;
  console.log(`[trends] Complete — ${trends.length} trends in ${durationMs}ms`);

  return { trends, signalCount: allSignals.length, sourceBreakdown, durationMs };
}
