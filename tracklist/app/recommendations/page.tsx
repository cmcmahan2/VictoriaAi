export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { getNewReleases } from "@/lib/spotify";
import { itunesTopAlbums } from "@/lib/itunes";

export default async function RecommendationsPage() {
  const session = await getServerSession(authOptions);
  if (!session?.user) redirect("/login");

  const userId = (session.user as { id?: string }).id;
  if (!userId) redirect("/login");

  // Get user's ratings and their genre preferences
  const [userRatings, userProfile] = await Promise.all([
    prisma.rating.findMany({
      where: { userId },
      include: { album: { select: { id: true, genres: true, avgRating: true } } },
    }),
    prisma.user.findUnique({
      where: { id: userId },
      select: { favoriteGenres: true },
    }),
  ]);

  const ratedAlbumIds = new Set(userRatings.map((r) => r.albumId));

  // Build genre scores from high-rated albums (4+ stars)
  const genreScores: Record<string, number> = {};
  for (const r of userRatings) {
    if (r.value >= 4) {
      for (const genre of r.album.genres) {
        genreScores[genre] = (genreScores[genre] ?? 0) + r.value;
      }
    }
  }

  // Add weight from profile genre preferences
  for (const g of userProfile?.favoriteGenres ?? []) {
    genreScores[g.toLowerCase()] = (genreScores[g.toLowerCase()] ?? 0) + 3;
  }

  const topGenres = Object.entries(genreScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([g]) => g);

  // Find unrated albums matching top genres, sorted by avg rating
  let recommendations = await prisma.album.findMany({
    where: {
      id: { notIn: [...ratedAlbumIds] },
      genres: topGenres.length > 0 ? { hasSome: topGenres } : undefined,
      ratingCount: { gte: 1 },
    },
    orderBy: [{ avgRating: "desc" }, { ratingCount: "desc" }],
    take: 24,
  });

  // Fall back to top-rated if not enough
  if (recommendations.length < 6) {
    const fallback = await prisma.album.findMany({
      where: { id: { notIn: [...ratedAlbumIds] }, ratingCount: { gte: 1 } },
      orderBy: [{ avgRating: "desc" }, { ratingCount: "desc" }],
      take: 24,
    });
    recommendations = fallback;
  }

  // If DB is basically empty, show current top albums (Spotify, else Apple)
  let spotifyRecs: Awaited<ReturnType<typeof getNewReleases>> = [];
  if (recommendations.length < 6) {
    try {
      spotifyRecs = (await getNewReleases(24).catch(() => [])).length
        ? await getNewReleases(24)
        : await itunesTopAlbums(24);
    } catch { /* ignore */ }
  }

  const hasRatings = userRatings.length > 0;

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
          For You
        </h1>
        <p className="text-[#888] mt-1">
          {hasRatings
            ? `Based on your taste in ${topGenres.slice(0, 3).join(", ")}`
            : "Rate some albums to get personalized recommendations"}
        </p>
      </div>

      {!hasRatings && (
        <div className="bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-2xl p-6 mb-8 text-center">
          <p className="text-[#F5F2EB] font-semibold mb-2">Your recommendations are waiting</p>
          <p className="text-[#888] text-sm mb-4">Rate at least 5 albums and we&apos;ll figure out exactly what you&apos;ll love next.</p>
          <Link href="/search" className="bg-[#E8B84B] text-black font-semibold px-6 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors text-sm">
            Find albums to rate →
          </Link>
        </div>
      )}

      {topGenres.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-8">
          <span className="text-[#555] text-xs self-center">Your taste:</span>
          {topGenres.map((g) => (
            <Link key={g} href={`/genre/${encodeURIComponent(g)}`} className="text-xs bg-[#1a1a1a] border border-[rgba(255,255,255,0.08)] text-[#888] rounded-full px-3 py-1 hover:text-[#E8B84B] hover:border-[#E8B84B] transition-all">
              {g}
            </Link>
          ))}
        </div>
      )}

      {recommendations.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {recommendations.map((album) => (
            <Link key={album.id} href={`/album/${album.id}`} className="group">
              <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
                {album.coverUrl ? (
                  <Image src={album.coverUrl} alt={album.title} width={180} height={180} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" sizes="180px" />
                ) : (
                  <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-3xl">♪</div>
                )}
              </div>
              <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{album.title}</p>
              <p className="text-[#555] text-[10px] truncate">{album.artistName}</p>
              {album.avgRating != null && (
                <p className="text-[#E8B84B] text-[10px]">★ {album.avgRating.toFixed(1)}</p>
              )}
            </Link>
          ))}
        </div>
      ) : spotifyRecs.length > 0 ? (
        <>
          <p className="text-[#888] text-xs uppercase tracking-widest mb-5">New on Spotify</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {spotifyRecs.map((a) => (
              <Link key={a.id} href={`/album/${a.id}`} className="group">
                <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
                  {a.images[0]?.url ? (
                    <Image src={a.images[0].url} alt={a.name} fill sizes="180px" className="object-cover group-hover:scale-105 transition-transform duration-300" />
                  ) : (
                    <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-3xl">♪</div>
                  )}
                </div>
                <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{a.name}</p>
                <p className="text-[#555] text-[10px] truncate">{a.artists[0]?.name}</p>
              </Link>
            ))}
          </div>
        </>
      ) : (
        <p className="text-[#888] text-center py-12">No recommendations yet — rate more albums!</p>
      )}
    </div>
  );
}
