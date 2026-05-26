import type { RawSignal } from './hackernews';

// Broad spread across commercial verticals — not just tech/AI. These are
// subreddits where real consumer and business demand surfaces, which is where
// easy-to-sell domains come from.
const DEFAULT_SUBREDDITS = [
  // Tech / startup
  'startups',
  'SaaS',
  'artificial',
  'technology',
  'cryptocurrency',
  // Business / money / side hustles
  'Entrepreneur',
  'smallbusiness',
  'personalfinance',
  'sidehustle',
  'ecommerce',
  // Health / wellness / lifestyle
  'fitness',
  'nutrition',
  'skincareaddiction',
  'mentalhealth',
  // Home / food / hobbies
  'food',
  'HomeImprovement',
  'gardening',
  'gaming',
  'travel',
  // Consumer / culture
  'BuyItForLife',
  'pets',
  'parenting',
  'fashion',
];

type RedditPost = {
  data: {
    title: string;
    url: string;
    score: number;
    subreddit: string;
  };
};

async function getAccessToken(clientId: string, clientSecret: string): Promise<string> {
  const res = await fetch('https://www.reddit.com/api/v1/access_token', {
    method: 'POST',
    headers: {
      Authorization: `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString('base64')}`,
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': 'DomainFlipEngine/0.1',
    },
    body: 'grant_type=client_credentials',
  });
  const data = await res.json() as { access_token?: string };
  if (!data.access_token) throw new Error('Reddit auth failed');
  return data.access_token;
}

export async function fetchReddit(
  clientId: string | undefined,
  clientSecret: string | undefined,
  subreddits: string[] = DEFAULT_SUBREDDITS,
): Promise<RawSignal[]> {
  if (!clientId || !clientSecret) {
    console.log('[trends] Reddit skipped — no credentials');
    return [];
  }

  try {
    const token = await getAccessToken(clientId, clientSecret);
    const results: RawSignal[] = [];

    await Promise.allSettled(
      subreddits.map(async (sub) => {
        const res = await fetch(`https://oauth.reddit.com/r/${sub}/rising?limit=25`, {
          headers: {
            Authorization: `Bearer ${token}`,
            'User-Agent': 'DomainFlipEngine/0.1',
          },
        });
        if (!res.ok) return;
        const data = await res.json() as { data?: { children?: RedditPost[] } };
        const posts = data.data?.children || [];
        for (const post of posts) {
          results.push({
            source: `reddit/r/${sub}`,
            title: post.data.title,
            url: post.data.url,
            score: post.data.score,
            content: post.data.title,
          });
        }
      }),
    );

    return results;
  } catch (err) {
    console.warn('[trends] Reddit fetch failed:', (err as Error).message);
    return [];
  }
}
