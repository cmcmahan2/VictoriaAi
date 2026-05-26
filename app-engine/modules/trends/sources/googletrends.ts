import type { RawSignal } from './hackernews';

// google-trends-api doesn't have official @types, using dynamic import
export async function fetchGoogleTrends(): Promise<RawSignal[]> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const googleTrends = require('google-trends-api');

    const rawJson: string = await Promise.race([
      googleTrends.dailyTrends({ trendDate: new Date(), geo: 'US' }) as Promise<string>,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('Google Trends timeout')), 8000),
      ),
    ]);

    const parsed = JSON.parse(rawJson) as {
      default?: {
        trendingSearchesDays?: {
          trendingSearches?: {
            title: { query: string };
            formattedTraffic: string;
            articles: { title: string; url: string }[];
          }[];
        }[];
      };
    };

    const searches = parsed.default?.trendingSearchesDays?.[0]?.trendingSearches || [];
    return searches.map((s) => ({
      source: 'google-trends',
      title: s.title.query,
      url: s.articles[0]?.url || '',
      score: parseInt(s.formattedTraffic.replace(/[^0-9]/g, ''), 10) || 0,
      content: [s.title.query, ...s.articles.map((a) => a.title)].join(' '),
    }));
  } catch (err) {
    console.warn('[trends] Google Trends fetch failed:', (err as Error).message);
    return [];
  }
}
