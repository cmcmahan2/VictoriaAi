import fs from 'node:fs';
import path from 'node:path';
import { runFfmpeg } from './ffmpeg';

// Concat-demuxer needs forward slashes and escaped quotes.
function concatLine(p: string): string {
  const fwd = p.split(path.sep).join('/');
  return `file '${fwd.replace(/'/g, "'\\''")}'`;
}

// Assemble a vertical 1080x1920 Short: each scene PNG is shown for exactly the
// length of its matching narration mp3, then all segments are concatenated.
// `speed` time-stretches the narration (and thus the pacing) via ffmpeg atempo
// — 1.0 = normal, 1.75 = punchy. Clamped to ffmpeg's 0.5–2.0 atempo range.
export async function assembleVideo(
  scenes: string[],
  audios: string[],
  outPath: string,
  opts: { speed?: number } = {},
): Promise<string> {
  if (scenes.length === 0) throw new Error('No scenes to assemble');
  const n = Math.min(scenes.length, audios.length);
  if (n === 0) throw new Error('No audio to assemble');

  const speed = Math.min(2, Math.max(0.5, opts.speed || 1));

  const dir = path.dirname(outPath);
  fs.mkdirSync(dir, { recursive: true });

  const segments: string[] = [];
  for (let i = 0; i < n; i++) {
    const seg = path.join(dir, `seg-${String(i).padStart(2, '0')}.mp4`);
    const args = [
      '-y',
      '-loop', '1',
      '-i', scenes[i],
      '-i', audios[i],
      '-c:v', 'libx264',
      '-tune', 'stillimage',
      '-pix_fmt', 'yuv420p',
      '-vf', 'scale=1080:1920,setsar=1',
      '-r', '30',
      '-c:a', 'aac',
      '-b:a', '192k',
    ];
    // Speed up the voiceover; the looped image follows via -shortest.
    if (speed !== 1) args.push('-filter:a', `atempo=${speed}`);
    args.push('-shortest', seg);
    await runFfmpeg(args);
    segments.push(seg);
  }

  const listPath = path.join(dir, 'concat.txt');
  fs.writeFileSync(listPath, segments.map(concatLine).join('\n'));

  await runFfmpeg([
    '-y',
    '-f', 'concat',
    '-safe', '0',
    '-i', listPath,
    '-c', 'copy',
    outPath,
  ]);

  return outPath;
}
