import fs from 'node:fs';
import path from 'node:path';

// A player photo sourced legally from Wikimedia/Wikipedia, with the
// attribution string we must show in the video description.
export type PlayerPhoto = {
  name: string;
  localPath: string;
  imageUrl: string;
  license: string;       // e.g. "CC BY-SA 4.0" or "Public domain"
  attribution: string;   // "Photo: <author> via Wikimedia Commons (<license>)"
};

const WIKI_API = 'https://en.wikipedia.org/w/api.php';
// Wikimedia requires a descriptive User-Agent on API requests.
const UA = 'MatchupMaker/1.0 (sports-debate Shorts generator)';

function stripHtml(s: string | undefined): string {
  if (!s) return '';
  return s.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

async function wikiGet(params: Record<string, string>): Promise<any> {
  const url = `${WIKI_API}?${new URLSearchParams({ format: 'json', ...params }).toString()}`;
  const res = await fetch(url, { headers: { 'User-Agent': UA } });
  if (!res.ok) throw new Error(`Wikipedia API ${res.status}`);
  return res.json();
}

// Resolve the main photo for a Wikipedia article title, download it, and
// capture its license + author for attribution. Returns null if no usable
// image is found (caller can fall back to a name-only card).
export async function fetchPlayerPhoto(
  wikiTitle: string,
  displayName: string,
  mediaDir: string,
): Promise<PlayerPhoto | null> {
  try {
    // 1. Original image URL + file title for the article.
    const page = await wikiGet({
      action: 'query',
      prop: 'pageimages',
      piprop: 'original|name',
      titles: wikiTitle,
      redirects: '1',
    });
    const pages = page?.query?.pages || {};
    const first: any = Object.values(pages)[0];
    const imageUrl: string | undefined = first?.original?.source;
    const fileName: string | undefined = first?.pageimage;
    if (!imageUrl || !fileName) return null;

    // 2. License + author metadata for that file.
    let license = 'See Wikimedia Commons';
    let author = '';
    try {
      const info = await wikiGet({
        action: 'query',
        prop: 'imageinfo',
        iiprop: 'extmetadata',
        titles: `File:${fileName}`,
        redirects: '1',
      });
      const ipages = info?.query?.pages || {};
      const ifirst: any = Object.values(ipages)[0];
      const meta = ifirst?.imageinfo?.[0]?.extmetadata || {};
      license = stripHtml(meta?.LicenseShortName?.value) || license;
      author = stripHtml(meta?.Artist?.value);
    } catch {
      // Non-fatal: keep generic license text.
    }

    // 3. Download the image bytes.
    const ext = (path.extname(new URL(imageUrl).pathname) || '.jpg').split('?')[0];
    const safe = displayName.replace(/[^a-z0-9]+/gi, '_').toLowerCase();
    const localPath = path.join(mediaDir, `photo-${safe}${ext}`);
    const imgRes = await fetch(imageUrl, { headers: { 'User-Agent': UA } });
    if (!imgRes.ok) return null;
    const buf = Buffer.from(await imgRes.arrayBuffer());
    fs.writeFileSync(localPath, buf);

    const attribution = `Photo of ${displayName}: ${author || 'Wikimedia Commons'} (${license})`;
    return { name: displayName, localPath, imageUrl, license, attribution };
  } catch {
    return null;
  }
}
