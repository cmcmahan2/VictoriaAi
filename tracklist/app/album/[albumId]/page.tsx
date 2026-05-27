export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { getAlbum, getArtistAlbums, spotifyAlbumToDbAlbum, type SpotifyAlbum } from "@/lib/spotify";
import { itunesLookupAlbum } from "@/lib/itunes";
import { GenreTag } from "@/components/ui/GenreTag";
import { ReviewCard, ReviewCardSkeleton } from "@/components/ui/ReviewCard";
import { RatingHistogram } from "@/components/album/RatingHistogram";
import { AlbumRatingSection } from "@/components/album/AlbumRatingSection";
import { DebateBoard } from "@/components/album/DebateBoard";
import { WatchlistButton } from "@/components/album/WatchlistButton";
import { ReviewComments } from "@/components/album/ReviewComments";
import { AlbumBlurb } from "@/components/album/AlbumBlurb";
import { MusicBrainzInfo } from "@/components/album/MusicBrainzInfo";
import { Suspense } from "react";

async function getOrCacheAlbum(albumId: string) {
  const cached = await prisma.album.findUnique({ where: { id: albumId } }).catch(() => null);
  if (cached) return cached;

  // Spotify IDs are 22-char base62; iTunes IDs are numeric. Try the matching source.
  let fetched: SpotifyAlbum | null = null;
  try {
    fetched = /^\d+$/.test(albumId) ? await itunesLookupAlbum(albumId) : await getAlbum(albumId);
  } catch {
    fetched = null;
  }
  if (!fetched?.id) return null;

  try {
    const data = spotifyAlbumToDbAlbum(fetched);
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
    <div className="space-y-6">
      {reviews.map((r: (typeof reviews)[number]) => (
        <div key={r.id} className="space-y-3">
          <ReviewCard
            id={r.id}
            body={r.body}
            rating={r.rating}
            likes={r.likes}
            createdAt={r.createdAt.toISOString()}
            user={r.user}
            albumId={albumId}
          />
          <ReviewComments reviewId={r.id} />
        </div>
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

async function MoreByArtist({ artistId, currentAlbumId }: { artistId: string; currentAlbumId: string }) {
  let artistAlbums: SpotifyAlbum[] = [];
  try {
    artistAlbums = await getArtistAlbums(artistId, 12);
  } catch {
    return null;
  }

  const filtered = artistAlbums.filter((a) => a.id !== currentAlbumId).slice(0, 8);
  if (filtered.length === 0) return null;

  return (
    <section className="mt-12 pt-10 border-t border-[rgba(255,255,255,0.06)]">
      <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-5">More by this Artist</h2>
      <div className="flex gap-3 overflow-x-auto pb-3 scrollbar-none">
        {filtered.map((a) => (
          <Link key={a.id} href={`/album/${a.id}`} className="shrink-0 group w-[120px]">
            <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
              {a.images[0]?.url ? (
                <Image
                  src={a.images[0].url}
                  alt={a.name}
                  width={120}
                  height={120}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
              ) : (
                <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-2xl">♪</div>
              )}
            </div>
            <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{a.name}</p>
            <p className="text-[#555] text-[10px]">{a.release_date?.slice(0, 4)}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

async function SimilarAlbums({ genres, currentAlbumId }: { genres: string[]; currentAlbumId: string }) {
  if (genres.length === 0) return null;

  const similar = await prisma.album.findMany({
    where: {
      id: { not: currentAlbumId },
      genres: { hasSome: genres },
    },
    orderBy: [{ ratingCount: "desc" }, { avgRating: "desc" }],
    take: 6,
  });

  if (similar.length === 0) return null;

  return (
    <section className="mt-10 pt-8 border-t border-[rgba(255,255,255,0.06)]">
      <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-5">You Might Also Like</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
        {similar.map((a) => (
          <Link key={a.id} href={`/album/${a.id}`} className="group">
            <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
              {a.coverUrl ? (
                <Image
                  src={a.coverUrl}
                  alt={a.title}
                  width={120}
                  height={120}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
              ) : (
                <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-2xl">♪</div>
              )}
            </div>
            <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{a.title}</p>
            <p className="text-[#555] text-[10px] truncate">{a.artistName}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default async function AlbumPage({ params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = await params;
  const album = await getOrCacheAlbum(albumId);

  if (!album) notFound();

  let tracks: Array<{ id: string; name: string; duration_ms: number; track_number: number }> = [];
  let spotifyData: SpotifyAlbum | null = null;
  try {
    spotifyData = await getAlbum(albumId);
    tracks = spotifyData.tracks?.items ?? [];
  } catch {
    // tracks unavailable
  }

  function formatDuration(ms: number) {
    const m = Math.floor(ms / 60000);
    const s = Math.floor((ms % 60000) / 1000);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }

  const totalDuration = tracks.reduce((acc, t) => acc + t.duration_ms, 0);
  const totalMin = Math.floor(totalDuration / 60000);

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
            <Link href={`/artist/${album.artistId}`} className="text-xl text-[#888] mt-1 hover:text-[#E8B84B] transition-colors inline-block">
              {album.artistName}
            </Link>
          </div>

          {album.genres.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {album.genres.map((g: string) => (
                <GenreTag key={g} genre={g} />
              ))}
            </div>
          )}

          <AlbumBlurb albumId={album.id} initialDescription={album.description} />

          <div className="flex items-center gap-6 flex-wrap">
            {album.avgRating != null && (
              <div>
                <span className="text-[#E8B84B] text-2xl font-bold">{album.avgRating.toFixed(1)}</span>
                <span className="text-[#888] text-sm ml-2">{album.ratingCount.toLocaleString()} ratings</span>
              </div>
            )}
            {tracks.length > 0 && (
              <div className="text-[#555] text-sm">
                {tracks.length} tracks · {totalMin} min
              </div>
            )}
            {spotifyData?.popularity != null && (
              <div className="flex items-center gap-1.5">
                <div className="w-16 h-1.5 bg-[#1a1a1a] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#E8B84B] rounded-full"
                    style={{ width: `${spotifyData.popularity}%` }}
                  />
                </div>
                <span className="text-[#555] text-xs">{spotifyData.popularity}/100 popularity</span>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
            <AlbumRatingSection albumId={album.id} />
            <WatchlistButton albumId={album.id} />
          </div>

          {/* Spotify link */}
          <a
            href={`https://open.spotify.com/album/${album.id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-[#555] hover:text-[#1DB954] text-sm transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
            </svg>
            Listen on Spotify
          </a>
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

          {/* Debate Board */}
          <section>
            <h3 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Debate</h3>
            <DebateBoard albumId={album.id} />
          </section>

          {/* MusicBrainz release info */}
          <Suspense fallback={null}>
            <MusicBrainzInfo artist={album.artistName} title={album.title} />
          </Suspense>

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

      {/* More by Artist */}
      {album.artistId && (
        <Suspense fallback={null}>
          <MoreByArtist artistId={album.artistId} currentAlbumId={album.id} />
        </Suspense>
      )}

      {/* Similar Albums from DB */}
      {album.genres.length > 0 && (
        <Suspense fallback={null}>
          <SimilarAlbums genres={album.genres} currentAlbumId={album.id} />
        </Suspense>
      )}
    </div>
  );
}
