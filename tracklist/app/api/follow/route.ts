import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const me = (session.user as { id?: string }).id;
  if (!me) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { targetUserId } = await req.json();
  if (!targetUserId || targetUserId === me) {
    return NextResponse.json({ error: "Invalid" }, { status: 400 });
  }

  const existing = await prisma.follow.findUnique({
    where: { followerId_followingId: { followerId: me, followingId: targetUserId } },
  });

  if (existing) {
    await prisma.follow.delete({
      where: { followerId_followingId: { followerId: me, followingId: targetUserId } },
    });
    return NextResponse.json({ following: false });
  } else {
    await prisma.follow.create({ data: { followerId: me, followingId: targetUserId } });
    return NextResponse.json({ following: true });
  }
}

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ following: false });
  const me = (session.user as { id?: string }).id;
  if (!me) return NextResponse.json({ following: false });

  const { searchParams } = new URL(req.url);
  const targetUserId = searchParams.get("targetUserId");
  if (!targetUserId) return NextResponse.json({ following: false });

  const existing = await prisma.follow.findUnique({
    where: { followerId_followingId: { followerId: me, followingId: targetUserId } },
  });
  return NextResponse.json({ following: !!existing });
}
