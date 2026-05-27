import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const users = await prisma.user.findMany({
    orderBy: { createdAt: "desc" },
    take: 60,
    select: {
      id: true,
      username: true,
      displayName: true,
      avatarUrl: true,
      bio: true,
      favoriteGenres: true,
      _count: { select: { ratings: true, reviews: true, followers: true } },
    },
  });

  return NextResponse.json(users);
}
