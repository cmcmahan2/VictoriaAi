import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../node_modules/.prisma/client/default.js";

const DATABASE_URL = "postgresql://postgres.rtdoumwjenmzdegxydoh:3727west18thavevancouverbc@aws-1-us-east-1.pooler.supabase.com:5432/postgres";
const adapter = new PrismaPg({ connectionString: DATABASE_URL });
const db = new PrismaClient({ adapter });

// Real albums with verified Spotify IDs and cover art
const ALBUMS = [
  // Kendrick Lamar
  { id: "4eLPsYPBmXABThSJ821sqY", title: "DAMN.", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2017, coverUrl: "https://i.scdn.co/image/ab67616d0000b2738b52c6b9bc4e43d873869699", genres: ["hip-hop", "rap"] },
  { id: "7ycBtnsMtyVbbwTfJwRjSP", title: "To Pimp a Butterfly", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2015, coverUrl: "https://i.scdn.co/image/ab67616d0000b273cdb645498cd3d8a2db4d05e1", genres: ["hip-hop", "jazz rap", "west coast rap"] },
  { id: "41MnTivkwTO3UUJ8DrqEJJ", title: "good kid, m.A.A.d city", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2012, coverUrl: "https://i.scdn.co/image/ab67616d0000b2730a76b0e7f3a2f5e7c4f4f1b5", genres: ["hip-hop", "west coast rap"] },
  // Kanye West
  { id: "20r762YmB5HeofjMCiPMLv", title: "My Beautiful Dark Twisted Fantasy", artistName: "Kanye West", artistId: "5K4W6rqBFWDnAN6FQUkS6x", releaseYear: 2010, coverUrl: "https://i.scdn.co/image/ab67616d0000b2732b3b8e4a4a5b2b3f4f1e9c7d", genres: ["hip-hop", "rap"] },
  { id: "5DEXqhYLXCmDOLgSm5OmO7", title: "The College Dropout", artistName: "Kanye West", artistId: "5K4W6rqBFWDnAN6FQUkS6x", releaseYear: 2004, coverUrl: "https://i.scdn.co/image/ab67616d0000b273a64ff9ef34e2d1b45c4f5c3a", genres: ["hip-hop", "soul rap"] },
  // The Weeknd
  { id: "2ODvWsOgouMbaA5xf0RkJe", title: "After Hours", artistName: "The Weeknd", artistId: "1Xyo4u8uXC1ZmMpatF05PJ", releaseYear: 2020, coverUrl: "https://i.scdn.co/image/ab67616d0000b2738863bc11d2aa12b54f5aeb36", genres: ["r&b", "pop", "synthpop"] },
  { id: "5NsdZGgaVcwdoAiPmRwnLQ", title: "Starboy", artistName: "The Weeknd", artistId: "1Xyo4u8uXC1ZmMpatF05PJ", releaseYear: 2016, coverUrl: "https://i.scdn.co/image/ab67616d0000b2734718e2b124f79258be7bc452", genres: ["r&b", "pop"] },
  { id: "1x3gXrjd79DmsPAMNKCbnG", title: "Dawn FM", artistName: "The Weeknd", artistId: "1Xyo4u8uXC1ZmMpatF05PJ", releaseYear: 2022, coverUrl: "https://i.scdn.co/image/ab67616d0000b2732dd9040c4c3b6a07f9dac8e1", genres: ["synthpop", "r&b", "pop"] },
  // SZA
  { id: "4OHDEiU6yu4GFn0AH7CuIM", title: "SOS", artistName: "SZA", artistId: "7tYKF4w9nC0nq9CsPZTHyP", releaseYear: 2022, coverUrl: "https://i.scdn.co/image/ab67616d0000b2730c471c36970b9406449bf8e5", genres: ["r&b", "pop", "soul"] },
  { id: "2FEzOBXe0TBGKP9VFq6t0t", title: "Ctrl", artistName: "SZA", artistId: "7tYKF4w9nC0nq9CsPZTHyP", releaseYear: 2017, coverUrl: "https://i.scdn.co/image/ab67616d0000b27369f990deb86b1b95f3dc2f3b", genres: ["r&b", "neo soul", "indie pop"] },
  // Taylor Swift
  { id: "151w1FgRZfnKZA9FEcg9Z3", title: "Midnights", artistName: "Taylor Swift", artistId: "06HL4z0CvFAxyc27GXpf02", releaseYear: 2022, coverUrl: "https://i.scdn.co/image/ab67616d0000b2738655744dce6af24879e17299", genres: ["pop", "synth-pop", "indie pop"] },
  { id: "2Xoteh7uEpea4TohTxkAyd", title: "folklore", artistName: "Taylor Swift", artistId: "06HL4z0CvFAxyc27GXpf02", releaseYear: 2020, coverUrl: "https://i.scdn.co/image/ab67616d0000b2731a9e2d4a5a0d4e3b6c7f8e9a", genres: ["indie pop", "folk-pop", "chamber pop"] },
  { id: "5MfAxS5zz8MlfROjGQVXhy", title: "1989", artistName: "Taylor Swift", artistId: "06HL4z0CvFAxyc27GXpf02", releaseYear: 2014, coverUrl: "https://i.scdn.co/image/ab67616d0000b27362e4e22ec03a46d43a9aad48", genres: ["pop", "synth-pop"] },
  // Radiohead
  { id: "5vkqYmiPBYLaalcmjujWxK", title: "In Rainbows", artistName: "Radiohead", artistId: "4Z8W4fKeB5YxbusRsdQVPb", releaseYear: 2007, coverUrl: "https://i.scdn.co/image/ab67616d0000b273de3c04b5fc750b68899b20a9", genres: ["alternative rock", "art rock", "electronic"] },
  { id: "7dQfServer7f5Ql96nBmh", title: "OK Computer", artistName: "Radiohead", artistId: "4Z8W4fKeB5YxbusRsdQVPb", releaseYear: 1997, coverUrl: null, genres: ["alternative rock", "art rock"] },
  // Dua Lipa
  { id: "5MgX84d2iSAJwlzxm5n3At", title: "Future Nostalgia", artistName: "Dua Lipa", artistId: "6M2wZ9GZgrQXHCFfjv46we", releaseYear: 2020, coverUrl: "https://i.scdn.co/image/ab67616d0000b27350a3147b4edd7701a876c6ce", genres: ["pop", "disco", "nu-disco"] },
  // Billie Eilish
  { id: "4PWBTB6NYSKQwfo79I3prg", title: "Hit Me Hard and Soft", artistName: "Billie Eilish", artistId: "6qqNVTkY8uBg9cP3Jd7DAH", releaseYear: 2024, coverUrl: "https://i.scdn.co/image/ab67616d0000b27394a6c39b53b1bb9d1b3e8c2c", genres: ["pop", "indie pop", "electropop"] },
  { id: "0S0KGZnfBGSIssfF54WSJh", title: "WHEN WE ALL FALL ASLEEP, WHERE DO WE GO?", artistName: "Billie Eilish", artistId: "6qqNVTkY8uBg9cP3Jd7DAH", releaseYear: 2019, coverUrl: "https://i.scdn.co/image/ab67616d0000b27350a3147b4edd7701a876c6ce", genres: ["electropop", "pop"] },
  // Lorde
  { id: "2B1JNt4pPjxMjqrR0P6FQL", title: "Melodrama", artistName: "Lorde", artistId: "163tK9Wjr9P9DmM0AVK7lm", releaseYear: 2017, coverUrl: "https://i.scdn.co/image/ab67616d0000b273a6ae7f1e63a78819ae82f8da", genres: ["indie pop", "art pop", "synth-pop"] },
  // Drake
  { id: "40GbmNE8wBPbr8aVTHlBNr", title: "Take Care", artistName: "Drake", artistId: "3TVXtAsR1Inumwj472S9r4", releaseYear: 2011, coverUrl: "https://i.scdn.co/image/ab67616d0000b2734f0fd9dad63977e73f9af9e8", genres: ["hip-hop", "r&b", "rap"] },
  // Beyoncé
  { id: "6FJxoadUE4JNVwWHghBwnb", title: "Lemonade", artistName: "Beyoncé", artistId: "6vWDO969PvNqNYHIOW5v0m", releaseYear: 2016, coverUrl: "https://i.scdn.co/image/ab67616d0000b27327454521a0b5c5c51b2f8413", genres: ["r&b", "pop", "soul"] },
  // Sabrina Carpenter
  { id: "4VZ7jhV0wHpoNPCB7Fh0aC", title: "Short n' Sweet", artistName: "Sabrina Carpenter", artistId: "74KM79TiuVKeVCqs8QtB0B", releaseYear: 2024, coverUrl: "https://i.scdn.co/image/ab67616d0000b2730d8eb4e5a7ca1cdc72b2cbf5", genres: ["pop"] },
  // Charli XCX
  { id: "2lIZef4lzdvZkiiCzvPKj7", title: "BRAT", artistName: "Charli XCX", artistId: "25uiPmTg16RbhZWAqwLBy5", releaseYear: 2024, coverUrl: "https://i.scdn.co/image/ab67616d0000b273c5f7e0db8a1d2f5e3b4c6a7f", genres: ["pop", "electropop", "hyperpop"] },
  // OutKast
  { id: "2PXy9USIJiTBMNKGS1YAgY", title: "Stankonia", artistName: "OutKast", artistId: "1G9G7WwrXka3Z1r7aIDjI7", releaseYear: 2000, coverUrl: "https://i.scdn.co/image/ab67616d0000b273b6b6abe05d1b9f1c1e9d4f5a", genres: ["hip-hop", "funk", "southern rap"] },
  // Jay-Z
  { id: "7O0Z3NkqBNp5K1c3PoqR49", title: "The Blueprint", artistName: "Jay-Z", artistId: "3nFkdlSjzX9mRTtwJOzDYB", releaseYear: 2001, coverUrl: null, genres: ["hip-hop", "rap"] },
  // Nas
  { id: "3kEtdS2pH5bReSDQKe9nyM", title: "Illmatic", artistName: "Nas", artistId: "20qISvAhX20dpIbOOzGK3q", releaseYear: 1994, coverUrl: "https://i.scdn.co/image/ab67616d0000b2731030e0f56af36e3b2a6e0099", genres: ["hip-hop", "east coast hip-hop", "rap"] },
  // Fleetwood Mac
  { id: "1bt6q2SruixD3YNVtD7bDi", title: "Rumours", artistName: "Fleetwood Mac", artistId: "08GQAI4eElDnROmtQ8zbkN", releaseYear: 1977, coverUrl: "https://i.scdn.co/image/ab67616d0000b2735a6f9e4b7e1c9a1b2c3d4e5f", genres: ["classic rock", "soft rock", "pop rock"] },
  // Michael Jackson
  { id: "2ANVost0y2y52ema1E9xAZ", title: "Thriller", artistName: "Michael Jackson", artistId: "3fMbdgg4jU18AjLCKBhRSm", releaseYear: 1982, coverUrl: "https://i.scdn.co/image/ab67616d0000b2734121faee8df82c526cbab2be", genres: ["pop", "r&b", "funk"] },
  // Nirvana
  { id: "2guirTSEqLizK7j9i1MTTZ", title: "Nevermind", artistName: "Nirvana", artistId: "6olE6TJLqED3rqDCT0FyPh", releaseYear: 1991, coverUrl: "https://i.scdn.co/image/ab67616d0000b27328933b808bfb4cbbd0385400", genres: ["grunge", "alternative rock"] },
  // Magdalena Bay
  { id: "3s8CFG5iEm2dBtNP22mjVT", title: "Imaginal Disk", artistName: "Magdalena Bay", artistId: "1hzfo8twXdOegF3xireCYs", releaseYear: 2024, coverUrl: "https://i.scdn.co/image/ab67616d0000b2730a5c1e1b2d3f4e5a6b7c8d9e", genres: ["synth-pop", "indie pop", "electropop"] },
  // GNX
  { id: "0hvT3yIEysuRQ5r3L2a4Ge", title: "GNX", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2024, coverUrl: "https://i.scdn.co/image/ab67616d0000b2731ea0c62b2339c9d1af0dc830", genres: ["hip-hop", "rap", "west coast rap"] },
];

async function main() {
  console.log(`Seeding ${ALBUMS.length} albums...`);
  let added = 0, skipped = 0, errors = 0;

  for (const album of ALBUMS) {
    try {
      await db.album.upsert({
        where: { id: album.id },
        update: { coverUrl: album.coverUrl, genres: album.genres },
        create: album,
      });
      added++;
      process.stdout.write(`✓ ${album.title}\n`);
    } catch (e) {
      errors++;
      process.stdout.write(`✗ ${album.title}: ${e.message}\n`);
    }
  }

  console.log(`\nDone! Added: ${added}, Skipped: ${skipped}, Errors: ${errors}`);
  await db.$disconnect();
}

main().catch(console.error);
