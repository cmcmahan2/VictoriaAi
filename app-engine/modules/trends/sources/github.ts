import type { RawSignal } from './hackernews';

const TRENDING_URL = 'https://github.com/trending';

export async function fetchGithubTrending(): Promise<RawSignal[]> {
  try {
    const { load } = await import('cheerio');

    const res = await fetch(TRENDING_URL, {
      headers: { 'User-Agent': 'Mozilla/5.0 DomainFlipEngine/0.1' },
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) throw new Error(`GitHub trending ${res.status}`);

    const html = await res.text();
    const $ = load(html);
    const results: RawSignal[] = [];

    $('article.Box-row').each((_, el) => {
      const repoLink = $(el).find('h2 a').first();
      const fullName = repoLink.text().trim().replace(/\s+/g, '');
      const description = $(el).find('p').first().text().trim();
      const starsText = $(el).find('[aria-label="star"] + span, .color-fg-muted').last().text().trim();
      const stars = parseInt(starsText.replace(/[^0-9]/g, ''), 10) || 0;

      if (fullName) {
        results.push({
          source: 'github-trending',
          title: fullName,
          url: `https://github.com/${fullName}`,
          score: stars,
          content: `${fullName} ${description}`,
        });
      }
    });

    return results.slice(0, 25);
  } catch (err) {
    console.warn('[trends] GitHub trending fetch failed:', (err as Error).message);
    return [];
  }
}
