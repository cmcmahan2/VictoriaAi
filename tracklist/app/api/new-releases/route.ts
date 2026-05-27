import { NextResponse } from "next/server";
import { getNewReleases } from "@/lib/spotify";
import { itunesTopAlbums } from "@/lib/itunes";

export async function GET() {
  // Prefer Spotify new releases when configured; otherwise fall back to
  // Apple Music top albums (no auth required) so the strip is never empty.
  // No DB writes here — this runs on every homepage load; seeding handles
  // persistence so these albums are clickable (same IDs as the seed).
  try {
    const albums = await getNewReleases(20);
    if (albums.length > 0) return NextResponse.json(albums);
  } catch { /* fall through to iTunes */ }

  try {
    const albums = await itunesTopAlbums(20);
    return NextResponse.json(albums);
  } catch {
    return NextResponse.json([], { status: 200 });
  }
}
