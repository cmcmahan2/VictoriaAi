import type { RawSignal } from './hackernews';

const YC_URL = 'https://www.ycombinator.com/companies?batch=W25';

export async function fetchYCombinator(): Promise<RawSignal[]> {
  try {
    const { load } = await import('cheerio');

    const res = await fetch(YC_URL, {
      headers: { 'User-Agent': 'Mozilla/5.0 DomainFlipEngine/0.1' },
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) throw new Error(`YC ${res.status}`);

    const html = await res.text();
    const $ = load(html);
    const results: RawSignal[] = [];

    // YC uses React-rendered content, so try to parse JSON from __NEXT_DATA__
    const nextData = $('#__NEXT_DATA__').text();
    if (nextData) {
      try {
        const parsed = JSON.parse(nextData);
        const companies: { name?: string; one_liner?: string; slug?: string }[] =
          parsed?.props?.pageProps?.companies || [];

        for (const c of companies.slice(0, 50)) {
          if (c.name) {
            results.push({
              source: 'ycombinator',
              title: c.name,
              url: `https://www.ycombinator.com/companies/${c.slug || ''}`,
              score: 50,
              content: `${c.name} ${c.one_liner || ''}`,
            });
          }
        }
        return results;
      } catch {
        // fall through to HTML scraping
      }
    }

    // Fallback: plain HTML scrape
    $('[class*="company"]').each((_, el) => {
      const name = $(el).find('h3, h4, [class*="name"]').first().text().trim();
      const desc = $(el).find('p, [class*="description"]').first().text().trim();
      if (name) {
        results.push({
          source: 'ycombinator',
          title: name,
          url: YC_URL,
          score: 40,
          content: `${name} ${desc}`,
        });
      }
    });

    return results.slice(0, 30);
  } catch (err) {
    console.warn('[trends] YC fetch failed:', (err as Error).message);
    return [];
  }
}
