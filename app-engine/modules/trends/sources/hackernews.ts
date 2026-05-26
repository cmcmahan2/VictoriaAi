export type RawSignal = {
  source: string;
  title: string;
  url: string;
  score: number;
  content: string;
};

const HN_BASE = 'https://hacker-news.firebaseio.com/v0';
const CUTOFF_HOURS = 72;
const MIN_SCORE = 50;
const MAX_ITEMS = 150;

export async function fetchHackerNews(): Promise<RawSignal[]> {
  try {
    const cutoff = Math.floor(Date.now() / 1000) - CUTOFF_HOURS * 3600;

    // No `next: { revalidate }` — that option is only valid in RSC GET fetches,
    // not inside POST route handlers, and throws in Next.js internals.
    const [topIds, bestIds] = await Promise.all([
      fetch(`${HN_BASE}/topstories.json`, { signal: AbortSignal.timeout(8000) })
        .then((r) => r.json() as Promise<number[]>),
      fetch(`${HN_BASE}/beststories.json`, { signal: AbortSignal.timeout(8000) })
        .then((r) => r.json() as Promise<number[]>),
    ]);

    const ids = Array.from(new Set([
      ...(Array.isArray(topIds) ? topIds.slice(0, MAX_ITEMS) : []),
      ...(Array.isArray(bestIds) ? bestIds.slice(0, MAX_ITEMS) : []),
    ]));

    const items = await Promise.allSettled(
      ids.map((id) =>
        fetch(`${HN_BASE}/item/${id}.json`, { signal: AbortSignal.timeout(5000) })
          .then((r) => r.json())
          .catch(() => null),
      ),
    );

    return items
      .filter((r): r is PromiseFulfilledResult<any> => r.status === 'fulfilled' && r.value)
      .map((r) => r.value)
      .filter((item) => item.score >= MIN_SCORE && item.time > cutoff && item.title)
      .map((item) => ({
        source: 'hackernews',
        title: item.title as string,
        url: item.url || `https://news.ycombinator.com/item?id=${item.id}`,
        score: item.score as number,
        content: item.title as string,
      }));
  } catch (err) {
    console.warn('[trends] HackerNews fetch failed:', (err as Error).message);
    return [];
  }
}
