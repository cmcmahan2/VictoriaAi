export const dynamic = "force-dynamic";

import Link from "next/link";
import Image from "next/image";
import { prisma } from "@/lib/prisma";
import { GenreTag } from "@/components/ui/GenreTag";

interface PageProps {
  params: Promise<{ artistId: string }>;
}

export default async function ArtistPage({ params }: PageProps) {
  const { artistId } = await params;

  const albums = await prisma.album.findMany({
    where: { artistId },
    orderBy: { releaseYear: "desc" },
  });

  if (albums.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <p className="text-[#888]">No albums found for this artist.</p>
      </div>
    );
  }

  const artist = albums[0];
  const allGenres = [...new Set(albums.flatMap((a) => a.genres))];

  const totalRatings = albums.reduce((sum, a) => sum + a.ratingCount, 0);
  const ratedAlbums = albums.filter((a) => a.avgRating != null);
  const avgRating = ratedAlbums.length
    ? ratedAlbums.reduce((sum, a) => sum + (a.avgRating ?? 0), 0) / ratedAlbums.length
    : null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-4xl font-bold text-[#F5F2EB] mb-2" style={{ fontFamily: "Playfair Display, serif" }}>
          {artist.artistName}
        </h1>
        <div className="flex flex-wrap items-center gap-6 text-sm text-[#888] mb-4">
          <span>{albums.length} album{albums.length !== 1 ? "s" : ""}</span>
          <span>{totalRatings.toLocaleString()} ratings</span>
          {avgRating != null && (
            <span className="text-[#E8B84B] font-semibold">{avgRating.toFixed(2)} avg rating</span>
          )}
        </div>
        {allGenres.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {allGenres.map((g) => <GenreTag key={g} genre={g} />)}
          </div>
        )}
      </div>

      {/* Discography */}
      <h2 className="text-xl font-semibold text-[#F5F2EB] mb-6" style={{ fontFamily: "Playfair Display, serif" }}>
        Discography
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {albums.map((album) => (
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
    </div>
  );
}
