import { NextRequest, NextResponse } from "next/server";
import { searchAlbums } from "@/lib/spotify";
import { itunesSearchAlbums } from "@/lib/itunes";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q");
  if (!q) return NextResponse.json({ error: "Missing query" }, { status: 400 });

  // Prefer Spotify when configured; otherwise fall back to iTunes (no auth).
  // No DB writes here — the album page caches an album on first view.
  try {
    const results = await searchAlbums(q);
    if (results.length > 0) return NextResponse.json(results);
  } catch { /* fall through to iTunes */ }

  try {
    const results = await itunesSearchAlbums(q, 20);
    return NextResponse.json(results);
  } catch {
    return NextResponse.json([], { status: 200 });
  }
}
