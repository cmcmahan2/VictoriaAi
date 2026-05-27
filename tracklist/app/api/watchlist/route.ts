import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json([], { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json([]);

  const items = await prisma.watchlist.findMany({
    where: { userId },
    orderBy: { createdAt: "desc" },
    include: {
      album: true,
    },
  });

  return NextResponse.json(items.map((w) => w.album));
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { albumId } = await req.json();
  if (!albumId) return NextResponse.json({ error: "albumId required" }, { status: 400 });

  const existing = await prisma.watchlist.findUnique({
    where: { userId_albumId: { userId, albumId } },
  });

  if (existing) {
    await prisma.watchlist.delete({ where: { userId_albumId: { userId, albumId } } });
    return NextResponse.json({ saved: false });
  }

  await prisma.watchlist.create({ data: { userId, albumId } });
  return NextResponse.json({ saved: true });
}

export async function DELETE(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const albumId = searchParams.get("albumId");
  if (!albumId) return NextResponse.json({ error: "albumId required" }, { status: 400 });

  await prisma.watchlist.deleteMany({ where: { userId, albumId } });
  return NextResponse.json({ saved: false });
}
