import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
import type { MatchupPlan } from '../matchup/script';

// Vertical Shorts canvas.
const W = 1080;
const H = 1920;

function esc(s: string): string {
  return (s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Greedy word-wrap into lines of ~maxChars, returned as <tspan> rows.
function wrapTspans(text: string, maxChars: number, x: number, lineHeight: number): string {
  const words = (text || '').split(/\s+/);
  const lines: string[] = [];
  let cur = '';
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > maxChars) {
      if (cur) lines.push(cur);
      cur = w;
    } else {
      cur = (cur + ' ' + w).trim();
    }
  }
  if (cur) lines.push(cur);
  return lines
    .map((ln, i) => `<tspan x="${x}" dy="${i === 0 ? 0 : lineHeight}">${esc(ln)}</tspan>`)
    .join('');
}

// Embed a photo as a base64 data URI clipped into a rounded square, or a
// fallback circle with initials when no photo is available.
function photoBlock(localPath: string | null, name: string, cx: number, cy: number, size: number, clipId: string): string {
  const r = size / 2;
  const initials = name.split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase();
  if (localPath && fs.existsSync(localPath)) {
    const ext = path.extname(localPath).toLowerCase();
    const mime = ext === '.png' ? 'image/png' : ext === '.webp' ? 'image/webp' : 'image/jpeg';
    const b64 = fs.readFileSync(localPath).toString('base64');
    return `
      <clipPath id="${clipId}"><circle cx="${cx}" cy="${cy}" r="${r}"/></clipPath>
      <circle cx="${cx}" cy="${cy}" r="${r + 6}" fill="none" stroke="#ffa657" stroke-width="8"/>
      <image href="data:${mime};base64,${b64}" x="${cx - r}" y="${cy - r}" width="${size}" height="${size}"
             preserveAspectRatio="xMidYMid slice" clip-path="url(#${clipId})"/>`;
  }
  return `
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="#1c2128" stroke="#ffa657" stroke-width="8"/>
    <text x="${cx}" y="${cy + 28}" font-size="84" fill="#8b949e" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">${esc(initials)}</text>`;
}

type SceneKind = 'intro' | 'stats' | 'verdict';

function renderSceneSvg(
  plan: MatchupPlan,
  caption: string,
  kind: SceneKind,
  photoA: string | null,
  photoB: string | null,
): string {
  const photoSize = 300;
  const aCx = W * 0.28;
  const bCx = W * 0.72;
  const photoCy = 360;

  // Middle band differs per scene kind.
  let middle = '';
  if (kind === 'intro') {
    middle = `<text x="${W / 2}" y="${photoCy + 30}" font-size="130" fill="#ffa657" text-anchor="middle" font-family="Arial, sans-serif" font-weight="800">VS</text>`;
  } else if (kind === 'verdict') {
    middle = `
      <text x="${W / 2}" y="720" font-size="74" fill="#e6edf3" text-anchor="middle" font-family="Arial, sans-serif" font-weight="800">WHO'S BETTER?</text>
      <text x="${W / 2}" y="820" font-size="56" fill="#58a6ff" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">Comment 1 or 2 👇</text>`;
  } else {
    // Stats table band.
    const rows = plan.statRows.slice(0, 7);
    const startY = 700;
    const rowH = 110;
    const rowsSvg = rows
      .map((row, i) => {
        const y = startY + i * rowH;
        const aColor = row.edge === 'A' ? '#3fb950' : '#e6edf3';
        const bColor = row.edge === 'B' ? '#3fb950' : '#e6edf3';
        return `
          <text x="${W * 0.30}" y="${y}" font-size="52" fill="${aColor}" text-anchor="end" font-family="Arial, sans-serif" font-weight="700">${esc(row.a)}</text>
          <text x="${W / 2}" y="${y}" font-size="34" fill="#8b949e" text-anchor="middle" font-family="Arial, sans-serif">${esc(row.label)}</text>
          <text x="${W * 0.70}" y="${y}" font-size="52" fill="${bColor}" text-anchor="start" font-family="Arial, sans-serif" font-weight="700">${esc(row.b)}</text>`;
      })
      .join('');
    middle = rowsSvg;
  }

  const captionTspans = wrapTspans(caption, 30, W / 2, 70);

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#0d1117"/>
        <stop offset="1" stop-color="#161b22"/>
      </linearGradient>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#bg)"/>

    ${photoBlock(photoA, plan.playerA.name, aCx, photoCy, photoSize, 'clipA')}
    ${photoBlock(photoB, plan.playerB.name, bCx, photoCy, photoSize, 'clipB')}

    <text x="${aCx}" y="${photoCy + photoSize / 2 + 70}" font-size="44" fill="#e6edf3" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">${esc(plan.playerA.name)}</text>
    <text x="${bCx}" y="${photoCy + photoSize / 2 + 70}" font-size="44" fill="#e6edf3" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">${esc(plan.playerB.name)}</text>

    ${middle}

    <text x="${W / 2}" y="1500" font-size="56" fill="#ffffff" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">${captionTspans}</text>
  </svg>`;
}

// Build one PNG frame per narration beat. Beat 0 = intro, last = verdict,
// the rest show the stat table. Returns the PNG paths in beat order.
// `beats` is passed in so scenes stay aligned with the TTS clips.
export async function buildScenes(
  plan: MatchupPlan,
  beats: string[],
  photoA: string | null,
  photoB: string | null,
  outDir: string,
): Promise<string[]> {
  fs.mkdirSync(outDir, { recursive: true });
  const paths: string[] = [];

  for (let i = 0; i < beats.length; i++) {
    const kind: SceneKind = i === 0 ? 'intro' : i === beats.length - 1 ? 'verdict' : 'stats';
    const svg = renderSceneSvg(plan, beats[i], kind, photoA, photoB);
    const out = path.join(outDir, `scene-${String(i).padStart(2, '0')}.png`);
    await sharp(Buffer.from(svg)).png().toFile(out);
    paths.push(out);
  }
  return paths;
}
