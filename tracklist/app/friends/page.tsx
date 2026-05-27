"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { redirect } from "next/navigation";
import { UserAvatar } from "@/components/ui/UserAvatar";

interface UserCard {
  id: string;
  username: string;
  displayName: string | null;
  avatarUrl: string | null;
  bio: string | null;
  favoriteGenres: string[];
  _count: { ratings: number; reviews: number; followers: number };
  isFollowing?: boolean;
  isMutual?: boolean;
}

function FollowBtn({ userId, initialFollowing }: { userId: string; initialFollowing: boolean }) {
  const qc = useQueryClient();
  const [following, setFollowing] = useState(initialFollowing);

  const mut = useMutation({
    mutationFn: () =>
      fetch("/api/follow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ targetUserId: userId }),
      }).then((r) => r.json()),
    onSuccess: (data) => {
      setFollowing(data.following);
      qc.invalidateQueries({ queryKey: ["friends"] });
    },
  });

  return (
    <button
      onClick={() => mut.mutate()}
      disabled={mut.isPending}
      className={`text-xs px-3 py-1.5 rounded-full border transition-all disabled:opacity-50 ${
        following
          ? "bg-[#1a1a1a] border-[rgba(255,255,255,0.1)] text-[#888] hover:border-red-500 hover:text-red-400"
          : "bg-[#E8B84B] border-[#E8B84B] text-black font-semibold hover:bg-[#d4a43a]"
      }`}
    >
      {following ? "Following" : "Follow"}
    </button>
  );
}

function UserRow({ user, showMutual }: { user: UserCard; showMutual?: boolean }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-xl hover:border-[rgba(255,255,255,0.12)] transition-colors">
      <Link href={`/user/${user.username}`} className="shrink-0">
        <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={44} />
      </Link>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link href={`/user/${user.username}`} className="text-[#F5F2EB] text-sm font-semibold hover:text-[#E8B84B] transition-colors truncate">
            {user.displayName ?? user.username}
          </Link>
          {showMutual && user.isMutual && (
            <span className="text-[9px] bg-[rgba(232,184,75,0.15)] text-[#E8B84B] border border-[rgba(232,184,75,0.3)] rounded-full px-1.5 py-0.5 shrink-0">
              Friends
            </span>
          )}
        </div>
        {user.displayName && <p className="text-[#555] text-xs">@{user.username}</p>}
        {user.bio && <p className="text-[#888] text-xs truncate mt-0.5">{user.bio}</p>}
        <div className="flex gap-3 mt-1">
          <span className="text-[#555] text-[10px]">{user._count.ratings} ratings</span>
          <span className="text-[#555] text-[10px]">{user._count.reviews} reviews</span>
          <span className="text-[#555] text-[10px]">{user._count.followers} followers</span>
        </div>
      </div>
      <div className="flex flex-col gap-1.5 shrink-0">
        <FollowBtn userId={user.id} initialFollowing={user.isFollowing ?? false} />
        <Link href={`/user/${user.username}/taste-match`} className="text-[10px] text-[#555] hover:text-[#E8B84B] transition-colors text-center">
          Taste Match
        </Link>
      </div>
    </div>
  );
}

type Tab = "friends" | "following" | "followers" | "suggestions";

export default function FriendsPage() {
  const { data: session, status } = useSession();
  const [tab, setTab] = useState<Tab>("friends");

  const { data, isLoading } = useQuery<{
    friends: UserCard[];
    following: UserCard[];
    followers: UserCard[];
    suggestions: UserCard[];
  }>({
    queryKey: ["friends"],
    queryFn: () => fetch("/api/friends").then((r) => r.json()),
    enabled: status === "authenticated",
  });

  if (status === "loading") return <div className="max-w-2xl mx-auto px-4 py-10 animate-pulse space-y-3">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 bg-[#111] rounded-xl" />)}</div>;
  if (status === "unauthenticated") {
    if (typeof window !== "undefined") window.location.href = "/login";
    return null;
  }

  const me = session?.user as { name?: string | null } | undefined;
  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "friends", label: "Friends", count: data?.friends.length },
    { key: "following", label: "Following", count: data?.following.length },
    { key: "followers", label: "Followers", count: data?.followers.length },
    { key: "suggestions", label: "Discover" },
  ];

  const current = data?.[tab] ?? [];

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
          Friends
        </h1>
        <p className="text-[#888] text-sm mt-1">People who share your taste in music.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-[#111] rounded-xl p-1 border border-[rgba(255,255,255,0.06)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.key
                ? "bg-[#E8B84B] text-black"
                : "text-[#888] hover:text-[#F5F2EB]"
            }`}
          >
            {t.label}
            {t.count != null && t.count > 0 && (
              <span className={`ml-1.5 text-xs ${tab === t.key ? "text-black/70" : "text-[#555]"}`}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-[#111] rounded-xl animate-pulse" />)}
        </div>
      ) : current.length === 0 ? (
        <div className="text-center py-12 bg-[#111] rounded-2xl border border-[rgba(255,255,255,0.06)]">
          {tab === "friends" && (
            <>
              <p className="text-[#F5F2EB] font-semibold mb-2">No mutual follows yet</p>
              <p className="text-[#888] text-sm mb-4">Follow people and follow back to become friends.</p>
              <button onClick={() => setTab("suggestions")} className="text-[#E8B84B] text-sm hover:underline">
                Find people to follow →
              </button>
            </>
          )}
          {tab === "following" && (
            <>
              <p className="text-[#888]">You&apos;re not following anyone yet.</p>
              <button onClick={() => setTab("suggestions")} className="text-[#E8B84B] text-sm mt-2 hover:underline block mx-auto">
                Discover people →
              </button>
            </>
          )}
          {tab === "followers" && <p className="text-[#888]">No followers yet. Share your profile to get started.</p>}
          {tab === "suggestions" && <p className="text-[#888]">No suggestions right now. Rate more albums to improve matches.</p>}
        </div>
      ) : (
        <div className="space-y-2">
          {tab === "suggestions" && (
            <p className="text-[#555] text-xs mb-3">Based on similar taste in music</p>
          )}
          {current.map((user) => (
            <UserRow key={user.id} user={user} showMutual={tab === "followers" || tab === "following"} />
          ))}
          {tab === "friends" && data?.friends.length === 0 && data?.following.length === 0 && (
            <div className="text-center pt-4">
              <Link href="/members" className="text-[#888] text-sm hover:text-[#E8B84B] transition-colors">
                Browse all members →
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Share your profile */}
      {me?.name && (
        <div className="mt-8 p-4 bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-xl flex items-center justify-between gap-4">
          <div>
            <p className="text-[#F5F2EB] text-sm font-semibold">Share your profile</p>
            <p className="text-[#555] text-xs mt-0.5">tracklist.app/user/{me.name}</p>
          </div>
          <button
            onClick={() => {
              navigator.clipboard?.writeText(`${window.location.origin}/user/${me.name}`);
            }}
            className="text-xs bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] text-[#888] rounded-full px-3 py-1.5 hover:text-[#E8B84B] hover:border-[#E8B84B] transition-all shrink-0"
          >
            Copy link
          </button>
        </div>
      )}
    </div>
  );
}
