"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { AlbumCardSkeleton } from "@/components/ui/AlbumCard";
import { Suspense } from "react";

interface SpotifyAlbumResult {
  id: string;
  name: string;
  artists: Array<{ name: string }>;
  release_date: string;
  images: Array<{ url: string }>;
}

interface UserList {
  id: string;
  title: string;
}

function AddToListButton({ albumId }: { albumId: string }) {
  const { data: session } = useSession();
  const [lists, setLists] = useState<UserList[]>([]);
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [added, setAdded] = useState<Set<string>>(new Set());

  const user = session?.user as { id?: string; name?: string | null } | undefined;

  useEffect(() => {
    if (open && user?.id) {
      fetch(`/api/lists?userId=${user.id}`)
        .then((r) => r.json())
        .then((data) => setLists(Array.isArray(data) ? data : []));
    }
  }, [open, user?.id]);

  if (!session) return null;

  async function addToList(listId: string) {
    setAdding(listId);
    const res = await fetch(`/api/lists/${listId}/entries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ albumId }),
    });
    if (res.ok) {
      setAdded((prev) => new Set([...prev, listId]));
    }
    setAdding(null);
  }

  return (
    <div className="relative">
      <button
        onClick={(e) => { e.preventDefault(); setOpen((v) => !v); }}
        className="absolute top-2 right-2 w-7 h-7 bg-[rgba(0,0,0,0.7)] rounded-full flex items-center justify-center text-[#888] hover:text-[#E8B84B] hover:bg-[rgba(0,0,0,0.9)] transition-all opacity-0 group-hover:opacity-100 z-10"
        title="Add to list"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </button>

      {open && (
        <div
          className="absolute top-2 right-10 bg-[#111] border border-[rgba(255,255,255,0.1)] rounded-xl py-1.5 w-48 shadow-2xl z-20"
          onClick={(e) => e.preventDefault()}
        >
          <p className="px-3 py-1.5 text-xs text-[#555] font-medium">Add to list</p>
          {lists.length === 0 ? (
            <div className="px-3 py-2">
              <Link href="/lists/new" className="text-[#E8B84B] text-xs hover:underline">
                Create your first list →
              </Link>
            </div>
          ) : (
            lists.map((list) => (
              <button
                key={list.id}
                onClick={() => addToList(list.id)}
                disabled={adding === list.id || added.has(list.id)}
                className="w-full text-left px-3 py-2 text-sm text-[#F5F2EB] hover:bg-[#1a1a1a] transition-colors disabled:opacity-50 flex items-center justify-between"
              >
                <span className="truncate">{list.title}</span>
                {added.has(list.id) && <span className="text-[#E8B84B] text-xs shrink-0">✓</span>}
              </button>
            ))
          )}
          <div className="border-t border-[rgba(255,255,255,0.06)] mt-1 pt-1">
            <Link href="/lists/new" className="block px-3 py-1.5 text-xs text-[#888] hover:text-[#E8B84B] transition-colors">
              + New list
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function SearchResults({ query, addToList }: { query: string; addToList: string | null }) {
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
    return <p className="text-[#888] text-center py-12">No results for &ldquo;{query}&rdquo;</p>;
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {data.map((album) => (
        <div key={album.id} className="group relative">
          <Link href={`/album/${album.id}`} className="block">
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
                {addToList && (
                  <div className="absolute inset-0 bg-[rgba(0,0,0,0.5)] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-[#E8B84B] text-xs font-semibold">Add to list</span>
                  </div>
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
          {!addToList && <AddToListButton albumId={album.id} />}
          {addToList && (
            <QuickAddToList albumId={album.id} listId={addToList} />
          )}
        </div>
      ))}
    </div>
  );
}

function QuickAddToList({ albumId, listId }: { albumId: string; listId: string }) {
  const [added, setAdded] = useState(false);
  const [adding, setAdding] = useState(false);

  async function add(e: React.MouseEvent) {
    e.preventDefault();
    if (added || adding) return;
    setAdding(true);
    const res = await fetch(`/api/lists/${listId}/entries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ albumId }),
    });
    if (res.ok) setAdded(true);
    setAdding(false);
  }

  return (
    <button
      onClick={add}
      disabled={added || adding}
      className={`absolute top-2 right-2 z-10 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
        added ? "bg-[#E8B84B] text-black" : "bg-[rgba(0,0,0,0.7)] text-[#888] hover:bg-[#E8B84B] hover:text-black opacity-0 group-hover:opacity-100"
      }`}
    >
      {added ? "✓" : "+"}
    </button>
  );
}

function SearchPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [input, setInput] = useState(searchParams.get("q") ?? "");
  const query = searchParams.get("q") ?? "";
  const addToList = searchParams.get("addToList");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (input.trim()) {
      const params = new URLSearchParams({ q: input.trim() });
      if (addToList) params.set("addToList", addToList);
      router.push(`/search?${params.toString()}`);
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-10">
      {addToList ? (
        <div className="flex items-center gap-3 mb-6">
          <Link href={`/lists/${addToList}`} className="text-[#888] hover:text-[#F5F2EB] transition-colors text-sm">← Back to list</Link>
          <p className="text-[#E8B84B] text-sm font-medium">Tap an album to add it to your list</p>
        </div>
      ) : (
        <h1 className="text-3xl font-bold text-[#F5F2EB] mb-8" style={{ fontFamily: "Playfair Display, serif" }}>
          Search Albums
        </h1>
      )}

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

      {query && <SearchResults query={query} addToList={addToList} />}
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
