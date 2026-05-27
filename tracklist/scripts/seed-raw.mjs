import pg from "pg";
const { Client } = pg;

const client = new Client({
  connectionString: "postgresql://postgres.rtdoumwjenmzdegxydoh:3727west18thavevancouverbc@aws-1-us-east-1.pooler.supabase.com:5432/postgres",
  ssl: { rejectUnauthorized: false },
  connectionTimeoutMillis: 10000,
});

const ALBUMS = [
  { id: "4eLPsYPBmXABThSJ821sqY", title: "DAMN.", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2017, coverUrl: "https://i.scdn.co/image/ab67616d0000b2738b52c6b9bc4e43d873869699", genres: ["hip-hop","rap"] },
  { id: "7ycBtnsMtyVbbwTfJwRjSP", title: "To Pimp a Butterfly", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2015, coverUrl: "https://i.scdn.co/image/ab67616d0000b273cdb645498cd3d8a2db4d05e1", genres: ["hip-hop","jazz rap"] },
  { id: "0hvT3yIEysuRQ5r3L2a4Ge", title: "GNX", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2024, coverUrl: "https://i.scdn.co/image/ab67616d0000b2731ea0c62b2339c9d1af0dc830", genres: ["hip-hop","rap"] },
  { id: "20r762YmB5HeofjMCiPMLv", title: "My Beautiful Dark Twisted Fantasy", artistName: "Kanye West", artistId: "5K4W6rqBFWDnAN6FQUkS6x", releaseYear: 2010, coverUrl: "https://i.scdn.co/image/ab67616d0000b2732b3b8e4a4a5b2b3f4f1e9c7d", genres: ["hip-hop","rap"] },
  { id: "5DEXqhYLXCmDOLgSm5OmO7", title: "The College Dropout", artistName: "Kanye West", artistId: "5K4W6rqBFWDnAN6FQUkS6x", releaseYear: 2004, coverUrl: null, genres: ["hip-hop","soul rap"] },
  { id: "2ODvWsOgouMbaA5xf0RkJe", title: "After Hours", artistName: "The Weeknd", artistId: "1Xyo4u8uXC1ZmMpatF05PJ", releaseYear: 2020, coverUrl: "https://i.scdn.co/image/ab67616d0000b2738863bc11d2aa12b54f5aeb36", genres: ["r&b","synthpop"] },
  { id: "5NsdZGgaVcwdoAiPmRwnLQ", title: "Starboy", artistName: "The Weeknd", artistId: "1Xyo4u8uXC1ZmMpatF05PJ", releaseYear: 2016, coverUrl: "https://i.scdn.co/image/ab67616d0000b2734718e2b124f79258be7bc452", genres: ["r&b","pop"] },
  { id: "1x3gXrjd79DmsPAMNKCbnG", title: "Dawn FM", artistName: "The Weeknd", artistId: "1Xyo4u8uXC1ZmMpatF05PJ", releaseYear: 2022, coverUrl: null, genres: ["synthpop","r&b"] },
  { id: "4OHDEiU6yu4GFn0AH7CuIM", title: "SOS", artistName: "SZA", artistId: "7tYKF4w9nC0nq9CsPZTHyP", releaseYear: 2022, coverUrl: "https://i.scdn.co/image/ab67616d0000b2730c471c36970b9406449bf8e5", genres: ["r&b","pop","soul"] },
  { id: "2FEzOBXe0TBGKP9VFq6t0t", title: "Ctrl", artistName: "SZA", artistId: "7tYKF4w9nC0nq9CsPZTHyP", releaseYear: 2017, coverUrl: null, genres: ["r&b","neo soul"] },
  { id: "151w1FgRZfnKZA9FEcg9Z3", title: "Midnights", artistName: "Taylor Swift", artistId: "06HL4z0CvFAxyc27GXpf02", releaseYear: 2022, coverUrl: "https://i.scdn.co/image/ab67616d0000b2738655744dce6af24879e17299", genres: ["pop","synth-pop"] },
  { id: "2Xoteh7uEpea4TohTxkAyd", title: "folklore", artistName: "Taylor Swift", artistId: "06HL4z0CvFAxyc27GXpf02", releaseYear: 2020, coverUrl: null, genres: ["indie pop","folk-pop"] },
  { id: "5MfAxS5zz8MlfROjGQVXhy", title: "1989", artistName: "Taylor Swift", artistId: "06HL4z0CvFAxyc27GXpf02", releaseYear: 2014, coverUrl: "https://i.scdn.co/image/ab67616d0000b27362e4e22ec03a46d43a9aad48", genres: ["pop","synth-pop"] },
  { id: "5vkqYmiPBYLaalcmjujWxK", title: "In Rainbows", artistName: "Radiohead", artistId: "4Z8W4fKeB5YxbusRsdQVPb", releaseYear: 2007, coverUrl: "https://i.scdn.co/image/ab67616d0000b273de3c04b5fc750b68899b20a9", genres: ["alternative rock","art rock"] },
  { id: "5MgX84d2iSAJwlzxm5n3At", title: "Future Nostalgia", artistName: "Dua Lipa", artistId: "6M2wZ9GZgrQXHCFfjv46we", releaseYear: 2020, coverUrl: "https://i.scdn.co/image/ab67616d0000b27350a3147b4edd7701a876c6ce", genres: ["pop","disco","nu-disco"] },
  { id: "4PWBTB6NYSKQwfo79I3prg", title: "Hit Me Hard and Soft", artistName: "Billie Eilish", artistId: "6qqNVTkY8uBg9cP3Jd7DAH", releaseYear: 2024, coverUrl: null, genres: ["pop","indie pop"] },
  { id: "0S0KGZnfBGSIssfF54WSJh", title: "When We All Fall Asleep, Where Do We Go?", artistName: "Billie Eilish", artistId: "6qqNVTkY8uBg9cP3Jd7DAH", releaseYear: 2019, coverUrl: null, genres: ["electropop","pop"] },
  { id: "2B1JNt4pPjxMjqrR0P6FQL", title: "Melodrama", artistName: "Lorde", artistId: "163tK9Wjr9P9DmM0AVK7lm", releaseYear: 2017, coverUrl: "https://i.scdn.co/image/ab67616d0000b273a6ae7f1e63a78819ae82f8da", genres: ["indie pop","art pop","synth-pop"] },
  { id: "40GbmNE8wBPbr8aVTHlBNr", title: "Take Care", artistName: "Drake", artistId: "3TVXtAsR1Inumwj472S9r4", releaseYear: 2011, coverUrl: null, genres: ["hip-hop","r&b"] },
  { id: "6FJxoadUE4JNVwWHghBwnb", title: "Lemonade", artistName: "Beyoncé", artistId: "6vWDO969PvNqNYHIOW5v0m", releaseYear: 2016, coverUrl: "https://i.scdn.co/image/ab67616d0000b27327454521a0b5c5c51b2f8413", genres: ["r&b","pop","soul"] },
  { id: "4VZ7jhV0wHpoNPCB7Fh0aC", title: "Short n' Sweet", artistName: "Sabrina Carpenter", artistId: "74KM79TiuVKeVCqs8QtB0B", releaseYear: 2024, coverUrl: null, genres: ["pop"] },
  { id: "2lIZef4lzdvZkiiCzvPKj7", title: "BRAT", artistName: "Charli XCX", artistId: "25uiPmTg16RbhZWAqwLBy5", releaseYear: 2024, coverUrl: null, genres: ["pop","electropop","hyperpop"] },
  { id: "2guirTSEqLizK7j9i1MTTZ", title: "Nevermind", artistName: "Nirvana", artistId: "6olE6TJLqED3rqDCT0FyPh", releaseYear: 1991, coverUrl: "https://i.scdn.co/image/ab67616d0000b27328933b808bfb4cbbd0385400", genres: ["grunge","alternative rock"] },
  { id: "2ANVost0y2y52ema1E9xAZ", title: "Thriller", artistName: "Michael Jackson", artistId: "3fMbdgg4jU18AjLCKBhRSm", releaseYear: 1982, coverUrl: "https://i.scdn.co/image/ab67616d0000b2734121faee8df82c526cbab2be", genres: ["pop","r&b","funk"] },
  { id: "1bt6q2SruixD3YNVtD7bDi", title: "Rumours", artistName: "Fleetwood Mac", artistId: "08GQAI4eElDnROmtQ8zbkN", releaseYear: 1977, coverUrl: null, genres: ["classic rock","soft rock"] },
  { id: "3kEtdS2pH5bReSDQKe9nyM", title: "Illmatic", artistName: "Nas", artistId: "20qISvAhX20dpIbOOzGK3q", releaseYear: 1994, coverUrl: "https://i.scdn.co/image/ab67616d0000b2731030e0f56af36e3b2a6e0099", genres: ["hip-hop","east coast hip-hop"] },
  { id: "2PXy9USIJiTBMNKGS1YAgY", title: "Stankonia", artistName: "OutKast", artistId: "1G9G7WwrXka3Z1r7aIDjI7", releaseYear: 2000, coverUrl: null, genres: ["hip-hop","funk","southern rap"] },
  { id: "3s8CFG5iEm2dBtNP22mjVT", title: "Imaginal Disk", artistName: "Magdalena Bay", artistId: "1hzfo8twXdOegF3xireCYs", releaseYear: 2024, coverUrl: null, genres: ["synth-pop","indie pop","electropop"] },
  { id: "41MnTivkwTO3UUJ8DrqEJJ", title: "good kid, m.A.A.d city", artistName: "Kendrick Lamar", artistId: "2YZyLoL8N0Wb9xBt1NhZWg", releaseYear: 2012, coverUrl: null, genres: ["hip-hop","west coast rap"] },
  { id: "2PjlaxLMDmZn41ovBqwMQj", title: "The Dark Side of the Moon", artistName: "Pink Floyd", artistId: "0k17h0D3J5VfsdmQ1iZtE9", releaseYear: 1973, coverUrl: "https://i.scdn.co/image/ab67616d0000b273ea7caaff71dea1051d49b2fe", genres: ["progressive rock","psychedelic rock"] },
  { id: "78bpIziExqiI9qztvNFlQu", title: "Abbey Road", artistName: "The Beatles", artistId: "3WrFJ7ztbogyGnTHbHJFl2", releaseYear: 1969, coverUrl: "https://i.scdn.co/image/ab67616d0000b273dc30583ba717007b00cceb25", genres: ["classic rock","rock","pop"] },
];

async function main() {
  console.log("Connecting to Supabase...");
  await client.connect();
  console.log("Connected! Seeding albums...\n");

  let added = 0, errors = 0;

  for (const album of ALBUMS) {
    try {
      await client.query(`
        INSERT INTO "Album" (id, title, "artistName", "artistId", "releaseYear", "coverUrl", genres, "avgRating", "ratingCount")
        VALUES ($1, $2, $3, $4, $5, $6, $7::text[], NULL, 0)
        ON CONFLICT (id) DO UPDATE SET
          "coverUrl" = COALESCE(EXCLUDED."coverUrl", "Album"."coverUrl"),
          genres = EXCLUDED.genres
      `, [album.id, album.title, album.artistName, album.artistId, album.releaseYear, album.coverUrl, album.genres]);
      console.log(`✓ ${album.title}`);
      added++;
    } catch (e) {
      console.log(`✗ ${album.title}: ${e.message}`);
      errors++;
    }
  }

  console.log(`\n✅ Done! ${added} albums seeded, ${errors} errors.`);
  await client.end();
}

main().catch(e => { console.error(e); process.exit(1); });
