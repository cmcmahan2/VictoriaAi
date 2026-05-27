import { NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { prisma } from "@/lib/prisma";

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

export async function GET(_req: Request, { params }: { params: Promise<{ albumId: string }> }) {
  const { albumId } = await params;

  const album = await prisma.album.findUnique({
    where: { id: albumId },
    select: { id: true, title: true, artistName: true, releaseYear: true, genres: true, description: true },
  }).catch(() => null);

  if (!album) return NextResponse.json({ error: "Album not found" }, { status: 404 });

  // Return cached blurb if available
  if (album.description) return NextResponse.json({ description: album.description });

  if (!process.env.ANTHROPIC_API_KEY) {
    return NextResponse.json({ description: null });
  }

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

    // Cache in DB — fire-and-forget, don't let a write failure block the response
    prisma.album.update({ where: { id: albumId }, data: { description: text } }).catch(() => {});

    return NextResponse.json({ description: text });
  } catch {
    return NextResponse.json({ description: null });
  }
}
