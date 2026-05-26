"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlbumCardSkeleton } from "@/components/ui/AlbumCard";
import { Suspense } from "react";

interface SpotifyAlbumResult {
  id: string;
  name: string;
  artists: Array<{ name: string }>;
  release_date: string;
  images: Array<{ url: string }>;
}

function SearchResults({ query }: { query: string }) {
  const { data, isLoading, isError } = useQuery<SpotifyAlbumResult[]>({
    queryKey: ["search", query],
    queryFn: async () => {
      const res = await fetch(`/api/albums/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error("Search failed");
      return res.json();
    },
    enabled: query.length > 0,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {Array.from({ length: 10 }).map((_, i) => <AlbumCardSkeleton key={i} />)}
      </div>
    );
  }

  if (isError) {
    return <p className="text-[#888] text-center py-12">Search failed. Make sure Spotify credentials are configured.</p>;
  }

  if (!data || data.length === 0) {
    return <p className="text-[#888] text-center py-12">No results for &quot;{query}&quot;</p>;
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {data.map((album) => (
        <Link key={album.id} href={`/album/${album.id}`} className="group block">
          <div className="border border-[rgba(255,255,255,0.08)] rounded-lg overflow-hidden bg-[#111] hover:border-[rgba(255,255,255,0.2)] transition-colors">
            <div className="relative aspect-square">
              {album.images[0]?.url ? (
                <Image
                  src={album.images[0].url}
                  alt={album.name}
                  fill
                  sizes="(max-width: 640px) 50vw, 20vw"
                  className="object-cover group-hover:scale-105 transition-transform duration-300"
                />
              ) : (
                <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-4xl">♪</div>
              )}
            </div>
            <div className="p-3">
              <p className="text-[#F5F2EB] font-medium text-sm truncate">{album.name}</p>
              <p className="text-[#888] text-xs mt-0.5 truncate">
                {album.artists.map((a) => a.name).join(", ")} · {album.release_date?.slice(0, 4)}
              </p>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

function SearchPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [input, setInput] = useState(searchParams.get("q") ?? "");
  const query = searchParams.get("q") ?? "";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (input.trim()) {
      router.push(`/search?q=${encodeURIComponent(input.trim())}`);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-10">
      <h1 className="text-3xl font-bold text-[#F5F2EB] mb-8" style={{ fontFamily: "Playfair Display, serif" }}>
        Search
      </h1>

      <form onSubmit={handleSubmit} className="mb-10">
        <div className="flex gap-3 max-w-xl">
          <input
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Search for albums or artists…"
            autoFocus
            className="flex-1 bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-full px-5 py-3 text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
          />
          <button
            type="submit"
            className="bg-[#E8B84B] text-black font-semibold px-6 py-3 rounded-full hover:bg-[#d4a43a] transition-colors"
          >
            Search
          </button>
        </div>
      </form>

      {query && <SearchResults query={query} />}
    </div>
  );
}

export default function SearchPageWrapper() {
  return (
    <Suspense>
      <SearchPage />
    </Suspense>
  );
}
