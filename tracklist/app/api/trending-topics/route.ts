import { NextResponse } from "next/server";

interface RedditPost {
  data: {
    id: string;
    title: string;
    score: number;
    num_comments: number;
    subreddit: string;
    permalink: string;
    created_utc: number;
    author: string;
    url: string;
  };
}

async function fetchSubreddit(sub: string) {
  try {
    const res = await fetch(`https://www.reddit.com/r/${sub}/hot.json?limit=8`, {
      headers: { "User-Agent": "tracklist-app/1.0" },
      next: { revalidate: 300 },
    });
    if (!res.ok) return [];
    const json = await res.json();
    return (json.data?.children as RedditPost[]).map((p) => ({
      id: p.data.id,
      title: p.data.title,
      url: `https://reddit.com${p.data.permalink}`,
      score: p.data.score,
      comments: p.data.num_comments,
      subreddit: p.data.subreddit,
      created: p.data.created_utc,
    }));
  } catch {
    return [];
  }
}

export async function GET() {
  const subreddits = ["Music", "hiphopheads", "indieheads", "popheads", "rnb", "metal"];

  // Pick 2 random subreddits to mix up the content
  const shuffled = [...subreddits].sort(() => Math.random() - 0.5).slice(0, 2);

  const results = await Promise.allSettled(shuffled.map(fetchSubreddit));

  const posts = results
    .flatMap((r) => (r.status === "fulfilled" ? r.value : []))
    .sort((a, b) => b.score - a.score)
    .slice(0, 10);

  return NextResponse.json({ posts, subreddits: shuffled });
}
