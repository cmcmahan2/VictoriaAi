export const dynamic = "force-dynamic";

import Link from "next/link";
import Image from "next/image";
import { prisma } from "@/lib/prisma";

interface PageProps {
  params: Promise<{ genre: string }>;
}

export default async function GenrePage({ params }: PageProps) {
  const { genre } = await params;
  const decoded = decodeURIComponent(genre);

  const albums = await prisma.album.findMany({
    where: { genres: { has: decoded } },
    orderBy: [{ ratingCount: "desc" }, { avgRating: "desc" }],
    take: 48,
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <div className="mb-8">
        <p className="text-[#888] text-sm uppercase tracking-widest mb-1">Genre</p>
        <h1 className="text-3xl font-bold text-[#F5F2EB] capitalize" style={{ fontFamily: "Playfair Display, serif" }}>
          {decoded}
        </h1>
        <p className="text-[#888] mt-1">{albums.length} album{albums.length !== 1 ? "s" : ""}</p>
      </div>

      {albums.length === 0 ? (
        <div className="text-center py-20 text-[#888]">
          <p>No albums found for this genre yet.</p>
          <Link href="/search" className="text-[#E8B84B] hover:underline mt-2 inline-block">
            Search for albums
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
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
                  <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-3xl">♪</div>
                )}
              </div>
              <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">
                {album.title}
              </p>
              <p className="text-[#555] text-xs truncate">{album.artistName}</p>
              {album.avgRating != null && (
                <p className="text-[#E8B84B] text-xs">★ {album.avgRating.toFixed(1)}</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
