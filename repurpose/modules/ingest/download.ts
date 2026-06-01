// Step 2 (next): download a source clip + its original caption via yt-dlp
// (through the youtube-dl-exec wrapper). Stubbed for the step-1 scaffold so the
// app type-checks and runs; the route returns a clear "not wired yet" error.

export type DownloadResult = {
  localPath: string;          // path to the downloaded .mp4
  platform: string;          // 'tiktok' | 'instagram' | 'youtube' | 'unknown'
  caption: string | null;    // original platform caption/description
  durationSec: number | null;
};

// Cheap platform sniff from the URL — full detection lands with the real
// downloader in step 2.
export function detectPlatform(url: string): string {
  const u = url.toLowerCase();
  if (u.includes('tiktok.com')) return 'tiktok';
  if (u.includes('instagram.com')) return 'instagram';
  if (u.includes('youtube.com') || u.includes('youtu.be')) return 'youtube';
  return 'unknown';
}

export async function downloadSource(_url: string): Promise<DownloadResult> {
  throw new Error(
    'download.ts is a step-1 stub. The yt-dlp-backed downloader is implemented in step 2.',
  );
}
