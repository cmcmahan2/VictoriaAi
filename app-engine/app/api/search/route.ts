import { NextResponse } from 'next/server';
import { checkAvailability } from '@/modules/domains/availability';

export const maxDuration = 30;

// TLD list: [name, approximate annual price USD, tier]
const TLDS: [string, number, 'budget' | 'standard' | 'premium'][] = [
  ['com',    12, 'standard'],
  ['net',    14, 'standard'],
  ['org',    12, 'standard'],
  ['co',     30, 'standard'],
  ['io',     39, 'premium'],
  ['app',    18, 'standard'],
  ['dev',    15, 'standard'],
  ['ai',     70, 'premium'],
  ['xyz',     3, 'budget'],
  ['site',    3, 'budget'],
  ['online',  3, 'budget'],
  ['store',   5, 'budget'],
];

const PREFIXES = ['get', 'my', 'the', 'use', 'try'];
const SUFFIXES = ['app', 'hq', 'hub', 'ai', 'labs', 'co', 'base', 'kit', 'ly'];

function sanitize(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 20);
}

function generateVariations(keyword: string): string[] {
  const kw = sanitize(keyword);
  if (!kw || kw.length < 2) return [];

  const labels = new Set<string>([kw]);
  for (const p of PREFIXES) {
    const v = sanitize(p + kw);
    if (v.length <= 20) labels.add(v);
  }
  for (const s of SUFFIXES) {
    const v = sanitize(kw + s);
    if (v.length <= 20) labels.add(v);
  }
  return [...labels];
}

export type SearchResult = {
  domain: string;
  sld: string;
  tld: string;
  available: boolean;
  price: number;
  tier: 'budget' | 'standard' | 'premium';
  registerUrl: string;
};

export async function POST(req: Request) {
  let body: { keyword?: string } = {};
  try { body = await req.json(); } catch { /* ignore */ }

  const raw = (body.keyword ?? '').trim();
  if (!raw) {
    return NextResponse.json({ ok: false, error: 'keyword is required' }, { status: 400 });
  }

  const labels = generateVariations(raw);
  if (labels.length === 0) {
    return NextResponse.json({ ok: false, error: 'Could not parse keyword into valid domain labels.' }, { status: 400 });
  }

  // Build candidate list: exact keyword gets all TLDs; variations get budget+standard only
  const exactLabel = sanitize(raw);
  const candidates: string[] = [];
  for (const [tld] of TLDS) {
    candidates.push(`${exactLabel}.${tld}`);
  }
  for (const label of labels) {
    if (label === exactLabel) continue;
    for (const [tld, , tier] of TLDS) {
      if (tier !== 'premium') candidates.push(`${label}.${tld}`);
    }
  }

  const availMap = await checkAvailability([...new Set(candidates)]);

  const tldMeta = new Map(TLDS.map(([t, p, tier]) => [t, { price: p, tier }]));

  const results: SearchResult[] = [...new Set(candidates)]
    .map((domain): SearchResult | null => {
      const parts = domain.split('.');
      const tld = parts.at(-1) ?? '';
      const sld = parts.slice(0, -1).join('.');
      const meta = tldMeta.get(tld);
      if (!meta) return null;
      const avail = availMap.get(domain);
      return {
        domain,
        sld,
        tld,
        available: avail === 'available',
        price: meta.price,
        tier: meta.tier,
        registerUrl: `https://www.namecheap.com/domains/registration/results/?domain=${encodeURIComponent(domain)}`,
      };
    })
    .filter((r): r is SearchResult => r !== null)
    .sort((a, b) => {
      // Available first, then price ascending, then alpha
      if (a.available !== b.available) return a.available ? -1 : 1;
      if (a.price !== b.price) return a.price - b.price;
      return a.domain.localeCompare(b.domain);
    });

  return NextResponse.json({ ok: true, results, keyword: raw });
}
