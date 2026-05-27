import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function POST(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const liker = session.user as { id?: string; name?: string | null };
  const { id } = await params;

  const review = await prisma.review.update({
    where: { id },
    data: { likes: { increment: 1 } },
    select: { likes: true, userId: true, albumId: true, album: { select: { title: true } } },
  });

  // Notify the review author (unless they liked their own review)
  if (review.userId !== liker.id && liker.id) {
    await prisma.notification.create({
      data: {
        recipientId: review.userId,
        senderId: liker.id,
        type: "like",
        message: `${liker.name ?? "Someone"} liked your review`,
        link: `/album/${review.albumId}`,
      },
    }).catch(() => {});
  }

  return NextResponse.json({ likes: review.likes });
}
