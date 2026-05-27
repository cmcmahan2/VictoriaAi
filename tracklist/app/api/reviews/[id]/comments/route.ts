import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const comments = await prisma.reviewComment.findMany({
    where: { reviewId: id },
    orderBy: { createdAt: "asc" },
    include: { user: { select: { username: true, avatarUrl: true } } },
  });
  return NextResponse.json(comments);
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const { body } = await req.json();
  if (!body?.trim()) return NextResponse.json({ error: "Body required" }, { status: 400 });

  const comment = await prisma.reviewComment.create({
    data: { reviewId: id, userId, body: body.trim() },
    include: { user: { select: { username: true, avatarUrl: true } } },
  });
  return NextResponse.json(comment);
}
