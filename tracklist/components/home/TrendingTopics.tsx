"use client";

import { useEffect, useState, useCallback } from "react";

interface Topic {
  id: string;
  title: string;
  url: string;
  score: number;
  comments: number;
  subreddit: string;
}

export function TrendingTopics() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [subreddits, setSubreddits] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchTopics = useCallback(() => {
    setLoading(true);
    fetch("/api/trending-topics")
      .then((r) => r.json())
      .then((d) => {
        setTopics(d.posts ?? []);
        setSubreddits(d.subreddits ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchTopics(); }, [fetchTopics]);

  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-8 bg-[#1a1a1a] rounded" />
        ))}
      </div>
    );
  }

  if (topics.length === 0) {
    return <p className="text-[#555] text-xs">No trending topics right now.</p>;
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[#333] text-xs">
          r/{subreddits.join(", r/")}
        </p>
        <button
          onClick={fetchTopics}
          className="text-[#333] hover:text-[#888] text-xs transition-colors"
          title="Refresh"
        >
          ↻
        </button>
      </div>
      {topics.map((topic) => (
        <a
          key={topic.id}
          href={topic.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block group"
        >
          <div className="flex items-start gap-2 py-1.5 border-b border-[rgba(255,255,255,0.04)] hover:border-[rgba(255,255,255,0.1)] transition-colors">
            <div className="flex flex-col items-center shrink-0 mt-0.5">
              <span className="text-[#555] text-[10px]">▲</span>
              <span className="text-[#444] text-[9px]">{topic.score > 999 ? `${(topic.score / 1000).toFixed(1)}k` : topic.score}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[#888] text-xs leading-snug group-hover:text-[#E8B84B] transition-colors line-clamp-2">
                {topic.title}
              </p>
              <p className="text-[#333] text-[9px] mt-0.5">r/{topic.subreddit} · {topic.comments} comments</p>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}
