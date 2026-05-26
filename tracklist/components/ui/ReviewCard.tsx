"use client";

import Link from "next/link";
import { UserAvatar } from "./UserAvatar";
import { StarRating } from "./StarRating";

interface ReviewCardProps {
  id: string;
  body: string;
  rating?: number | null;
  likes: number;
  createdAt: string;
  user: { username: string; avatarUrl?: string | null };
  albumId?: string;
  albumTitle?: string;
  albumCoverUrl?: string | null;
  showAlbum?: boolean;
}

export function ReviewCard({
  body,
  rating,
  likes,
  createdAt,
  user,
  albumTitle,
  showAlbum = false,
}: ReviewCardProps) {
  const date = new Date(createdAt).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="border border-[rgba(255,255,255,0.08)] rounded-lg p-4 bg-[#111] space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={32} />
          <div>
            <Link href={`/user/${user.username}`} className="text-[#F5F2EB] text-sm font-medium hover:text-[#E8B84B] transition-colors">
              {user.username}
            </Link>
            {showAlbum && albumTitle && (
              <p className="text-[#888] text-xs">on {albumTitle}</p>
            )}
          </div>
        </div>
        <span className="text-[#888] text-xs shrink-0">{date}</span>
      </div>

      {rating != null && <StarRating value={rating} readonly size="sm" />}

      <p className="text-[#F5F2EB] text-sm leading-[1.8] max-w-[680px]">{body}</p>

      <div className="flex items-center gap-4 text-[#888] text-xs">
        <button className="hover:text-[#E8B84B] transition-colors flex items-center gap-1">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
          {likes}
        </button>
      </div>
    </div>
  );
}

export function ReviewCardSkeleton() {
  return (
    <div className="border border-[rgba(255,255,255,0.08)] rounded-lg p-4 bg-[#111] space-y-3 animate-pulse">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-full bg-[#1a1a1a]" />
        <div className="h-4 bg-[#1a1a1a] rounded w-24" />
      </div>
      <div className="space-y-2">
        <div className="h-3 bg-[#1a1a1a] rounded w-full" />
        <div className="h-3 bg-[#1a1a1a] rounded w-5/6" />
        <div className="h-3 bg-[#1a1a1a] rounded w-3/4" />
      </div>
    </div>
  );
}
