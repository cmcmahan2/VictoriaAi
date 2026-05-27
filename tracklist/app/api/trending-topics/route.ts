import { NextResponse } from "next/server";

interface RedditPost {
  data: {
    id: string;
    title: string;
    url: string;
    score: number;
    num_comments: number;
    subreddit: string;
    permalink: string;
    thumbnail: string;
    created_utc: number;
    selftext: string;
    author: string;
  };
}

export async function GET() {
  try {
    const subreddits = ["music", "hiphopheads", "indieheads", "popheads"];
    const chosen = subreddits[Math.floor(Math.random() * subreddits.length)];

    const res = await fetch(
      `https://www.reddit.com/r/${chosen}/hot.json?limit=15`,
      {
        headers: { "User-Agent": "tracklist-app/1.0" },
        next: { revalidate: 300 },
      }
    );

    if (!res.ok) throw new Error("Reddit unavailable");
    const json = await res.json();

    const posts = (json.data?.children as RedditPost[])
      .map((p) => ({
        id: p.data.id,
        title: p.data.title,
        url: `https://reddit.com${p.data.permalink}`,
        score: p.data.score,
        comments: p.data.num_comments,
        subreddit: p.data.subreddit,
        author: p.data.author,
        created: p.data.created_utc,
      }))
      .filter((p) => !p.title.includes("[DISCUSSION]") || p.comments > 20)
      .slice(0, 8);

    return NextResponse.json({ posts, subreddit: chosen });
  } catch {
    return NextResponse.json({ posts: [], subreddit: "music" });
  }
}
