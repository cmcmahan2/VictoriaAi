export type RawSignal = {
  source: string;
  title: string;
  url: string;
  score: number;
  content: string;
};

const HN_BASE = 'https://hacker-news.firebaseio.com/v0';
const CUTOFF_HOURS = 72;  // wider window catches slower-burning trends
const MIN_SCORE = 50;     // lower bar catches early risers before they peak
const MAX_ITEMS = 150;

export async function fetchHackerNews(): Promise<RawSignal[]> {
  const cutoff = Math.floor(Date.now() / 1000) - CUTOFF_HOURS * 3600;

  const [topIds, bestIds] = await Promise.all([
    fetch(`${HN_BASE}/topstories.json`, { next: { revalidate: 1800 } })
      .then((r) => r.json() as Promise<number[]>),
    fetch(`${HN_BASE}/beststories.json`, { next: { revalidate: 1800 } })
      .then((r) => r.json() as Promise<number[]>),
  ]);

  const ids = Array.from(new Set([...topIds.slice(0, MAX_ITEMS), ...bestIds.slice(0, MAX_ITEMS)]));

  const items = await Promise.allSettled(
    ids.map((id) =>
      fetch(`${HN_BASE}/item/${id}.json`)
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
}
