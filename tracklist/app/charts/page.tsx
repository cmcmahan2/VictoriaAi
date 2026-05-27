export const dynamic = "force-dynamic";

import Link from "next/link";
import Image from "next/image";
import { Suspense } from "react";
import { getNewReleases } from "@/lib/spotify";
import { prisma } from "@/lib/prisma";
import { AlbumCard, AlbumCardSkeleton } from "@/components/ui/AlbumCard";
import { TrendingTopics } from "@/components/home/TrendingTopics";

async function NewReleases() {
  let albums = [];
  try {
    albums = await getNewReleases(24);
  } catch {
    return <p className="text-[#888] text-sm">Spotify unavailable right now.</p>;
  }

  if (!albums.length) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {albums.map((album) => (
        <Link key={album.id} href={`/album/${album.id}`} className="group">
          <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2 relative">
            {album.images[0]?.url ? (
              <Image
                src={album.images[0].url}
                alt={album.name}
                fill
                sizes="200px"
                className="object-cover group-hover:scale-105 transition-transform duration-300"
              />
            ) : (
              <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-3xl">♪</div>
            )}
            {/* "NEW" badge */}
            <div className="absolute top-2 left-2 bg-[#E8B84B] text-black text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide">
              New
            </div>
          </div>
          <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">
            {album.name}
          </p>
          <p className="text-[#555] text-xs truncate">{album.artists[0]?.name}</p>
          <p className="text-[#333] text-xs">{album.release_date?.slice(0, 10)}</p>
        </Link>
      ))}
    </div>
  );
}

async function TopRatedAllTime() {
  const albums = await prisma.album.findMany({
    where: { ratingCount: { gte: 1 } },
    orderBy: [{ avgRating: "desc" }, { ratingCount: "desc" }],
    take: 10,
  });

  if (!albums.length) return <p className="text-[#888] text-sm">No rated albums yet. Be the first!</p>;

  return (
    <ol className="space-y-2">
      {albums.map((album, i) => (
        <li key={album.id}>
          <Link
            href={`/album/${album.id}`}
            className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-[rgba(255,255,255,0.03)] transition-colors group"
          >
            <span className="text-[#555] text-sm font-mono w-5 text-center shrink-0">{i + 1}</span>
            <div className="w-10 h-10 rounded overflow-hidden shrink-0">
              {album.coverUrl ? (
                <Image src={album.coverUrl} alt={album.title} width={40} height={40} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444]">♪</div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[#F5F2EB] text-sm font-medium truncate group-hover:text-[#E8B84B] transition-colors">{album.title}</p>
              <p className="text-[#555] text-xs truncate">{album.artistName}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-[#E8B84B] text-sm font-bold">★ {album.avgRating?.toFixed(2)}</p>
              <p className="text-[#555] text-xs">{album.ratingCount} ratings</p>
            </div>
          </Link>
        </li>
      ))}
    </ol>
  );
}

async function TrendingThisWeek() {
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const recentRatings = await prisma.rating.groupBy({
    by: ["albumId"],
    where: { createdAt: { gte: sevenDaysAgo } },
    _count: { albumId: true },
    orderBy: { _count: { albumId: "desc" } },
    take: 10,
  });

  if (!recentRatings.length) {
    // fallback: most rated of all time
    const albums = await prisma.album.findMany({
      where: { ratingCount: { gt: 0 } },
      orderBy: { ratingCount: "desc" },
      take: 10,
    });
    if (!albums.length) return <p className="text-[#888] text-sm">No activity yet.</p>;
    return <AlbumList albums={albums} />;
  }

  const ids = recentRatings.map((r: { albumId: string }) => r.albumId);
  const albums = await prisma.album.findMany({ where: { id: { in: ids } } });
  const albumMap = new Map(albums.map((a) => [a.id, a]));
  const sorted = recentRatings.map((r: { albumId: string }) => albumMap.get(r.albumId)).filter(Boolean) as typeof albums;

  return <AlbumList albums={sorted} />;
}

function AlbumList({ albums }: { albums: Array<{ id: string; title: string; artistName: string; coverUrl: string | null; avgRating: number | null; ratingCount: number; releaseYear: number }> }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
      {albums.map((album) => (
        <AlbumCard
          key={album.id}
          id={album.id}
          title={album.title}
          artistName={album.artistName}
          coverUrl={album.coverUrl}
          avgRating={album.avgRating}
          ratingCount={album.ratingCount}
          releaseYear={album.releaseYear}
        />
      ))}
    </div>
  );
}

export default function ChartsPage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
          Charts
        </h1>
        <p className="text-[#888] mt-1">What&apos;s moving in music right now.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        <div className="lg:col-span-2 space-y-12">
          {/* New Releases */}
          <section>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest">New Releases</h2>
              <span className="text-[#555] text-xs">Updated hourly from Spotify</span>
            </div>
            <Suspense fallback={
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                {Array.from({ length: 12 }).map((_, i) => <AlbumCardSkeleton key={i} />)}
              </div>
            }>
              <NewReleases />
            </Suspense>
          </section>

          {/* Trending This Week */}
          <section>
            <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-5">Trending This Week</h2>
            <Suspense fallback={
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {Array.from({ length: 10 }).map((_, i) => <AlbumCardSkeleton key={i} />)}
              </div>
            }>
              <TrendingThisWeek />
            </Suspense>
          </section>
        </div>

        <div className="space-y-10">
          {/* Top Rated All Time */}
          <section>
            <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Top Rated All Time</h2>
            <Suspense fallback={<div className="space-y-2 animate-pulse">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 bg-[#1a1a1a] rounded-xl" />)}</div>}>
              <TopRatedAllTime />
            </Suspense>
          </section>

          {/* Music News */}
          <section>
            <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Music News</h2>
            <TrendingTopics />
          </section>
        </div>
      </div>
    </div>
  );
}
