import Link from "next/link";
import {
  searchMBReleaseGroup,
  getMBReleaseGroup,
  type MBRelease,
} from "@/lib/musicbrainz";

function formatDate(date?: string) {
  if (!date) return null;
  if (date.length === 4) return date;
  const d = new Date(date);
  if (isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function dedupedEditions(releases: MBRelease[]): MBRelease[] {
  const seen = new Set<string>();
  return releases
    .filter((r) => {
      const key = [r.title, r.disambiguation, r.media?.[0]?.format]
        .filter(Boolean)
        .join("|")
        .toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 8);
}

export async function MusicBrainzInfo({
  artist,
  title,
}: {
  artist: string;
  title: string;
}) {
  const mbid = await searchMBReleaseGroup(artist, title);
  if (!mbid) return null;

  const rg = await getMBReleaseGroup(mbid);
  if (!rg) return null;

  const tags = (rg.tags ?? [])
    .sort((a, b) => b.count - a.count)
    .slice(0, 8)
    .map((t) => t.name);

  const releases = dedupedEditions(rg.releases ?? []);

  const wikiUrl = rg.relations?.find(
    (r) => r.type === "wikipedia" && r.url?.resource.includes("en.wikipedia")
  )?.url?.resource;

  const mbUrl = `https://musicbrainz.org/release-group/${mbid}`;

  if (tags.length === 0 && releases.length === 0) return null;

  return (
    <section className="space-y-4">
      <h3 className="text-sm font-semibold text-[#888] uppercase tracking-widest">
        Release Info
        <span className="text-[#444] font-normal normal-case tracking-normal text-xs ml-2">
          via MusicBrainz
        </span>
      </h3>

      {tags.length > 0 && (
        <div>
          <p className="text-[#555] text-xs mb-2 uppercase tracking-wider">Tags</p>
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={tag}
                className="text-[10px] bg-[#161616] border border-[rgba(255,255,255,0.07)] text-[#888] rounded-full px-2.5 py-0.5"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {releases.length > 0 && (
        <div>
          <p className="text-[#555] text-xs mb-2 uppercase tracking-wider">Editions</p>
          <ul className="space-y-1.5">
            {releases.map((r) => (
              <li key={r.id} className="flex items-start justify-between gap-2 text-xs">
                <span className="text-[#ccc] leading-snug">
                  {r.disambiguation
                    ? `${r.title} — ${r.disambiguation}`
                    : r.title}
                  {r.media?.[0]?.format && (
                    <span className="text-[#555] ml-1">({r.media[0].format})</span>
                  )}
                </span>
                <span className="text-[#555] shrink-0 tabular-nums">
                  {formatDate(r.date)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex gap-3 pt-1">
        <a
          href={mbUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-[#555] hover:text-[#E8B84B] transition-colors"
        >
          MusicBrainz →
        </a>
        {wikiUrl && (
          <a
            href={wikiUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-[#555] hover:text-[#E8B84B] transition-colors"
          >
            Wikipedia →
          </a>
        )}
      </div>
    </section>
  );
}
