import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const me = (session.user as { id?: string }).id;
  if (!me) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const following = await prisma.follow.findMany({
    where: { followerId: me },
    select: { followingId: true },
  });
  const followingIds = following.map((f: { followingId: string }) => f.followingId);

  const [ratings, reviews] = await Promise.all([
    prisma.rating.findMany({
      where: { userId: { in: followingIds } },
      orderBy: { createdAt: "desc" },
      take: 30,
      include: {
        user: { select: { username: true, avatarUrl: true } },
        album: { select: { id: true, title: true, artistName: true, coverUrl: true } },
      },
    }),
    prisma.review.findMany({
      where: { userId: { in: followingIds } },
      orderBy: { createdAt: "desc" },
      take: 30,
      include: {
        user: { select: { username: true, avatarUrl: true } },
        album: { select: { id: true, title: true, artistName: true, coverUrl: true } },
      },
    }),
  ]);

  type RatingActivity = typeof ratings[number] & { type: "rating" };
  type ReviewActivity = typeof reviews[number] & { type: "review" };

  const feed: (RatingActivity | ReviewActivity)[] = [
    ...ratings.map((r) => ({ ...r, type: "rating" as const })),
    ...reviews.map((r) => ({ ...r, type: "review" as const })),
  ].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()).slice(0, 40);

  return NextResponse.json(feed);
}
