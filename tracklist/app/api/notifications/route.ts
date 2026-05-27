import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json([], { status: 401 });

  const user = session.user as { id?: string };
  if (!user.id) return NextResponse.json([]);

  const notifications = await prisma.notification.findMany({
    where: { recipientId: user.id },
    orderBy: { createdAt: "desc" },
    take: 30,
    include: {
      sender: { select: { username: true, avatarUrl: true } },
    },
  });

  return NextResponse.json(notifications);
}

export async function PATCH() {
  // Mark all as read
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({}, { status: 401 });

  const user = session.user as { id?: string };
  if (!user.id) return NextResponse.json({});

  await prisma.notification.updateMany({
    where: { recipientId: user.id, read: false },
    data: { read: true },
  });

  return NextResponse.json({ ok: true });
}
