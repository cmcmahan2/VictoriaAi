import { NextResponse } from "next/server";
import { getNewReleases, spotifyAlbumToDbAlbum, type SpotifyAlbum } from "@/lib/spotify";
import { itunesTopAlbums } from "@/lib/itunes";
import { prisma } from "@/lib/prisma";

// Fire-and-forget: cache albums into the DB so /album/[id] resolves them.
// Apple RSS feed IDs don't resolve via the iTunes lookup API, so we must
// persist them here. Bounded to 20 albums, non-blocking.
function cacheInBackground(albums: SpotifyAlbum[]) {
  Promise.allSettled(
    albums.map((a) => {
      const data = spotifyAlbumToDbAlbum(a);
      if (!data.id) return Promise.resolve();
      return prisma.album.upsert({
        where: { id: data.id },
        update: { coverUrl: data.coverUrl },
        create: data,
      });
    })
  ).catch(() => {});
}

export async function GET() {
  try {
    const albums = await getNewReleases(20);
    if (albums.length > 0) {
      cacheInBackground(albums);
      return NextResponse.json(albums);
    }
  } catch { /* fall through to iTunes */ }

  try {
    const albums = await itunesTopAlbums(20);
    cacheInBackground(albums);
    return NextResponse.json(albums);
  } catch {
    return NextResponse.json([], { status: 200 });
  }
}

