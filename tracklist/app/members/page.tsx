"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { UserAvatar } from "@/components/ui/UserAvatar";

interface Member {
  id: string;
  username: string;
  displayName: string | null;
  avatarUrl: string | null;
  bio: string | null;
  favoriteGenres: string[];
  _count: { ratings: number; reviews: number; followers: number };
}

export default function MembersPage() {
  const [query, setQuery] = useState("");

  const { data: searchResults, isLoading: searching } = useQuery<Member[]>({
    queryKey: ["userSearch", query],
    queryFn: () => fetch(`/api/users?q=${encodeURIComponent(query)}`).then((r) => r.json()),
    enabled: query.length >= 2,
  });

  const { data: allMembers } = useQuery<Member[]>({
    queryKey: ["members"],
    queryFn: () => fetch("/api/users/all").then((r) => r.json()),
    enabled: query.length < 2,
  });

  const members = query.length >= 2 ? (searchResults ?? []) : (allMembers ?? []);
  const isLoading = query.length >= 2 ? searching : !allMembers;

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
          Members
        </h1>
        <p className="text-[#888] mt-1">Find people who love the same music you do.</p>
      </div>

      {/* Search */}
      <div className="mb-8">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search members by username…"
          className="w-full max-w-sm bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-full px-5 py-2.5 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
        />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-20 bg-[#111] rounded-xl animate-pulse" />
          ))}
        </div>
      ) : members.length === 0 ? (
        <p className="text-[#888] text-center py-12">
          {query.length >= 2 ? `No members found for "${query}"` : "No members yet."}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {members.map((user) => (
            <Link
              key={user.id}
              href={`/user/${user.username}`}
              className="flex items-center gap-4 bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 hover:border-[rgba(255,255,255,0.2)] transition-colors group"
            >
              <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={48} />
              <div className="flex-1 min-w-0">
                <p className="text-[#F5F2EB] font-semibold group-hover:text-[#E8B84B] transition-colors">
                  {user.displayName ?? user.username}
                </p>
                {user.displayName && (
                  <p className="text-[#555] text-xs">@{user.username}</p>
                )}
                {user.bio && <p className="text-[#888] text-xs truncate mt-0.5">{user.bio}</p>}
                <div className="flex gap-3 mt-1.5 flex-wrap">
                  <span className="text-[#555] text-xs">{user._count.ratings} ratings</span>
                  <span className="text-[#555] text-xs">{user._count.reviews} reviews</span>
                  <span className="text-[#555] text-xs">{user._count.followers} followers</span>
                </div>
                {user.favoriteGenres?.length > 0 && (
                  <div className="flex gap-1 mt-1.5 flex-wrap">
                    {user.favoriteGenres.slice(0, 3).map((g) => (
                      <span key={g} className="text-[9px] bg-[#1a1a1a] text-[#555] rounded-full px-2 py-0.5 border border-[rgba(255,255,255,0.06)]">
                        {g}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
