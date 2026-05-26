import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { albumId, value } = await req.json();

  if (!albumId || typeof value !== "number" || value < 0.5 || value > 5) {
    return NextResponse.json({ error: "Invalid rating" }, { status: 400 });
  }

  const rating = await prisma.rating.upsert({
    where: { userId_albumId: { userId, albumId } },
    update: { value },
    create: { userId, albumId, value },
  });

  // Recalculate album average
  const agg = await prisma.rating.aggregate({
    where: { albumId },
    _avg: { value: true },
    _count: true,
  });

  await prisma.album.update({
    where: { id: albumId },
    data: {
      avgRating: agg._avg.value,
      ratingCount: agg._count,
    },
  });

  return NextResponse.json(rating);
}
