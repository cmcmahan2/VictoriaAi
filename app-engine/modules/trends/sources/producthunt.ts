import type { RawSignal } from './hackernews';

const PH_API = 'https://api.producthunt.com/v2/api/graphql';

const QUERY = `
  query {
    posts(order: VOTES, postedAfter: "${new Date(Date.now() - 48 * 3600 * 1000).toISOString()}") {
      edges {
        node {
          name
          tagline
          votesCount
          website
          topics { edges { node { name } } }
        }
      }
    }
  }
`;

export async function fetchProductHunt(token: string | undefined): Promise<RawSignal[]> {
  if (!token) {
    console.log('[trends] Product Hunt skipped — no token');
    return [];
  }

  try {
    const res = await fetch(PH_API, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: QUERY }),
    });

    if (!res.ok) throw new Error(`PH API ${res.status}`);

    const data = await res.json() as {
      data?: { posts?: { edges?: { node: { name: string; tagline: string; votesCount: number; website: string } }[] } };
    };

    const edges = data.data?.posts?.edges || [];
    return edges.map((e) => ({
      source: 'producthunt',
      title: `${e.node.name}: ${e.node.tagline}`,
      url: e.node.website || '',
      score: e.node.votesCount,
      content: `${e.node.name} ${e.node.tagline}`,
    }));
  } catch (err) {
    console.warn('[trends] Product Hunt fetch failed:', (err as Error).message);
    return [];
  }
}
