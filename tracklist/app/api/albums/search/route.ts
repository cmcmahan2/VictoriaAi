import { NextRequest, NextResponse } from "next/server";
import { searchAlbums } from "@/lib/spotify";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q");
  if (!q) return NextResponse.json({ error: "Missing query" }, { status: 400 });

  try {
    const results = await searchAlbums(q);
    return NextResponse.json(results);
  } catch {
    return NextResponse.json({ error: "Search failed" }, { status: 500 });
  }
}
