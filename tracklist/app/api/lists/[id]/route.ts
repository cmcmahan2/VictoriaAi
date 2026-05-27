import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const list = await prisma.list.findUnique({
    where: { id },
    include: {
      user: { select: { username: true, avatarUrl: true } },
      entries: { orderBy: { rank: "asc" } },
    },
  });
  if (!list) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const albumIds = list.entries.map((e) => e.albumId);
  const albums = await prisma.album.findMany({
    where: { id: { in: albumIds } },
    select: { id: true, title: true, artistName: true, coverUrl: true, releaseYear: true },
  });
  const albumMap = new Map(albums.map((a) => [a.id, a]));

  return NextResponse.json({
    ...list,
    entries: list.entries.map((e) => ({ ...e, album: albumMap.get(e.albumId) })),
  });
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const list = await prisma.list.findUnique({ where: { id } });
  if (!list || list.userId !== userId) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const { title, description, isPublic, entries } = await req.json();

  await prisma.list.update({
    where: { id },
    data: {
      title: title?.trim() ?? list.title,
      description: description?.trim() ?? list.description,
      isPublic: isPublic ?? list.isPublic,
    },
  });

  if (Array.isArray(entries)) {
    await prisma.listEntry.deleteMany({ where: { listId: id } });
    await prisma.listEntry.createMany({
      data: entries.map((e: { albumId: string; rank: number; note?: string }) => ({
        listId: id,
        albumId: e.albumId,
        rank: e.rank,
        note: e.note ?? null,
      })),
    });
  }

  return NextResponse.json({ success: true });
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const list = await prisma.list.findUnique({ where: { id } });
  if (!list || list.userId !== userId) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  await prisma.listEntry.deleteMany({ where: { listId: id } });
  await prisma.list.delete({ where: { id } });
  return NextResponse.json({ success: true });
}
