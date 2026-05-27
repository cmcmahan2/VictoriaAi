import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const list = await prisma.list.findUnique({ where: { id } });
  if (!list || list.userId !== userId) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const { albumId, note } = await req.json();
  if (!albumId) return NextResponse.json({ error: "albumId required" }, { status: 400 });

  const count = await prisma.listEntry.count({ where: { listId: id } });
  const entry = await prisma.listEntry.create({
    data: { listId: id, albumId, rank: count + 1, note: note ?? null },
  });
  return NextResponse.json(entry);
}
