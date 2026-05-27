"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";

interface SpotifyAlbum {
  id: string;
  name: string;
  artists: Array<{ name: string }>;
  release_date: string;
  images: Array<{ url: string }>;
}

export function NewReleasesStrip() {
  const [albums, setAlbums] = useState<SpotifyAlbum[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/new-releases")
      .then((r) => r.json())
      .then((data) => { setAlbums(Array.isArray(data) ? data.slice(0, 20) : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-hidden">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="shrink-0 w-[120px] animate-pulse">
            <div className="w-[120px] h-[120px] bg-[#1a1a1a] rounded-lg mb-2" />
            <div className="h-3 bg-[#1a1a1a] rounded w-4/5 mb-1" />
            <div className="h-3 bg-[#1a1a1a] rounded w-3/5" />
          </div>
        ))}
      </div>
    );
  }

  if (!albums.length) return null;

  return (
    <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none">
      {albums.map((album) => (
        <Link key={album.id} href={`/album/${album.id}`} className="shrink-0 group w-[120px]">
          <div className="w-[120px] h-[120px] rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all relative mb-2">
            {album.images[0]?.url ? (
              <Image
                src={album.images[0].url}
                alt={album.name}
                fill
                sizes="120px"
                className="object-cover group-hover:scale-105 transition-transform duration-300"
              />
            ) : (
              <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-3xl">♪</div>
            )}
            <div className="absolute top-1.5 left-1.5 bg-[#E8B84B] text-black text-[8px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide">
              New
            </div>
          </div>
          <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">
            {album.name}
          </p>
          <p className="text-[#555] text-xs truncate">{album.artists[0]?.name}</p>
        </Link>
      ))}
    </div>
  );
}
