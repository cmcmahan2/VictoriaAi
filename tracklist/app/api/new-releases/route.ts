import { NextResponse } from "next/server";
import { getNewReleases } from "@/lib/spotify";

export async function GET() {
  try {
    const albums = await getNewReleases(20);
    return NextResponse.json(albums);
  } catch {
    return NextResponse.json([], { status: 200 });
  }
}
