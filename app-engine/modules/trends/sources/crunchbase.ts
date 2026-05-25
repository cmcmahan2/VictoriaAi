import type { RawSignal } from './hackernews';

const CB_NEWS_URL = 'https://news.crunchbase.com/';

export async function fetchCrunchbase(): Promise<RawSignal[]> {
  try {
    const { load } = await import('cheerio');

    const res = await fetch(CB_NEWS_URL, {
      headers: { 'User-Agent': 'Mozilla/5.0 DomainFlipEngine/0.1' },
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) throw new Error(`Crunchbase ${res.status}`);

    const html = await res.text();
    const $ = load(html);
    const results: RawSignal[] = [];

    $('article, .article, [class*="post"]').each((_, el) => {
      const titleEl = $(el).find('h2, h3, [class*="title"]').first();
      const title = titleEl.text().trim();
      const linkEl = titleEl.find('a').first() || $(el).find('a').first();
      const href = linkEl.attr('href') || '';
      const excerpt = $(el).find('p, [class*="excerpt"], [class*="description"]').first().text().trim();

      if (title && title.length > 10) {
        results.push({
          source: 'crunchbase-news',
          title,
          url: href.startsWith('http') ? href : `https://news.crunchbase.com${href}`,
          score: 30,
          content: `${title} ${excerpt}`,
        });
      }
    });

    return results.slice(0, 20);
  } catch (err) {
    console.warn('[trends] Crunchbase fetch failed:', (err as Error).message);
    return [];
  }
}
