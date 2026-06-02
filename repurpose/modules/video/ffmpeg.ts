import { spawn } from 'node:child_process';
// @ts-ignore - package ships no TypeScript types
import ffmpegInstaller from '@ffmpeg-installer/ffmpeg';

// Resolve a usable ffmpeg binary: explicit override → bundled installer →
// whatever is on PATH. The bundled installer means users don't have to
// install ffmpeg themselves.
function resolveFfmpegPath(): string {
  if (process.env.FFMPEG_PATH) return process.env.FFMPEG_PATH;
  try {
    if (ffmpegInstaller?.path) return ffmpegInstaller.path as string;
  } catch {
    // fall through
  }
  return 'ffmpeg';
}

export const FFMPEG_PATH = resolveFfmpegPath();

// Run ffmpeg with the given args, rejecting with the tail of stderr on failure.
export function runFfmpeg(args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn(FFMPEG_PATH, args, { windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', (d) => {
      stderr += d.toString();
    });
    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited ${code}: ${stderr.slice(-600)}`));
    });
  });
}
