import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { albumId, body, rating } = await req.json();

  if (!albumId || !body?.trim()) {
    return NextResponse.json({ error: "Missing fields" }, { status: 400 });
  }

  const review = await prisma.review.upsert({
    where: { userId_albumId: { userId, albumId } },
    update: { body, rating: rating ?? null, updatedAt: new Date() },
    create: { userId, albumId, body, rating: rating ?? null },
    include: { user: { select: { username: true, avatarUrl: true } } },
  });

  return NextResponse.json(review);
}

export async function GET(req: NextRequest) {
  const albumId = req.nextUrl.searchParams.get("albumId");
  if (!albumId) return NextResponse.json({ error: "Missing albumId" }, { status: 400 });

  const reviews = await prisma.review.findMany({
    where: { albumId },
    orderBy: { createdAt: "desc" },
    include: { user: { select: { username: true, avatarUrl: true } } },
  });

  return NextResponse.json(reviews);
}
