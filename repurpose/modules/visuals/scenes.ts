import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
import type { MatchupPlan, SceneKind } from '../matchup/script';

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

// Rough text width estimate for Arial-ish fonts (0.6 ≈ bold average).
const CHAR_W = 0.6;
function estWidth(text: string, fontSize: number): number {
  return (text || '').length * fontSize * CHAR_W;
}

// Largest font (<= base) that fits `text` within `maxWidth`, floored at `min`.
function fitFont(text: string, maxWidth: number, base: number, min = 20): number {
  if (estWidth(text, base) <= maxWidth) return base;
  const size = Math.floor(maxWidth / (Math.max(1, (text || '').length) * CHAR_W));
  return Math.max(min, Math.min(base, size));
}

function wrapLines(text: string, maxChars: number): string[] {
  const words = (text || '').split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let cur = '';
  for (const w of words) {
    if (cur && (cur + ' ' + w).length > maxChars) {
      lines.push(cur);
      cur = w;
    } else {
      cur = cur ? cur + ' ' + w : w;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

// Fit a caption into a box: largest font where the wrapped text fits.
function fitCaption(text: string, maxWidth: number, maxHeight: number) {
  for (const fontSize of [56, 52, 48, 44, 40, 36, 32, 28]) {
    const lineHeight = Math.round(fontSize * 1.2);
    const maxChars = Math.max(8, Math.floor(maxWidth / (fontSize * CHAR_W)));
    const lines = wrapLines(text, maxChars);
    if (lines.length * lineHeight <= maxHeight) return { fontSize, lineHeight, lines };
  }
  const fontSize = 28;
  const lineHeight = Math.round(fontSize * 1.2);
  const maxChars = Math.max(8, Math.floor(maxWidth / (fontSize * CHAR_W)));
  return { fontSize, lineHeight, lines: wrapLines(text, maxChars) };
}

// Embed a photo as a base64 data URI clipped into a circle, or a fallback
// circle with initials when no photo is available.
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

// One scene to render: derived from the plan (intro / comparison / verdict).
export type RenderScene = {
  kind: 'intro' | SceneKind | 'verdict';
  title?: string;
  aItems?: string[];
  bItems?: string[];
  caption: string;
};

// Expand a plan into the ordered scenes: intro → each comparison → verdict.
// Captions double as the narration beats (kept aligned for TTS).
export function planToRenderScenes(plan: MatchupPlan): RenderScene[] {
  const items: RenderScene[] = [{ kind: 'intro', caption: plan.hook }];
  for (const s of plan.scenes) {
    items.push({ kind: s.kind, title: s.title, aItems: s.aItems, bItems: s.bItems, caption: s.narration });
  }
  items.push({ kind: 'verdict', caption: plan.verdict });
  return items.filter((it) => it.caption && it.caption.trim());
}

// Two centered columns of short bullets, one per player.
function listMiddle(title: string, aItems: string[], bItems: string[], aCx: number, bCx: number): string {
  const titleY = 650;
  const startY = 760;
  const lineH = 100;
  const colW = 460;
  const col = (items: string[], cx: number) =>
    (items || [])
      .slice(0, 4)
      .map((it, i) => {
        const f = fitFont(it, colW, 40, 22);
        return `<text x="${cx}" y="${startY + i * lineH}" font-size="${f}" fill="#e6edf3" text-anchor="middle" font-family="Arial, sans-serif" font-weight="600">${esc(it)}</text>`;
      })
      .join('');
  return `
    <text x="${W / 2}" y="${titleY}" font-size="56" fill="#ffa657" text-anchor="middle" font-family="Arial, sans-serif" font-weight="800">${esc(title)}</text>
    ${col(aItems, aCx)}
    ${col(bItems, bCx)}`;
}

// The head-to-head stat table.
function statsMiddle(plan: MatchupPlan): string {
  const rows = plan.statRows.slice(0, 6);
  const startY = 700;
  const rowH = 112;
  const aValX = 400;
  const bValX = 680;
  const valMaxW = 360;
  const labelMaxW = 250;
  return rows
    .map((row, i) => {
      const y = startY + i * rowH;
      const aColor = row.edge === 'A' ? '#3fb950' : '#e6edf3';
      const bColor = row.edge === 'B' ? '#3fb950' : '#e6edf3';
      const aFont = fitFont(row.a, valMaxW, 48, 24);
      const bFont = fitFont(row.b, valMaxW, 48, 24);
      const lFont = fitFont(row.label, labelMaxW, 30, 18);
      return `
        <text x="${aValX}" y="${y}" font-size="${aFont}" fill="${aColor}" text-anchor="end" font-family="Arial, sans-serif" font-weight="700">${esc(row.a)}</text>
        <text x="${W / 2}" y="${y}" font-size="${lFont}" fill="#8b949e" text-anchor="middle" font-family="Arial, sans-serif">${esc(row.label)}</text>
        <text x="${bValX}" y="${y}" font-size="${bFont}" fill="${bColor}" text-anchor="start" font-family="Arial, sans-serif" font-weight="700">${esc(row.b)}</text>`;
    })
    .join('');
}

function renderSceneSvg(plan: MatchupPlan, item: RenderScene, photoA: string | null, photoB: string | null): string {
  const photoSize = 300;
  const aCx = W * 0.28;
  const bCx = W * 0.72;
  const photoCy = 360;
  const nameY = photoCy + photoSize / 2 + 70;
  const aNameFont = fitFont(plan.playerA.name, 380, 44, 26);
  const bNameFont = fitFont(plan.playerB.name, 380, 44, 26);

  let middle = '';
  if (item.kind === 'intro') {
    middle = `<text x="${W / 2}" y="${photoCy + 30}" font-size="130" fill="#ffa657" text-anchor="middle" font-family="Arial, sans-serif" font-weight="800">VS</text>`;
  } else if (item.kind === 'verdict') {
    middle = `
      <text x="${W / 2}" y="720" font-size="74" fill="#e6edf3" text-anchor="middle" font-family="Arial, sans-serif" font-weight="800">WHO'S BETTER?</text>
      <text x="${W / 2}" y="820" font-size="56" fill="#58a6ff" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">Comment 1 or 2 👇</text>`;
  } else if (item.kind === 'stats') {
    middle = statsMiddle(plan);
  } else {
    middle = listMiddle(item.title || '', item.aItems || [], item.bItems || [], aCx, bCx);
  }

  const capTop = 1380;
  const capBottom = 1860;
  const cap = fitCaption(item.caption, 980, capBottom - capTop);
  const blockHeight = cap.lines.length * cap.lineHeight;
  const firstBaseline = (capTop + capBottom) / 2 - blockHeight / 2 + cap.fontSize;
  const captionTspans = cap.lines
    .map((ln, i) => `<tspan x="${W / 2}" y="${firstBaseline + i * cap.lineHeight}">${esc(ln)}</tspan>`)
    .join('');

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

    <text x="${aCx}" y="${nameY}" font-size="${aNameFont}" fill="#e6edf3" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">${esc(plan.playerA.name)}</text>
    <text x="${bCx}" y="${nameY}" font-size="${bNameFont}" fill="#e6edf3" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700">${esc(plan.playerB.name)}</text>

    ${middle}

    <text fill="#ffffff" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" font-size="${cap.fontSize}">${captionTspans}</text>
  </svg>`;
}

// Render one PNG per scene, in order, aligned to the TTS beats.
export async function buildScenes(
  plan: MatchupPlan,
  items: RenderScene[],
  photoA: string | null,
  photoB: string | null,
  outDir: string,
): Promise<string[]> {
  fs.mkdirSync(outDir, { recursive: true });
  const paths: string[] = [];
  for (let i = 0; i < items.length; i++) {
    const svg = renderSceneSvg(plan, items[i], photoA, photoB);
    const out = path.join(outDir, `scene-${String(i).padStart(2, '0')}.png`);
    await sharp(Buffer.from(svg)).png().toFile(out);
    paths.push(out);
  }
  return paths;
}
