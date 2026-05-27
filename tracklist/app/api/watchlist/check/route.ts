import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ saved: false });
  const userId = (session.user as { id?: string }).id;
  if (!userId) return NextResponse.json({ saved: false });

  const { searchParams } = new URL(req.url);
  const albumId = searchParams.get("albumId");
  if (!albumId) return NextResponse.json({ saved: false });

  const entry = await prisma.watchlist.findUnique({
    where: { userId_albumId: { userId, albumId } },
  });

  return NextResponse.json({ saved: !!entry });
}
