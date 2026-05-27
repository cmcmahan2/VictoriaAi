export const dynamic = "force-dynamic";

import Link from "next/link";
import Image from "next/image";
import { prisma } from "@/lib/prisma";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { getNewReleases, spotifyAlbumToDbAlbum } from "@/lib/spotify";

const RELATED_GENRES: Record<string, string[]> = {
  "hip-hop": ["rap", "west coast rap", "east coast hip-hop", "southern rap"],
  "r&b": ["soul", "neo soul", "funk"],
  "pop": ["synth-pop", "electropop", "indie pop", "art pop"],
  "alternative rock": ["indie rock", "grunge", "art rock"],
  "electronic": ["electropop", "synth-pop", "hyperpop"],
  "indie pop": ["folk-pop", "chamber pop", "art pop"],
};

interface PageProps {
  params: Promise<{ genre: string }>;
}

export default async function GenrePage({ params }: PageProps) {
  const { genre } = await params;
  const decoded = decodeURIComponent(genre).toLowerCase();

  const related = RELATED_GENRES[decoded] ?? [];

  const [albums, topReviewers] = await Promise.all([
    prisma.album.findMany({
      where: { genres: { has: decoded } },
      orderBy: [{ ratingCount: "desc" }, { avgRating: "desc" }],
      take: 48,
    }),
    // Top users who've rated albums in this genre most
    prisma.rating.groupBy({
      by: ["userId"],
      where: { album: { genres: { has: decoded } } },
      _count: { userId: true },
      _avg: { value: true },
      orderBy: { _count: { userId: "desc" } },
      take: 8,
    }),
  ]);

  // Fetch reviewer user details
  const reviewerIds = topReviewers.map((r: { userId: string }) => r.userId);
  const reviewerUsers = await prisma.user.findMany({
    where: { id: { in: reviewerIds } },
    select: { id: true, username: true, avatarUrl: true, displayName: true, _count: { select: { ratings: true } } },
  });
  const reviewerMap = new Map(reviewerUsers.map((u) => [u.id, u]));

  // If no albums in DB, try Spotify
  let spotifyAlbums: Awaited<ReturnType<typeof getNewReleases>> = [];
  if (albums.length === 0) {
    try {
      const releases = await getNewReleases(24);
      spotifyAlbums = releases;
      // Cache them
      await Promise.allSettled(releases.map((a) =>
        prisma.album.upsert({ where: { id: a.id }, update: {}, create: spotifyAlbumToDbAlbum(a) })
      ));
    } catch { /* ignore */ }
  }

  const displayAlbums = albums.length > 0 ? albums : null;

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="mb-8">
        <p className="text-[#888] text-sm uppercase tracking-widest mb-1">Genre</p>
        <h1 className="text-4xl font-bold text-[#F5F2EB] capitalize" style={{ fontFamily: "Playfair Display, serif" }}>
          {decoded}
        </h1>
        <p className="text-[#888] mt-1">{(displayAlbums?.length ?? 0).toLocaleString()} album{(displayAlbums?.length ?? 0) !== 1 ? "s" : ""} rated</p>
      </div>

      {/* Related genres */}
      {related.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-8">
          <span className="text-[#555] text-xs self-center">Related:</span>
          {related.map((g) => (
            <Link key={g} href={`/genre/${encodeURIComponent(g)}`} className="text-xs bg-[#111] border border-[rgba(255,255,255,0.08)] text-[#888] rounded-full px-3 py-1 hover:text-[#E8B84B] hover:border-[#E8B84B] transition-all">
              {g}
            </Link>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        <div className="lg:col-span-3">
          {displayAlbums && displayAlbums.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {displayAlbums.map((album) => (
                <Link key={album.id} href={`/album/${album.id}`} className="group">
                  <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
                    {album.coverUrl ? (
                      <Image src={album.coverUrl} alt={album.title} width={200} height={200} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" sizes="200px" />
                    ) : (
                      <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-3xl">♪</div>
                    )}
                  </div>
                  <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{album.title}</p>
                  <p className="text-[#555] text-xs truncate">{album.artistName}</p>
                  {album.avgRating != null && (
                    <p className="text-[#E8B84B] text-xs">★ {album.avgRating.toFixed(1)} <span className="text-[#555]">({album.ratingCount})</span></p>
                  )}
                </Link>
              ))}
            </div>
          ) : spotifyAlbums.length > 0 ? (
            <>
              <p className="text-[#888] text-xs mb-4">No local ratings yet — showing recent Spotify releases</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {spotifyAlbums.map((a) => (
                  <Link key={a.id} href={`/album/${a.id}`} className="group">
                    <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
                      {a.images[0]?.url ? (
                        <Image src={a.images[0].url} alt={a.name} fill sizes="200px" className="object-cover group-hover:scale-105 transition-transform duration-300" />
                      ) : (
                        <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-3xl">♪</div>
                      )}
                    </div>
                    <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{a.name}</p>
                    <p className="text-[#555] text-xs truncate">{a.artists[0]?.name}</p>
                  </Link>
                ))}
              </div>
            </>
          ) : (
            <div className="text-center py-20">
              <p className="text-[#888]">No albums found for this genre yet.</p>
              <Link href="/search" className="text-[#E8B84B] hover:underline mt-2 inline-block text-sm">Search for albums →</Link>
            </div>
          )}
        </div>

        {/* Sidebar: top listeners */}
        {topReviewers.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Top Listeners</h2>
            <div className="space-y-3">
              {topReviewers.map((r: { userId: string; _count: { userId: number }; _avg: { value: number | null } }) => {
                const u = reviewerMap.get(r.userId);
                if (!u) return null;
                return (
                  <Link key={r.userId} href={`/user/${u.username}`} className="flex items-center gap-2.5 group">
                    <UserAvatar username={u.username} avatarUrl={u.avatarUrl} size={34} />
                    <div className="flex-1 min-w-0">
                      <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">
                        {u.displayName ?? u.username}
                      </p>
                      <p className="text-[#555] text-[10px]">{r._count.userId} rated · ★ {r._avg.value?.toFixed(1)}</p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
