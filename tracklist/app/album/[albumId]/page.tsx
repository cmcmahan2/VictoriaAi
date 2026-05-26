export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import Image from "next/image";
import { prisma } from "@/lib/prisma";
import { getAlbum, spotifyAlbumToDbAlbum } from "@/lib/spotify";
import { GenreTag } from "@/components/ui/GenreTag";
import { ReviewCard, ReviewCardSkeleton } from "@/components/ui/ReviewCard";
import { RatingHistogram } from "@/components/album/RatingHistogram";
import { AlbumRatingSection } from "@/components/album/AlbumRatingSection";
import { Suspense } from "react";

async function getOrCacheAlbum(albumId: string) {
  const cached = await prisma.album.findUnique({ where: { id: albumId } });
  if (cached) return cached;

  try {
    const spotifyAlbum = await getAlbum(albumId);
    const data = spotifyAlbumToDbAlbum(spotifyAlbum);
    return await prisma.album.upsert({
      where: { id: albumId },
      update: {},
      create: data,
    });
  } catch {
    return null;
  }
}

async function AlbumReviews({ albumId }: { albumId: string }) {
  const reviews = await prisma.review.findMany({
    where: { albumId },
    orderBy: { createdAt: "desc" },
    take: 20,
    include: { user: { select: { username: true, avatarUrl: true } } },
  });

  if (reviews.length === 0) {
    return <p className="text-[#888] py-8 text-center">No reviews yet. Be the first to write one!</p>;
  }

  return (
    <div className="space-y-4">
      {reviews.map((r) => (
        <ReviewCard
          key={r.id}
          id={r.id}
          body={r.body}
          rating={r.rating}
          likes={r.likes}
          createdAt={r.createdAt.toISOString()}
          user={r.user}
          albumId={albumId}
        />
      ))}
    </div>
  );
}

async function AlbumRatingStats({ albumId }: { albumId: string }) {
  const ratings = await prisma.rating.findMany({ where: { albumId } });

  const distribution: Record<string, number> = {};
  for (const r of ratings) {
    distribution[String(r.value)] = (distribution[String(r.value)] ?? 0) + 1;
  }

  if (ratings.length === 0) {
    return <p className="text-[#888] text-sm">No ratings yet.</p>;
  }

  return <RatingHistogram distribution={distribution} total={ratings.length} />;
}

export default async function AlbumPage({ params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = await params;
  const album = await getOrCacheAlbum(albumId);

  if (!album) notFound();

  let tracks: Array<{ id: string; name: string; duration_ms: number; track_number: number }> = [];
  try {
    const spotifyData = await getAlbum(albumId);
    tracks = spotifyData.tracks?.items ?? [];
  } catch {
    // tracks unavailable
  }

  function formatDuration(ms: number) {
    const m = Math.floor(ms / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-10">
      {/* Hero */}
      <div className="flex flex-col md:flex-row gap-8 mb-12">
        <div className="shrink-0">
          {album.coverUrl ? (
            <Image
              src={album.coverUrl}
              alt={album.title}
              width={280}
              height={280}
              className="rounded-lg object-cover shadow-2xl"
              sizes="280px"
              priority
            />
          ) : (
            <div className="w-[280px] h-[280px] bg-[#1a1a1a] rounded-lg flex items-center justify-center text-[#444] text-6xl">♪</div>
          )}
        </div>

        <div className="flex-1 space-y-4">
          <div>
            <p className="text-[#888] text-sm uppercase tracking-widest mb-1">{album.releaseYear}</p>
            <h1 className="text-3xl md:text-4xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
              {album.title}
            </h1>
            <p className="text-xl text-[#888] mt-1">{album.artistName}</p>
          </div>

          {album.genres.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {album.genres.map((g) => (
                <GenreTag key={g} genre={g} />
              ))}
            </div>
          )}

          <div className="flex items-center gap-4">
            {album.avgRating != null && (
              <div>
                <span className="text-[#E8B84B] text-2xl font-bold">{album.avgRating.toFixed(1)}</span>
                <span className="text-[#888] text-sm ml-2">{album.ratingCount.toLocaleString()} ratings</span>
              </div>
            )}
          </div>

          <AlbumRatingSection albumId={album.id} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        <div className="lg:col-span-2 space-y-10">
          {/* Reviews */}
          <section>
            <h2 className="text-xl font-semibold text-[#F5F2EB] mb-4" style={{ fontFamily: "Playfair Display, serif" }}>Reviews</h2>
            <Suspense fallback={<div className="space-y-4"><ReviewCardSkeleton /><ReviewCardSkeleton /></div>}>
              <AlbumReviews albumId={album.id} />
            </Suspense>
          </section>
        </div>

        <div className="space-y-8">
          {/* Rating distribution */}
          <section>
            <h3 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Rating Distribution</h3>
            <Suspense fallback={<div className="space-y-1 animate-pulse">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-4 bg-[#1a1a1a] rounded" />)}</div>}>
              <AlbumRatingStats albumId={album.id} />
            </Suspense>
          </section>

          {/* Tracklist */}
          {tracks.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Tracklist</h3>
              <ol className="space-y-1">
                {tracks.map((track) => (
                  <li key={track.id} className="flex justify-between text-sm py-1 border-b border-[rgba(255,255,255,0.05)]">
                    <span className="text-[#F5F2EB] flex gap-3">
                      <span className="text-[#555] w-5 text-right shrink-0">{track.track_number}</span>
                      {track.name}
                    </span>
                    <span className="text-[#555] shrink-0 ml-4">{formatDuration(track.duration_ms)}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
