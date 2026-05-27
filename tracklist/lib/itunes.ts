import type { SpotifyAlbum } from "./spotify";
import { spotifyAlbumToDbAlbum } from "./spotify";
import { prisma } from "./prisma";

// Auth-free album data via the public iTunes Search API and Apple Music RSS feed.
// Returns objects shaped like SpotifyAlbum so existing consumers work unchanged.

function bigArtwork(url: string | undefined): string | null {
  if (!url) return null;
  return url.replace(/\/\d+x\d+bb\./, "/600x600bb.");
}

interface ItunesSearchResult {
  collectionId?: number;
  collectionName?: string;
  artistId?: number;
  artistName?: string;
  releaseDate?: string;
  artworkUrl100?: string;
  primaryGenreName?: string;
  trackCount?: number;
  wrapperType?: string;
}

function searchResultToAlbum(r: ItunesSearchResult): SpotifyAlbum | null {
  if (!r.collectionId || !r.collectionName) return null;
  const cover = bigArtwork(r.artworkUrl100);
  return {
    id: String(r.collectionId),
    name: r.collectionName,
    artists: [{ id: r.artistId ? String(r.artistId) : "", name: r.artistName ?? "Unknown Artist" }],
    release_date: r.releaseDate ?? "",
    images: cover ? [{ url: cover, width: 600, height: 600 }] : [],
    genres: r.primaryGenreName ? [r.primaryGenreName.toLowerCase()] : [],
    total_tracks: r.trackCount ?? 0,
  };
}

export async function itunesSearchAlbums(query: string, limit = 10): Promise<SpotifyAlbum[]> {
  const res = await fetch(
    `https://itunes.apple.com/search?term=${encodeURIComponent(query)}&entity=album&limit=${limit}`,
    { next: { revalidate: 3600 } }
  );
  if (!res.ok) return [];
  const data = (await res.json()) as { results?: ItunesSearchResult[] };
  return (data.results ?? [])
    .map(searchResultToAlbum)
    .filter((a): a is SpotifyAlbum => a !== null);
}

export async function itunesLookupAlbum(id: string): Promise<SpotifyAlbum | null> {
  const res = await fetch(
    `https://itunes.apple.com/lookup?id=${encodeURIComponent(id)}&entity=album`,
    { next: { revalidate: 86400 } }
  );
  if (!res.ok) return null;
  const data = (await res.json()) as { results?: ItunesSearchResult[] };
  const collection = (data.results ?? []).find((r) => r.wrapperType === "collection") ?? data.results?.[0];
  return collection ? searchResultToAlbum(collection) : null;
}

// Apple's legacy per-genre "top albums" RSS chart. Genre IDs:
// 14 Pop, 18 Hip-Hop/Rap, 21 Rock, 20 Alternative, 15 R&B/Soul,
// 7 Electronic, 17 Dance, 6 Country, 11 Jazz, 10 Singer/Songwriter,
// 12 Latin, 24 Reggae, 5 Classical, 19 World, 1153 K-Pop.
export const ITUNES_GENRES: Record<string, number> = {
  pop: 14,
  "hip-hop/rap": 18,
  rock: 21,
  alternative: 20,
  "r&b/soul": 15,
  electronic: 7,
  dance: 17,
  country: 6,
  jazz: 11,
  "singer/songwriter": 10,
  latin: 12,
  reggae: 24,
};

interface LegacyEntry {
  "im:name"?: { label?: string };
  "im:image"?: Array<{ label?: string }>;
  "im:artist"?: { label?: string };
  "im:releaseDate"?: { label?: string };
  id?: { attributes?: { "im:id"?: string } };
  category?: { attributes?: { label?: string } };
}

export async function itunesTopAlbumsByGenre(genreId: number, limit = 50): Promise<SpotifyAlbum[]> {
  const res = await fetch(
    `https://itunes.apple.com/us/rss/topalbums/limit=${limit}/genre=${genreId}/json`,
    { next: { revalidate: 86400 } }
  );
  if (!res.ok) return [];
  const data = (await res.json()) as { feed?: { entry?: LegacyEntry | LegacyEntry[] } };
  const raw = data.feed?.entry;
  const entries = Array.isArray(raw) ? raw : raw ? [raw] : [];
  return entries
    .map((e): SpotifyAlbum | null => {
      const id = e.id?.attributes?.["im:id"];
      const name = e["im:name"]?.label;
      if (!id || !name) return null;
      const images = e["im:image"] ?? [];
      const cover = bigArtwork(images[images.length - 1]?.label);
      const genre = e.category?.attributes?.label;
      return {
        id,
        name,
        artists: [{ id: "", name: e["im:artist"]?.label ?? "Unknown Artist" }],
        release_date: e["im:releaseDate"]?.label ?? "",
        images: cover ? [{ url: cover, width: 600, height: 600 }] : [],
        genres: genre ? [genre.toLowerCase()] : [],
        total_tracks: 0,
      };
    })
    .filter((a): a is SpotifyAlbum => a !== null);
}

interface RssResult {
  id?: string;
  name?: string;
  artistName?: string;
  artworkUrl100?: string;
  releaseDate?: string;
  genres?: Array<{ name?: string }>;
}

// Persist fetched albums so /album/[id] resolves them from the DB and the
// catalog fills over time. Apple's RSS feed IDs don't resolve via the iTunes
// lookup API, so caching on display is what makes those albums clickable.
export async function cacheAlbums(albums: SpotifyAlbum[]): Promise<void> {
  await Promise.allSettled(
    albums.map((a) => {
      const data = spotifyAlbumToDbAlbum(a);
      if (!data.id) return Promise.resolve();
      return prisma.album.upsert({
        where: { id: data.id },
        update: { coverUrl: data.coverUrl, genres: data.genres },
        create: data,
      });
    })
  );
}

export async function itunesTopAlbums(limit = 20): Promise<SpotifyAlbum[]> {
  const res = await fetch(
    `https://rss.applemarketingtools.com/api/v2/us/music/most-played/${limit}/albums.json`,
    { next: { revalidate: 3600 } }
  );
  if (!res.ok) return [];
  const data = (await res.json()) as { feed?: { results?: RssResult[] } };
  return (data.feed?.results ?? [])
    .map((r): SpotifyAlbum | null => {
      if (!r.id || !r.name) return null;
      const cover = bigArtwork(r.artworkUrl100);
      const genres = (r.genres ?? [])
        .map((g) => g.name?.toLowerCase())
        .filter((g): g is string => !!g && g !== "music");
      return {
        id: r.id,
        name: r.name,
        artists: [{ id: "", name: r.artistName ?? "Unknown Artist" }],
        release_date: r.releaseDate ?? "",
        images: cover ? [{ url: cover, width: 600, height: 600 }] : [],
        genres,
        total_tracks: 0,
      };
    })
    .filter((a): a is SpotifyAlbum => a !== null);
}
