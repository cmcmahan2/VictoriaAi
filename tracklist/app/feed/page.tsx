"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import Image from "next/image";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { StarRating } from "@/components/ui/StarRating";

interface FeedItem {
  id: string;
  type: "rating" | "review";
  createdAt: string;
  value?: number;
  body?: string;
  rating?: number | null;
  likes?: number;
  user: { username: string; avatarUrl?: string | null };
  album: { id: string; title: string; artistName: string; coverUrl?: string | null };
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function FeedPage() {
  const { data: session, status } = useSession();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (status === "authenticated") {
      fetch("/api/feed")
        .then((r) => r.json())
        .then((data) => {
          setItems(Array.isArray(data) ? data : []);
          setLoading(false);
        });
    } else if (status === "unauthenticated") {
      setLoading(false);
    }
  }, [status]);

  if (status === "unauthenticated") {
    return (
      <div className="max-w-2xl mx-auto px-4 py-20 text-center">
        <h1 className="text-3xl font-bold text-[#F5F2EB] mb-4" style={{ fontFamily: "Playfair Display, serif" }}>
          Your Feed
        </h1>
        <p className="text-[#888] mb-6">Sign in to see activity from people you follow.</p>
        <Link href="/login" className="bg-[#E8B84B] text-black font-semibold px-6 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors">
          Sign in
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 animate-pulse">
            <div className="flex gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-[#1a1a1a]" />
              <div className="flex-1 space-y-2">
                <div className="h-3 bg-[#1a1a1a] rounded w-32" />
                <div className="h-3 bg-[#1a1a1a] rounded w-48" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-20 text-center">
        <div className="text-5xl mb-4">🎵</div>
        <h2 className="text-xl font-semibold text-[#F5F2EB] mb-2">Your feed is empty</h2>
        <p className="text-[#888] mb-6">Follow other users to see their ratings and reviews here.</p>
        <Link href="/search" className="text-[#E8B84B] hover:underline">Search for albums</Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-[#F5F2EB] mb-6" style={{ fontFamily: "Playfair Display, serif" }}>
        Activity Feed
      </h1>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.id + item.type} className="bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 hover:border-[rgba(255,255,255,0.15)] transition-colors">
            <div className="flex gap-3">
              <Link href={`/user/${item.user.username}`}>
                <UserAvatar username={item.user.username} avatarUrl={item.user.avatarUrl} size={40} />
              </Link>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link href={`/user/${item.user.username}`} className="text-[#F5F2EB] font-medium text-sm hover:text-[#E8B84B] transition-colors">
                    {item.user.username}
                  </Link>
                  <span className="text-[#555] text-xs">
                    {item.type === "rating" ? "rated" : "reviewed"}
                  </span>
                  <Link href={`/album/${item.album.id}`} className="text-[#E8B84B] text-sm font-medium hover:underline truncate max-w-[200px]">
                    {item.album.title}
                  </Link>
                  <span className="text-[#555] text-xs ml-auto">{timeAgo(item.createdAt)}</span>
                </div>

                <div className="flex gap-3 mt-2">
                  {item.album.coverUrl && (
                    <Link href={`/album/${item.album.id}`} className="shrink-0">
                      <Image
                        src={item.album.coverUrl}
                        alt={item.album.title}
                        width={52}
                        height={52}
                        className="rounded object-cover"
                      />
                    </Link>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-[#888] text-xs mb-1">{item.album.artistName}</p>
                    {item.type === "rating" && item.value != null && (
                      <StarRating value={item.value} readonly size="sm" />
                    )}
                    {item.type === "review" && (
                      <>
                        {item.rating != null && <StarRating value={item.rating} readonly size="sm" />}
                        <p className="text-[#F5F2EB] text-sm mt-1 line-clamp-2">{item.body}</p>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
