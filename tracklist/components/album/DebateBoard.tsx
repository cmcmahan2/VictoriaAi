"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { UserAvatar } from "@/components/ui/UserAvatar";
import Link from "next/link";

interface DebatePost {
  id: string;
  body: string;
  upvotes: number;
  downvotes: number;
  createdAt: string;
  parentId: string | null;
  user: { username: string; avatarUrl?: string | null };
  replies?: DebatePost[];
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function PostItem({
  post,
  albumId,
  onVote,
  depth = 0,
}: {
  post: DebatePost;
  albumId: string;
  onVote: (postId: string, vote: "up" | "down") => void;
  depth?: number;
}) {
  const { data: session } = useSession();
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyBody, setReplyBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [localReplies, setLocalReplies] = useState<DebatePost[]>(post.replies ?? []);

  async function submitReply() {
    if (!replyBody.trim() || submitting) return;
    setSubmitting(true);
    const res = await fetch("/api/debate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ albumId, body: replyBody.trim(), parentId: post.id }),
    });
    if (res.ok) {
      const newPost = await res.json();
      setLocalReplies((prev) => [...prev, { ...newPost, replies: [] }]);
      setReplyBody("");
      setReplyOpen(false);
    }
    setSubmitting(false);
  }

  return (
    <div className={`${depth > 0 ? "ml-6 border-l border-[rgba(255,255,255,0.06)] pl-4" : ""}`}>
      <div className="py-3">
        <div className="flex items-center gap-2 mb-2">
          <Link href={`/user/${post.user.username}`}>
            <UserAvatar username={post.user.username} avatarUrl={post.user.avatarUrl} size={28} />
          </Link>
          <Link href={`/user/${post.user.username}`} className="text-[#F5F2EB] text-sm font-medium hover:text-[#E8B84B] transition-colors">
            {post.user.username}
          </Link>
          <span className="text-[#555] text-xs">{timeAgo(post.createdAt)}</span>
        </div>
        <p className="text-[#F5F2EB] text-sm leading-relaxed mb-2">{post.body}</p>
        <div className="flex items-center gap-3">
          <button onClick={() => onVote(post.id, "up")} className="flex items-center gap-1 text-xs text-[#888] hover:text-green-400 transition-colors">
            <span>▲</span> {post.upvotes}
          </button>
          <button onClick={() => onVote(post.id, "down")} className="flex items-center gap-1 text-xs text-[#888] hover:text-red-400 transition-colors">
            <span>▼</span> {post.downvotes}
          </button>
          {session && depth === 0 && (
            <button onClick={() => setReplyOpen((v) => !v)} className="text-xs text-[#888] hover:text-[#F5F2EB] transition-colors">
              Reply
            </button>
          )}
        </div>

        {replyOpen && (
          <div className="mt-3 space-y-2">
            <textarea
              value={replyBody}
              onChange={(e) => setReplyBody(e.target.value)}
              placeholder="Write a reply..."
              rows={2}
              className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-3 py-2 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={submitReply}
                disabled={submitting || !replyBody.trim()}
                className="text-xs bg-[#E8B84B] text-black font-medium px-3 py-1.5 rounded-full hover:bg-[#d4a43a] transition-colors disabled:opacity-50"
              >
                {submitting ? "Posting..." : "Post"}
              </button>
              <button onClick={() => setReplyOpen(false)} className="text-xs text-[#888] hover:text-[#F5F2EB] transition-colors">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {localReplies.length > 0 && (
        <div>
          {localReplies.map((reply) => (
            <PostItem key={reply.id} post={reply} albumId={albumId} onVote={onVote} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function DebateBoard({ albumId }: { albumId: string }) {
  const { data: session } = useSession();
  const [posts, setPosts] = useState<DebatePost[]>([]);
  const [loading, setLoading] = useState(true);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetch(`/api/debate?albumId=${albumId}`)
      .then((r) => r.json())
      .then((data) => { setPosts(Array.isArray(data) ? data : []); setLoading(false); });
  }, [albumId]);

  async function submitPost() {
    if (!body.trim() || submitting) return;
    setSubmitting(true);
    const res = await fetch("/api/debate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ albumId, body: body.trim() }),
    });
    if (res.ok) {
      const newPost = await res.json();
      setPosts((prev) => [{ ...newPost, replies: [] }, ...prev]);
      setBody("");
    }
    setSubmitting(false);
  }

  async function handleVote(postId: string, vote: "up" | "down") {
    const res = await fetch("/api/debate", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ postId, vote }),
    });
    if (res.ok) {
      const updated = await res.json();
      setPosts((prev) =>
        prev.map((p) => p.id === postId ? { ...p, ...updated } : {
          ...p,
          replies: p.replies?.map((r) => r.id === postId ? { ...r, ...updated } : r),
        })
      );
    }
  }

  return (
    <div>
      {session ? (
        <div className="mb-6 space-y-2">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Share your take on this album..."
            rows={3}
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-4 py-3 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors resize-none"
          />
          <button
            onClick={submitPost}
            disabled={submitting || !body.trim()}
            className="text-sm bg-[#E8B84B] text-black font-semibold px-5 py-2 rounded-full hover:bg-[#d4a43a] transition-colors disabled:opacity-50"
          >
            {submitting ? "Posting..." : "Post"}
          </button>
        </div>
      ) : (
        <p className="text-[#888] text-sm mb-6">
          <a href="/login" className="text-[#E8B84B] hover:underline">Sign in</a> to join the debate.
        </p>
      )}

      {loading ? (
        <div className="space-y-4 animate-pulse">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="py-3">
              <div className="flex gap-2 mb-2">
                <div className="w-7 h-7 rounded-full bg-[#1a1a1a]" />
                <div className="h-3 bg-[#1a1a1a] rounded w-24" />
              </div>
              <div className="space-y-1">
                <div className="h-3 bg-[#1a1a1a] rounded w-full" />
                <div className="h-3 bg-[#1a1a1a] rounded w-4/5" />
              </div>
            </div>
          ))}
        </div>
      ) : posts.length === 0 ? (
        <p className="text-[#888] text-sm text-center py-8">No posts yet. Start the debate!</p>
      ) : (
        <div className="divide-y divide-[rgba(255,255,255,0.06)]">
          {posts.map((post) => (
            <PostItem key={post.id} post={post} albumId={albumId} onVote={handleVote} />
          ))}
        </div>
      )}
    </div>
  );
}
