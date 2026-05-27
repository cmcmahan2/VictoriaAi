"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { UserAvatar } from "@/components/ui/UserAvatar";

interface Comment {
  id: string;
  body: string;
  createdAt: string;
  user: { username: string; avatarUrl: string | null };
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function ReviewComments({ reviewId }: { reviewId: string }) {
  const { data: session } = useSession();
  const [comments, setComments] = useState<Comment[]>([]);
  const [shown, setShown] = useState(false);
  const [body, setBody] = useState("");
  const [posting, setPosting] = useState(false);
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    // Just fetch count initially
    fetch(`/api/reviews/${reviewId}/comments`)
      .then((r) => r.json())
      .then((d: Comment[]) => { setCount(d.length); if (shown) setComments(d); });
  }, [reviewId, shown]);

  function toggle() {
    if (!shown) {
      fetch(`/api/reviews/${reviewId}/comments`)
        .then((r) => r.json())
        .then((d: Comment[]) => { setComments(d); setCount(d.length); });
    }
    setShown((v) => !v);
  }

  async function post(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim() || posting) return;
    setPosting(true);
    const res = await fetch(`/api/reviews/${reviewId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: body.trim() }),
    });
    if (res.ok) {
      const comment: Comment = await res.json();
      setComments((prev) => [...prev, comment]);
      setCount((c) => (c ?? 0) + 1);
      setBody("");
    }
    setPosting(false);
  }

  return (
    <div className="ml-4 pl-4 border-l border-[rgba(255,255,255,0.06)]">
      <button
        onClick={toggle}
        className="text-[#555] text-xs hover:text-[#888] transition-colors"
      >
        💬 {count !== null && count > 0 ? `${count} comment${count !== 1 ? "s" : ""}` : "Add a comment"}
        {shown ? " ▲" : " ▼"}
      </button>

      {shown && (
        <div className="mt-3 space-y-3">
          {comments.map((c) => (
            <div key={c.id} className="flex gap-2">
              <UserAvatar username={c.user.username} avatarUrl={c.user.avatarUrl} size={22} />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <Link href={`/user/${c.user.username}`} className="text-[#F5F2EB] text-xs font-medium hover:text-[#E8B84B] transition-colors">
                    {c.user.username}
                  </Link>
                  <span className="text-[#444] text-[10px]">{timeAgo(c.createdAt)}</span>
                </div>
                <p className="text-[#888] text-xs leading-relaxed mt-0.5">{c.body}</p>
              </div>
            </div>
          ))}

          {session ? (
            <form onSubmit={post} className="flex gap-2 mt-2">
              <input
                type="text"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Write a comment…"
                maxLength={500}
                className="flex-1 bg-[#1a1a1a] border border-[rgba(255,255,255,0.08)] rounded-full px-3 py-1.5 text-xs text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
              />
              <button
                type="submit"
                disabled={!body.trim() || posting}
                className="text-[#E8B84B] text-xs font-medium disabled:opacity-40 hover:text-[#d4a43a] transition-colors px-2"
              >
                {posting ? "…" : "Post"}
              </button>
            </form>
          ) : (
            <Link href="/login" className="text-[#555] text-xs hover:text-[#E8B84B] transition-colors">
              Sign in to comment
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
