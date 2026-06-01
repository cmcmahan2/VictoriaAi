import youtubedl from 'youtube-dl-exec';
import fs from 'node:fs';
import path from 'node:path';
import { loadEnv } from '../../lib/env';

export type DownloadResult = {
  localPath: string;          // path to the downloaded video file
  platform: string;          // 'tiktok' | 'instagram' | 'youtube' | 'unknown'
  caption: string | null;    // original platform caption/description
  title: string | null;      // original title (often == caption on TikTok)
  durationSec: number | null;
  sourceId: string | null;   // platform's own id for the clip
  webpageUrl: string | null;
};

// Cheap platform sniff from the URL.
export function detectPlatform(url: string): string {
  const u = url.toLowerCase();
  if (u.includes('tiktok.com')) return 'tiktok';
  if (u.includes('instagram.com')) return 'instagram';
  if (u.includes('youtube.com') || u.includes('youtu.be')) return 'youtube';
  return 'unknown';
}

// Minimal shape of the yt-dlp --dump-single-json payload we rely on.
type FlatInfo = {
  id?: string;
  title?: string;
  description?: string;
  duration?: number;
  webpage_url?: string;
};

// Pull metadata only (no media download) — used to read the caption and to
// name the output file deterministically.
export async function probeMetadata(url: string): Promise<FlatInfo> {
  const info = (await youtubedl(url, {
    dumpSingleJson: true,
    noWarnings: true,
    noPlaylist: true,
  })) as unknown as FlatInfo;
  return info;
}

// Download a single progressive file. We deliberately pick a single-file
// format (best[ext=mp4] / mp4 / best) so yt-dlp never needs ffmpeg to merge
// separate video+audio streams — ffmpeg is not assumed to be installed.
export async function downloadSource(url: string): Promise<DownloadResult> {
  const env = loadEnv();
  const mediaDir = path.resolve(env.MEDIA_DIR);
  fs.mkdirSync(mediaDir, { recursive: true });

  const platform = detectPlatform(url);
  const info = await probeMetadata(url);
  const id = info.id || String(Date.now());
  const prefix = `${platform}-${id}-${Date.now()}`;
  const outputTemplate = path.join(mediaDir, `${prefix}.%(ext)s`);

  await youtubedl(url, {
    output: outputTemplate,
    format: 'best[ext=mp4]/mp4/best',
    noPlaylist: true,
    noWarnings: true,
    noPart: true,
  });

  const localPath = resolveDownloadedFile(mediaDir, prefix);
  if (!localPath) {
    throw new Error('Download completed but no output file was found');
  }

  return {
    localPath,
    platform,
    caption: info.description || info.title || null,
    title: info.title || null,
    durationSec: info.duration ?? null,
    sourceId: id,
    webpageUrl: info.webpage_url || null,
  };
}

// The downloaded extension depends on the source; find the file we just wrote
// by its unique prefix.
function resolveDownloadedFile(dir: string, prefix: string): string | null {
  const match = fs.readdirSync(dir).find((f) => f.startsWith(prefix));
  return match ? path.join(dir, match) : null;
}
