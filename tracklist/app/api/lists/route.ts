import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const userId = searchParams.get("userId");
  if (!userId) return NextResponse.json({ error: "userId required" }, { status: 400 });

  const lists = await prisma.list.findMany({
    where: { userId, isPublic: true },
    orderBy: { createdAt: "desc" },
    include: {
      _count: { select: { entries: true } },
      entries: {
        orderBy: { rank: "asc" },
        take: 4,
        include: { list: false },
      },
    },
  });

  const albumIds = lists.flatMap((l) => l.entries.map((e) => e.albumId));
  const albums = await prisma.album.findMany({
    where: { id: { in: albumIds } },
    select: { id: true, coverUrl: true, title: true, artistName: true },
  });
  const albumMap = new Map(albums.map((a) => [a.id, a]));

  return NextResponse.json(lists.map((l) => ({
    ...l,
    entries: l.entries.map((e) => ({ ...e, album: albumMap.get(e.albumId) })),
  })));
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { title, description, isPublic } = await req.json();
  if (!title?.trim()) return NextResponse.json({ error: "Title required" }, { status: 400 });

  const list = await prisma.list.create({
    data: { userId, title: title.trim(), description: description?.trim() || null, isPublic: isPublic !== false },
  });
  return NextResponse.json(list);
}
