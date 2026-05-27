import type { SpotifyAlbum } from "./spotify";

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

interface RssResult {
  id?: string;
  name?: string;
  artistName?: string;
  artworkUrl100?: string;
  releaseDate?: string;
  genres?: Array<{ name?: string }>;
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
