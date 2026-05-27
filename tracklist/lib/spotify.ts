const SPOTIFY_BASE = "https://api.spotify.com/v1";

async function getAccessToken(): Promise<string> {
  const res = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(
        `${process.env.SPOTIFY_CLIENT_ID}:${process.env.SPOTIFY_CLIENT_SECRET}`
      ).toString("base64")}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
    next: { revalidate: 3500 },
  });
  const data = await res.json();
  return data.access_token;
}

export interface SpotifyAlbum {
  id: string;
  name: string;
  album_type?: string;
  artists: Array<{ id: string; name: string }>;
  release_date: string;
  images: Array<{ url: string; width: number; height: number }>;
  genres: string[];
  tracks?: { items: Array<{ id: string; name: string; duration_ms: number; track_number: number }> };
  total_tracks: number;
  popularity?: number;
}

export interface SpotifyArtist {
  id: string;
  name: string;
  images: Array<{ url: string; width: number; height: number }>;
  genres: string[];
  followers: { total: number };
  popularity: number;
}

export async function searchAlbums(query: string): Promise<SpotifyAlbum[]> {
  const token = await getAccessToken();
  const res = await fetch(
    `${SPOTIFY_BASE}/search?q=${encodeURIComponent(query)}&type=album&limit=10`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  const data = await res.json();
  return data.albums?.items ?? [];
}

export async function getAlbum(spotifyId: string): Promise<SpotifyAlbum> {
  const token = await getAccessToken();
  const res = await fetch(`${SPOTIFY_BASE}/albums/${spotifyId}`, {
    headers: { Authorization: `Bearer ${token}` },
    next: { revalidate: 86400 },
  });
  return res.json();
}

export async function getNewReleases(limit = 20): Promise<SpotifyAlbum[]> {
  const token = await getAccessToken();
  const res = await fetch(
    `${SPOTIFY_BASE}/browse/new-releases?limit=${limit}&country=US`,
    {
      headers: { Authorization: `Bearer ${token}` },
      next: { revalidate: 3600 },
    }
  );
  const data = await res.json();
  return data.albums?.items ?? [];
}

export async function getArtist(artistId: string): Promise<SpotifyArtist> {
  const token = await getAccessToken();
  const res = await fetch(`${SPOTIFY_BASE}/artists/${artistId}`, {
    headers: { Authorization: `Bearer ${token}` },
    next: { revalidate: 86400 },
  });
  return res.json();
}

export async function getArtistAlbums(artistId: string, limit = 10): Promise<SpotifyAlbum[]> {
  const token = await getAccessToken();
  const res = await fetch(
    `${SPOTIFY_BASE}/artists/${artistId}/albums?limit=${limit}&album_type=album&market=US`,
    {
      headers: { Authorization: `Bearer ${token}` },
      next: { revalidate: 86400 },
    }
  );
  const data = await res.json();
  return data.items ?? [];
}

export async function searchArtists(query: string): Promise<SpotifyArtist[]> {
  const token = await getAccessToken();
  const res = await fetch(
    `${SPOTIFY_BASE}/search?q=${encodeURIComponent(query)}&type=artist&limit=5`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  const data = await res.json();
  return data.artists?.items ?? [];
}

export function spotifyAlbumToDbAlbum(album: SpotifyAlbum) {
  // release_date may be ISO ("2024-01-31") or human ("December 13, 2024"),
  // so find any 4-digit year rather than slicing, to avoid NaN.
  const yearMatch = album.release_date?.match(/\d{4}/);
  return {
    id: album.id,
    title: album.name,
    artistName: album.artists[0]?.name ?? "Unknown Artist",
    artistId: album.artists[0]?.id ?? "",
    releaseYear: yearMatch ? parseInt(yearMatch[0], 10) : 0,
    coverUrl: album.images[0]?.url ?? null,
    genres: album.genres ?? [],
  };
}
