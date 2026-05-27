import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({}, { status: 401 });
  const me = (session.user as { id?: string }).id;
  if (!me) return NextResponse.json({}, { status: 401 });

  const user = await prisma.user.findUnique({
    where: { id: me },
    select: { username: true, email: true, displayName: true, bio: true, avatarUrl: true, website: true, location: true, favoriteGenres: true },
  });

  return NextResponse.json(user);
}

export async function PATCH(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const me = (session.user as { id?: string }).id;
  if (!me) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const allowed = ["displayName", "bio", "avatarUrl", "website", "location", "favoriteGenres"];
  const data: Record<string, unknown> = {};
  for (const key of allowed) {
    if (key in body) data[key] = body[key];
  }

  const updated = await prisma.user.update({
    where: { id: me },
    data,
    select: { username: true, displayName: true, bio: true, avatarUrl: true, website: true, location: true, favoriteGenres: true },
  });

  return NextResponse.json(updated);
}
