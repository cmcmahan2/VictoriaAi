import {
  searchMBArtist,
  getMBArtist,
  getWikipediaExtract,
  wikiTitleFromUrl,
} from "@/lib/musicbrainz";

export async function MusicBrainzBio({ artistName }: { artistName: string }) {
  const mbid = await searchMBArtist(artistName);
  if (!mbid) return null;

  const artist = await getMBArtist(mbid);
  if (!artist) return null;

  const wikiRel = artist.relations?.find(
    (r) => r.type === "wikipedia" && r.url?.resource.includes("en.wikipedia")
  );
  const wikiUrl = wikiRel?.url?.resource ?? null;
  const wikiTitle = wikiUrl ? wikiTitleFromUrl(wikiUrl) : null;

  const bio = wikiTitle ? await getWikipediaExtract(wikiTitle) : null;

  const mbUrl = `https://musicbrainz.org/artist/${mbid}`;

  const externalLinks = (artist.relations ?? [])
    .filter(
      (r) =>
        r.url?.resource &&
        ["official homepage", "social network", "streaming music", "last.fm", "discogs"].includes(
          r.type
        )
    )
    .slice(0, 4);

  if (!bio && externalLinks.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      {bio && (
        <div>
          <p className="text-[#aaa] text-sm leading-relaxed line-clamp-4">{bio}</p>
          {wikiUrl && (
            <a
              href={wikiUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[#555] hover:text-[#E8B84B] transition-colors mt-1 inline-block"
            >
              Read more on Wikipedia →
            </a>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-3 text-xs">
        <a
          href={mbUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#555] hover:text-[#E8B84B] transition-colors"
        >
          MusicBrainz
        </a>
        {externalLinks.map((r) => {
          const url = r.url!.resource;
          let label = r.type;
          if (url.includes("last.fm")) label = "Last.fm";
          else if (url.includes("discogs")) label = "Discogs";
          else if (url.includes("twitter") || url.includes("x.com")) label = "Twitter";
          else if (url.includes("instagram")) label = "Instagram";
          else if (r.type === "official homepage") label = "Official site";
          return (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#555] hover:text-[#E8B84B] transition-colors"
            >
              {label}
            </a>
          );
        })}
      </div>
    </div>
  );
}
