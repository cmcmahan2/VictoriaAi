import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  // Reviews where the reviewer's rating diverges ≥ 1.5 from the album's avg
  const reviews = await prisma.review.findMany({
    where: { rating: { not: null } },
    orderBy: { createdAt: "desc" },
    take: 200,
    include: {
      user: { select: { username: true, avatarUrl: true } },
      album: { select: { id: true, title: true, artistName: true, coverUrl: true, avgRating: true } },
    },
  });

  const hotTakes = reviews
    .filter((r) => {
      if (r.rating == null || r.album.avgRating == null) return false;
      return Math.abs(r.rating - r.album.avgRating) >= 1.5;
    })
    .sort((a, b) => {
      const diffA = Math.abs((a.rating ?? 0) - (a.album.avgRating ?? 0));
      const diffB = Math.abs((b.rating ?? 0) - (b.album.avgRating ?? 0));
      return diffB - diffA;
    })
    .slice(0, 30);

  return NextResponse.json(hotTakes);
}
