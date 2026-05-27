// MusicBrainz open music encyclopedia — no API key required.
// Rate limit: 1 req/sec, but all fetches use next.revalidate so in practice
// each unique resource is only fetched once per day per edge node.

const MB_BASE = "https://musicbrainz.org/ws/2";
const MB_HEADERS = {
  "User-Agent": "Tracklist/1.0 ( https://victoria-ai-jwub.vercel.app )",
  Accept: "application/json",
};

export interface MBRelease {
  id: string;
  title: string;
  date?: string;
  country?: string;
  disambiguation?: string;
  status?: string;
  media?: Array<{ format?: string; "track-count"?: number }>;
}

export interface MBReleaseGroup {
  id: string;
  title: string;
  "primary-type"?: string;
  "secondary-types"?: string[];
  tags?: Array<{ name: string; count: number }>;
  releases?: MBRelease[];
  "artist-credit"?: Array<{ artist?: { id: string; name: string } }>;
  relations?: Array<{ type: string; url?: { resource: string } }>;
}

export interface MBArtist {
  id: string;
  name: string;
  disambiguation?: string;
  tags?: Array<{ name: string; count: number }>;
  relations?: Array<{ type: string; url?: { resource: string } }>;
}

async function mbFetch<T>(path: string): Promise<T | null> {
  try {
    const url = `${MB_BASE}${path}${path.includes("?") ? "&" : "?"}fmt=json`;
    const res = await fetch(url, {
      headers: MB_HEADERS,
      next: { revalidate: 86400 },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function searchMBReleaseGroup(artist: string, title: string): Promise<string | null> {
  const q = encodeURIComponent(`artist:"${artist}" AND release:"${title}"`);
  const data = await mbFetch<{ "release-groups"?: Array<{ id: string }> }>(
    `/release-group?query=${q}&limit=1`
  );
  return data?.["release-groups"]?.[0]?.id ?? null;
}

export async function getMBReleaseGroup(mbid: string): Promise<MBReleaseGroup | null> {
  return mbFetch<MBReleaseGroup>(
    `/release-group/${mbid}?inc=releases+artist-credits+tags+url-rels`
  );
}

export async function searchMBArtist(name: string): Promise<string | null> {
  const q = encodeURIComponent(`artist:"${name}"`);
  const data = await mbFetch<{ artists?: Array<{ id: string }> }>(
    `/artist?query=${q}&limit=1`
  );
  return data?.artists?.[0]?.id ?? null;
}

export async function getMBArtist(mbid: string): Promise<MBArtist | null> {
  return mbFetch<MBArtist>(`/artist/${mbid}?inc=url-rels+tags`);
}

export async function getWikipediaExtract(articleTitle: string): Promise<string | null> {
  try {
    const url =
      `https://en.wikipedia.org/w/api.php?action=query` +
      `&titles=${encodeURIComponent(articleTitle)}` +
      `&prop=extracts&exintro=true&explaintext=true&exsentences=5&format=json&origin=*`;
    const res = await fetch(url, { next: { revalidate: 86400 } });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      query?: { pages?: Record<string, { extract?: string; missing?: string }> };
    };
    const page = Object.values(data.query?.pages ?? {})[0];
    if (!page || "missing" in page) return null;
    const text = page.extract?.trim() ?? "";
    // Skip disambiguation or redirect pages
    if (!text || text.toLowerCase().includes("may refer to")) return null;
    return text;
  } catch {
    return null;
  }
}

// Extracts the Wikipedia article title from a Wikipedia URL.
export function wikiTitleFromUrl(url: string): string | null {
  const match = url.match(/en\.wikipedia\.org\/wiki\/(.+)/);
  if (!match) return null;
  return decodeURIComponent(match[1].replace(/_/g, " "));
}
