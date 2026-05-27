import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { spotifyAlbumToDbAlbum, type SpotifyAlbum } from "@/lib/spotify";
import { itunesSearchAlbums, itunesTopAlbums } from "@/lib/itunes";

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

export async function POST() {
  const results = { added: 0, skipped: 0, errors: 0 };

  // Grab current top albums from Apple Music (no auth required)
  let topAlbums: SpotifyAlbum[] = [];
  try {
    topAlbums = await itunesTopAlbums(25);
  } catch { /* ignore */ }

  const allAlbums: SpotifyAlbum[] = [...topAlbums];

  // Search and collect from curated list via iTunes (no auth, batched)
  const BATCH_SIZE = 5;
  for (let i = 0; i < SEED_QUERIES.length; i += BATCH_SIZE) {
    const batch = SEED_QUERIES.slice(i, i + BATCH_SIZE);
    const batchResults = await Promise.allSettled(
      batch.map((q) => itunesSearchAlbums(q, 1).then((r) => r[0]).catch(() => null))
    );
    for (const r of batchResults) {
      if (r.status === "fulfilled" && r.value) {
        allAlbums.push(r.value);
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  // Deduplicate by id
  const seen = new Set<string>();
  const unique = allAlbums.filter((a) => {
    if (!a?.id || seen.has(a.id)) return false;
    seen.add(a.id);
    return true;
  });

  // Upsert all into DB
  for (const album of unique) {
    try {
      const data = spotifyAlbumToDbAlbum(album);
      await prisma.album.upsert({
        where: { id: data.id },
        update: { coverUrl: data.coverUrl, genres: data.genres },
        create: data,
      });
      results.added++;
    } catch {
      results.errors++;
    }
  }

  return NextResponse.json({ ...results, total: unique.length });
}

export async function GET() {
  const count = await prisma.album.count();
  return NextResponse.json({ albumsInDb: count });
}
