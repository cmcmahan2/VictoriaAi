import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const albumId = searchParams.get("albumId");
  if (!albumId) return NextResponse.json({ error: "albumId required" }, { status: 400 });

  const posts = await prisma.debatePost.findMany({
    where: { albumId, parentId: null },
    orderBy: { upvotes: "desc" },
    take: 50,
    include: {
      user: { select: { username: true, avatarUrl: true } },
      replies: {
        orderBy: { createdAt: "asc" },
        include: { user: { select: { username: true, avatarUrl: true } } },
      },
    },
  });
  return NextResponse.json(posts);
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { albumId, body, parentId } = await req.json();
  if (!albumId || !body?.trim()) return NextResponse.json({ error: "albumId and body required" }, { status: 400 });

  const post = await prisma.debatePost.create({
    data: { albumId, userId, body: body.trim(), parentId: parentId ?? null },
    include: { user: { select: { username: true, avatarUrl: true } } },
  });
  return NextResponse.json(post);
}

export async function PATCH(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { postId, vote } = await req.json();
  if (!postId || (vote !== "up" && vote !== "down")) {
    return NextResponse.json({ error: "Invalid" }, { status: 400 });
  }

  const post = await prisma.debatePost.update({
    where: { id: postId },
    data: vote === "up" ? { upvotes: { increment: 1 } } : { downvotes: { increment: 1 } },
    select: { upvotes: true, downvotes: true },
  });
  return NextResponse.json(post);
}
