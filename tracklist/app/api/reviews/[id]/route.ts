import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const userId = (session.user as { id?: string }).id;
  const { id } = await params;

  const review = await prisma.review.findUnique({ where: { id } });
  if (!review || review.userId !== userId) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { body, rating } = await req.json();
  const updated = await prisma.review.update({
    where: { id },
    data: { body, rating: rating ?? null },
    include: { user: { select: { username: true, avatarUrl: true } } },
  });

  return NextResponse.json(updated);
}
