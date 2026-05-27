import { NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { prisma } from "@/lib/prisma";

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

export async function GET(_req: Request, { params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = await params;

  // Check if album exists and already has a cached description (raw SQL avoids schema dependency)
  type Row = { description: string | null };
  const rows = await prisma.$queryRaw<Row[]>`
    SELECT "description" FROM "Album" WHERE id = ${albumId} LIMIT 1
  `.catch(() => [] as Row[]);

  if (rows.length === 0) return NextResponse.json({ error: "Album not found" }, { status: 404 });
  if (rows[0].description) return NextResponse.json({ description: rows[0].description });

  if (!process.env.ANTHROPIC_API_KEY) return NextResponse.json({ description: null });

  // Need album metadata for the prompt — fetch from Prisma (no description field)
  const album = await prisma.album.findUnique({
    where: { id: albumId },
    select: { title: true, artistName: true, releaseYear: true, genres: true },
  }).catch(() => null);

  if (!album) return NextResponse.json({ description: null });

  const genreStr = album.genres.length > 0 ? ` (${album.genres.slice(0, 3).join(", ")})` : "";
  const prompt = `Write a 2–3 sentence description of the album "${album.title}" by ${album.artistName}${genreStr}, released in ${album.releaseYear}. Describe the sound, themes, and what makes it notable. Be concise, vivid, and engaging — no spoilers, no lists.`;

  try {
    const message = await anthropic.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 180,
      messages: [{ role: "user", content: prompt }],
    });

    const block = message.content[0];
    const text = block.type === "text" ? block.text.trim() : null;
    if (!text) return NextResponse.json({ description: null });

    // Cache via raw SQL — column exists in DB even though it's not in Prisma schema
    prisma.$executeRaw`
      UPDATE "Album" SET "description" = ${text} WHERE id = ${albumId}
    `.catch(() => {});

    return NextResponse.json({ description: text });
  } catch {
    return NextResponse.json({ description: null });
  }
}
