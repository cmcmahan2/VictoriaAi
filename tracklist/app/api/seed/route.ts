import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { spotifyAlbumToDbAlbum, type SpotifyAlbum } from "@/lib/spotify";
import { itunesSearchAlbums, itunesTopAlbums, itunesTopAlbumsByGenre, ITUNES_GENRES } from "@/lib/itunes";

export const maxDuration = 60;

// Curated list of classic + current albums to seed the DB
const SEED_QUERIES = [
  // New/Current
  "GNX Kendrick Lamar",
  "Short n Sweet Sabrina Carpenter",
  "Brat Charli XCX",
  "Hit Me Hard and Soft Billie Eilish",
  "The Great Impersonator Halsey",
  "Manning Fireworks MJ Lenderman",
  "Imaginal Disk Magdalena Bay",
  "Bright Future Adrianne Lenker",
  "Lives of the Saints Vampire Weekend",
  // All-time classics
  "To Pimp a Butterfly Kendrick Lamar",
  "Blonde Frank Ocean",
  "good kid maad city Kendrick Lamar",
  "My Beautiful Dark Twisted Fantasy Kanye West",
  "In Rainbows Radiohead",
  "OK Computer Radiohead",
  "Thriller Michael Jackson",
  "Abbey Road Beatles",
  "Kind of Blue Miles Davis",
  "Purple Rain Prince",
  "Nevermind Nirvana",
  "The Miseducation of Lauryn Hill",
  "Enter the Wu-Tang Wu-Tang Clan",
  "Illmatic Nas",
  "Ready to Die Notorious BIG",
  "Reasonable Doubt Jay-Z",
  "The College Dropout Kanye West",
  "808s and Heartbreak Kanye West",
  "Channel Orange Frank Ocean",
  "Ctrl SZA",
  "SOS SZA",
  "Future Nostalgia Dua Lipa",
  "Melodrama Lorde",
  "Pure Heroine Lorde",
  "Rumours Fleetwood Mac",
  "Dark Side of the Moon Pink Floyd",
  "Led Zeppelin IV",
  "Born to Run Bruce Springsteen",
  "Achtung Baby U2",
  "Nevermind Nirvana",
  "Doggystyle Snoop Dogg",
  "The Chronic Dr Dre",
  "Aquemini Outkast",
  "Stankonia Outkast",
  "Speakerboxxx The Love Below Outkast",
  "1989 Taylor Swift",
  "folklore Taylor Swift",
  "Midnights Taylor Swift",
  "After Hours The Weeknd",
  "Dawn FM The Weeknd",
  "Starboy The Weeknd",
  "DAMN Kendrick Lamar",
  "Certified Lover Boy Drake",
  "Take Care Drake",
  "If Youre Reading This Its Too Late Drake",
];

async function runSeed() {
  const results = { added: 0, errors: 0 };
  const allAlbums: SpotifyAlbum[] = [];

  // 1. Current top albums (Apple Music most-played)
  try {
    allAlbums.push(...(await itunesTopAlbums(50)));
  } catch { /* ignore */ }

  // 2. Wide, genre-diverse catalog from Apple's per-genre charts (no auth)
  const genreResults = await Promise.allSettled(
    Object.values(ITUNES_GENRES).map((id) => itunesTopAlbumsByGenre(id, 50))
  );
  for (const r of genreResults) {
    if (r.status === "fulfilled") allAlbums.push(...r.value);
  }

  // 3. Curated classics via iTunes search (batched)
  const BATCH_SIZE = 8;
  for (let i = 0; i < SEED_QUERIES.length; i += BATCH_SIZE) {
    const batch = SEED_QUERIES.slice(i, i + BATCH_SIZE);
    const batchResults = await Promise.allSettled(
      batch.map((q) => itunesSearchAlbums(q, 1).then((r) => r[0]).catch(() => null))
    );
    for (const r of batchResults) {
      if (r.status === "fulfilled" && r.value) allAlbums.push(r.value);
    }
  }

  // Deduplicate by id
  const seen = new Set<string>();
  const unique = allAlbums.filter((a) => {
    if (!a?.id || seen.has(a.id)) return false;
    seen.add(a.id);
    return true;
  });

  // Upsert into DB in parallel chunks
  const CHUNK = 25;
  for (let i = 0; i < unique.length; i += CHUNK) {
    const chunk = unique.slice(i, i + CHUNK);
    const settled = await Promise.allSettled(
      chunk.map((album) => {
        const data = spotifyAlbumToDbAlbum(album);
        return prisma.album.upsert({
          where: { id: data.id },
          update: { coverUrl: data.coverUrl, genres: data.genres },
          create: data,
        });
      })
    );
    for (const s of settled) s.status === "fulfilled" ? results.added++ : results.errors++;
  }

  return { ...results, total: unique.length };
}

export async function POST() {
  return NextResponse.json(await runSeed());
}

// GET runs the seed too, so it can be triggered from a browser. Skips if the
// catalog is already populated unless ?force=1 is passed.
export async function GET(req: Request) {
  const force = new URL(req.url).searchParams.get("force") === "1";
  const count = await prisma.album.count().catch(() => 0);
  if (count > 50 && !force) {
    return NextResponse.json({ albumsInDb: count, seeded: false, note: "Already populated. Add ?force=1 to re-run." });
  }
  const result = await runSeed();
  const newCount = await prisma.album.count().catch(() => 0);
  return NextResponse.json({ ...result, albumsInDb: newCount, seeded: true });
}
