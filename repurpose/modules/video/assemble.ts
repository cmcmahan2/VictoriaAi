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
  opts: { speed?: number; animate?: boolean } = {},
): Promise<string> {
  if (scenes.length === 0) throw new Error('No scenes to assemble');
  const n = Math.min(scenes.length, audios.length);
  if (n === 0) throw new Error('No audio to assemble');

  const speed = Math.min(2, Math.max(0.5, opts.speed || 1));
  const animate = opts.animate !== false; // default on

  // Ken Burns: upscale for headroom, then slowly zoom in. Alternate the focal
  // point per scene so consecutive cards don't feel identical. Falls back to a
  // plain scale when animation is disabled.
  function videoFilter(index: number): string {
    if (!animate) return 'scale=1080:1920,setsar=1';
    const zoomIn = index % 2 === 0;
    const z = zoomIn
      ? `'min(zoom+0.0005,1.2)'`
      : `'if(eq(on,0),1.2,max(zoom-0.0005,1.0))'`;
    return (
      `scale=1620:2880,zoompan=z=${z}:d=1500:` +
      `x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,setsar=1`
    );
  }

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
      '-vf', videoFilter(i),
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
