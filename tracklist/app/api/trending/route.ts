import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

  // Get albums with recent rating activity, sorted by velocity + avg rating
  const recentRatings = await prisma.rating.groupBy({
    by: ["albumId"],
    where: { createdAt: { gte: sevenDaysAgo } },
    _count: { albumId: true },
    _avg: { value: true },
    orderBy: { _count: { albumId: "desc" } },
    take: 20,
  });

  const albumIds = recentRatings.map((r) => r.albumId);
  const albums = await prisma.album.findMany({
    where: { id: { in: albumIds } },
  });

  const albumMap = new Map(albums.map((a) => [a.id, a]));
  const trending = recentRatings
    .map((r) => albumMap.get(r.albumId))
    .filter(Boolean);

  return NextResponse.json(trending);
}
