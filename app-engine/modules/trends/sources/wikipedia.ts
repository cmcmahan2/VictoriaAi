import type { RawSignal } from './hackernews';

// Wikipedia's most-viewed articles for the prior day. Free, keyless, and broad:
// it surfaces what the whole world is paying attention to across every category
// — people, products, events, places, culture — not just tech. A strong signal
// for general consumer demand that domain buyers care about.

const REST_BASE = 'https://api.wikimedia.org/feed/v1/wikipedia/en/featured';

// Administrative / non-commercial pages that dominate the list but are useless
// as naming trends.
const SKIP = [
  'Main_Page',
  'Special:Search',
  'Wikipedia:',
  'Portal:',
  'Special:',
  'Cleopatra', // perennial noise example; generic filter below handles most
];

function isNoise(title: string): boolean {
  if (SKIP.some((s) => title.startsWith(s) || title === s)) return true;
  // Skip "List of ...", dates, and disambiguation-style noise.
  if (/^List_of_/i.test(title)) return true;
  if (/^\d{4}$/.test(title)) return true;
  return false;
}

export async function fetchWikipediaTrends(): Promise<RawSignal[]> {
  try {
    // Yesterday in UTC — today's feed may not be populated yet.
    const d = new Date(Date.now() - 24 * 3600 * 1000);
    const yyyy = d.getUTCFullYear();
    const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(d.getUTCDate()).padStart(2, '0');

    const res = await fetch(`${REST_BASE}/${yyyy}/${mm}/${dd}`, {
      headers: {
        'User-Agent': 'DomainFlipEngine/0.3 (domain trend research)',
        Accept: 'application/json',
      },
      next: { revalidate: 3600 },
    });
    if (!res.ok) return [];

    const data = (await res.json()) as {
      mostread?: {
        articles?: { titles?: { normalized?: string }; title?: string; views?: number }[];
      };
    };

    const articles = data.mostread?.articles || [];
    return articles
      .map((a) => {
        const raw = a.title || '';
        const display = a.titles?.normalized || raw.replace(/_/g, ' ');
        return { raw, display, views: a.views || 0 };
      })
      .filter((a) => a.raw && !isNoise(a.raw))
      .slice(0, 40)
      .map((a) => ({
        source: 'wikipedia',
        title: a.display,
        url: `https://en.wikipedia.org/wiki/${encodeURIComponent(a.raw)}`,
        score: a.views,
        content: a.display,
      }));
  } catch (err) {
    console.warn('[trends] Wikipedia fetch failed:', (err as Error).message);
    return [];
  }
}
