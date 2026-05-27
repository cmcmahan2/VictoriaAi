import { NextResponse } from "next/server";
import { getNewReleases, spotifyAlbumToDbAlbum, type SpotifyAlbum } from "@/lib/spotify";
import { itunesTopAlbums } from "@/lib/itunes";
import { prisma } from "@/lib/prisma";

// Persist albums into the DB so /album/[id] resolves them. Apple RSS feed IDs
// don't resolve via the iTunes lookup API, so they MUST be cached here while we
// have the data. This is awaited (not fire-and-forget): on serverless, work
// left running after the response is sent gets frozen and never completes, so
// background writes silently drop and album links 404. Batched to stay within
// the connection pool (max 5).
async function cacheAlbums(albums: SpotifyAlbum[]) {
  const BATCH = 5;
  for (let i = 0; i < albums.length; i += BATCH) {
    const batch = albums.slice(i, i + BATCH);
    await Promise.allSettled(
      batch.map((a) => {
        const data = spotifyAlbumToDbAlbum(a);
        if (!data.id) return Promise.resolve();
        return prisma.album.upsert({
          where: { id: data.id },
          update: { coverUrl: data.coverUrl },
          create: data,
        });
      })
    );
  }
}

export async function GET() {
  let albums: SpotifyAlbum[] = [];

  try {
    albums = await getNewReleases(20);
  } catch { /* fall through to iTunes */ }

  if (albums.length === 0) {
    try {
      albums = await itunesTopAlbums(20);
    } catch {
      return NextResponse.json([], { status: 200 });
    }
  }

  await cacheAlbums(albums).catch(() => {});
  return NextResponse.json(albums);
}
