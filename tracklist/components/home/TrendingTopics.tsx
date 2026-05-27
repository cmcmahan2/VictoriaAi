"use client";

import { useEffect, useState } from "react";

interface Topic {
  id: string;
  title: string;
  url: string;
  score: number;
  comments: number;
  subreddit: string;
}

function timeAgo(ts: number) {
  const diff = Date.now() / 1000 - ts;
  const h = Math.floor(diff / 3600);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function TrendingTopics() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [subreddit, setSubreddit] = useState("music");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/trending-topics")
      .then((r) => r.json())
      .then((d) => {
        setTopics(d.posts ?? []);
        setSubreddit(d.subreddit ?? "music");
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-9 bg-[#1a1a1a] rounded" />
        ))}
      </div>
    );
  }

  if (topics.length === 0) {
    return <p className="text-[#555] text-xs">No trending topics right now.</p>;
  }

  return (
    <div className="space-y-2">
      <p className="text-[#333] text-xs mb-2">r/{subreddit} · hot</p>
      {topics.map((topic) => (
        <a
          key={topic.id}
          href={topic.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block group"
        >
          <div className="flex items-start gap-2 py-1.5 border-b border-[rgba(255,255,255,0.04)] hover:border-[rgba(255,255,255,0.1)] transition-colors">
            <span className="text-[#555] text-xs shrink-0 mt-0.5">▲ {topic.score > 999 ? `${(topic.score / 1000).toFixed(1)}k` : topic.score}</span>
            <p className="text-[#888] text-xs leading-snug group-hover:text-[#E8B84B] transition-colors line-clamp-2">
              {topic.title}
            </p>
          </div>
        </a>
      ))}
    </div>
  );
}
