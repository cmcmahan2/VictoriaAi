import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getAlbum, spotifyAlbumToDbAlbum } from "@/lib/spotify";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const cached = await prisma.album.findUnique({ where: { id } });
  if (cached) return NextResponse.json(cached);

  try {
    const spotifyAlbum = await getAlbum(id);
    const data = spotifyAlbumToDbAlbum(spotifyAlbum);
    const album = await prisma.album.upsert({
      where: { id },
      update: {},
      create: data,
    });
    return NextResponse.json({ ...album, tracks: spotifyAlbum.tracks?.items });
  } catch {
    return NextResponse.json({ error: "Album not found" }, { status: 404 });
  }
}
