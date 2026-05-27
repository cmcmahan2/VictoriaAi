export const dynamic = "force-dynamic";

import Link from "next/link";
import Image from "next/image";
import { prisma } from "@/lib/prisma";
import { getArtist, getArtistAlbums, spotifyAlbumToDbAlbum } from "@/lib/spotify";
import { GenreTag } from "@/components/ui/GenreTag";

interface PageProps {
  params: Promise<{ artistId: string }>;
}

export default async function ArtistPage({ params }: PageProps) {
  const { artistId } = await params;

  // Fetch Spotify artist data and DB albums in parallel
  const [spotifyArtist, dbAlbums] = await Promise.allSettled([
    getArtist(artistId),
    prisma.album.findMany({ where: { artistId }, orderBy: { releaseYear: "desc" } }),
  ]);

  const artist = spotifyArtist.status === "fulfilled" ? spotifyArtist.value : null;
  const albums = dbAlbums.status === "fulfilled" ? dbAlbums.value : [];

  // If no DB albums, try Spotify discography and cache them
  let spotifyAlbums: Awaited<ReturnType<typeof getArtistAlbums>> = [];
  if (albums.length === 0 && artist) {
    try {
      spotifyAlbums = await getArtistAlbums(artistId, 20);
      // Cache them in DB
      await Promise.allSettled(
        spotifyAlbums.map((a) =>
          prisma.album.upsert({
            where: { id: a.id },
            update: {},
            create: spotifyAlbumToDbAlbum(a),
          })
        )
      );
    } catch {
      // ignore
    }
  }

  const displayName = artist?.name ?? (albums[0]?.artistName ?? "Artist");
  const allGenres = artist?.genres.length
    ? artist.genres
    : [...new Set(albums.flatMap((a) => a.genres))];

  const totalRatings = albums.reduce((sum, a) => sum + a.ratingCount, 0);
  const ratedAlbums = albums.filter((a) => a.avgRating != null);
  const avgRating = ratedAlbums.length
    ? ratedAlbums.reduce((sum, a) => sum + (a.avgRating ?? 0), 0) / ratedAlbums.length
    : null;

  const artistImage = artist?.images[0]?.url ?? null;
  const followers = artist?.followers?.total ?? null;

  if (!artist && albums.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <p className="text-[#888]">Artist not found.</p>
      </div>
    );
  }

  // Combine DB albums with any freshly fetched Spotify ones
  const allAlbumsToShow = albums.length > 0 ? albums : spotifyAlbums.map((a) => ({
    id: a.id,
    title: a.name,
    artistName: a.artists[0]?.name ?? displayName,
    artistId,
    releaseYear: parseInt(a.release_date?.slice(0, 4) ?? "0", 10),
    coverUrl: a.images[0]?.url ?? null,
    genres: a.genres ?? [],
    avgRating: null,
    ratingCount: 0,
  }));

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      {/* Hero */}
      <div className="flex flex-col sm:flex-row gap-8 mb-10">
        {artistImage && (
          <div className="shrink-0">
            <Image
              src={artistImage}
              alt={displayName}
              width={180}
              height={180}
              className="rounded-full object-cover w-[140px] h-[140px] sm:w-[180px] sm:h-[180px] border-2 border-[rgba(255,255,255,0.1)]"
              sizes="180px"
            />
          </div>
        )}
        <div className="flex-1">
          <p className="text-[#888] text-xs uppercase tracking-widest mb-1">Artist</p>
          <h1 className="text-4xl font-bold text-[#F5F2EB] mb-3" style={{ fontFamily: "Playfair Display, serif" }}>
            {displayName}
          </h1>
          <div className="flex flex-wrap items-center gap-4 text-sm text-[#888] mb-4">
            {followers != null && (
              <span>{(followers / 1_000_000).toFixed(1)}M followers on Spotify</span>
            )}
            {allAlbumsToShow.length > 0 && (
              <span>{allAlbumsToShow.length} album{allAlbumsToShow.length !== 1 ? "s" : ""}</span>
            )}
            {totalRatings > 0 && (
              <span>{totalRatings.toLocaleString()} ratings</span>
            )}
            {avgRating != null && (
              <span className="text-[#E8B84B] font-semibold">★ {avgRating.toFixed(2)} avg</span>
            )}
            {artist?.popularity != null && (
              <span>Popularity {artist.popularity}/100</span>
            )}
          </div>
          {allGenres.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {allGenres.slice(0, 8).map((g) => <GenreTag key={g} genre={g} />)}
            </div>
          )}
        </div>
      </div>

      {/* Discography */}
      {allAlbumsToShow.length > 0 && (
        <>
          <h2 className="text-xl font-semibold text-[#F5F2EB] mb-6" style={{ fontFamily: "Playfair Display, serif" }}>
            Discography
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {allAlbumsToShow.map((album) => (
              <Link key={album.id} href={`/album/${album.id}`} className="group">
                <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
                  {album.coverUrl ? (
                    <Image
                      src={album.coverUrl}
                      alt={album.title}
                      width={200}
                      height={200}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      sizes="200px"
                    />
                  ) : (
                    <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-4xl">♪</div>
                  )}
                </div>
                <p className="text-[#F5F2EB] text-sm font-medium truncate group-hover:text-[#E8B84B] transition-colors">
                  {album.title}
                </p>
                <div className="flex items-center justify-between">
                  <p className="text-[#555] text-xs">{album.releaseYear}</p>
                  {album.avgRating != null && (
                    <p className="text-[#E8B84B] text-xs font-semibold">★ {album.avgRating.toFixed(1)}</p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
