import type { AppState, BankAccount, Entry, ISODate, Rule } from './types';
import { daysBetween, toISO } from './format';

/** RFC-4180-ish CSV parser (quotes, escaped quotes, CRLF). */
export function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let q = false;
  const t = text.replace(/^﻿/, '');
  for (let i = 0; i < t.length; i++) {
    const ch = t[i];
    if (q) {
      if (ch === '"') {
        if (t[i + 1] === '"') { cell += '"'; i++; } else q = false;
      } else cell += ch;
    } else if (ch === '"') q = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && t[i + 1] === '\n') i++;
      row.push(cell); cell = '';
      if (row.some((c) => c.trim() !== '')) rows.push(row);
      row = [];
    } else cell += ch;
  }
  row.push(cell);
  if (row.some((c) => c.trim() !== '')) rows.push(row);
  return rows.map((r) => r.map((c) => c.trim()));
}

export function toCSV(rows: (string | number | undefined | null)[][]): string {
  return rows
    .map((r) => r.map((v) => {
      const s = v == null ? '' : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(','))
    .join('\n');
}

const MONTHS: Record<string, number> = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, nov: 11, dec: 12 };

/** Accepts 2026-11-24, 11/24/2026, 24/11/2026 (dmy), 20261124, "24 Nov. 2026", "Nov 24, 2026". */
export function parseDate(raw: string, order: 'mdy' | 'dmy' = 'mdy'): ISODate | null {
  const s = raw.trim().replace(/\./g, '');
  let m = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (m) return mk(+m[1], +m[2], +m[3]);
  m = s.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (m) return mk(+m[1], +m[2], +m[3]);
  m = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})/);
  if (m) {
    let a = +m[1], b = +m[2];
    const y = +m[3] < 100 ? 2000 + +m[3] : +m[3];
    if (order === 'dmy') [a, b] = [b, a];
    if (a > 12 && b <= 12) [a, b] = [b, a];
    return mk(y, a, b);
  }
  m = s.match(/^(\d{1,2})[\s-]([A-Za-z]{3,})[\s-,]*(\d{4})/);
  if (m && MONTHS[m[2].slice(0, 3).toLowerCase()]) return mk(+m[3], MONTHS[m[2].slice(0, 3).toLowerCase()], +m[1]);
  m = s.match(/^([A-Za-z]{3,})\s+(\d{1,2}),?\s+(\d{4})/);
  if (m && MONTHS[m[1].slice(0, 3).toLowerCase()]) return mk(+m[3], MONTHS[m[1].slice(0, 3).toLowerCase()], +m[2]);
  return null;
}

function mk(y: number, m: number, d: number): ISODate | null {
  if (!y || m < 1 || m > 12 || d < 1 || d > 31) return null;
  return toISO(new Date(y, m - 1, d));
}

const num = (s: string | undefined) => {
  if (s == null) return NaN;
  let t = s.replace(/[$\s,]/g, '');
  let neg = false;
  if (/^\(.*\)$/.test(t)) { neg = true; t = t.slice(1, -1); }
  if (t.endsWith('-')) { neg = true; t = t.slice(0, -1); }
  if (t === '') return NaN;
  const n = parseFloat(t);
  return neg ? -n : n;
};

export interface Mapping {
  hasHeader: boolean;
  date: number;
  desc: number[];
  amount: number; // -1 when using debit/credit columns
  debit: number;
  credit: number;
  /** Which sign means money spent */
  spendSign: 'negative' | 'positive';
  dateOrder: 'mdy' | 'dmy';
}

export const ACCOUNT_HINT: Record<BankAccount, { spendSign: Mapping['spendSign']; help: string }> = {
  RBC: { spendSign: 'negative', help: 'RBC Online Banking → Download Transactions → Comma Separated Values (.csv).' },
  Tangerine: { spendSign: 'negative', help: 'Tangerine → Account → Download Transactions → CSV.' },
  Amex: { spendSign: 'positive', help: 'americanexpress.ca → Statements & Activity → Download → CSV.' },
};

/** Guess the column layout from headers (or from the data when there's no header row). */
export function detectMapping(rows: string[][], account: BankAccount): Mapping {
  const first = rows[0] ?? [];
  const hasHeader = first.some((c) => /date|description|amount|transaction|merchant|name|memo|cad|debit|credit/i.test(c)) && !first.some((c) => parseDate(c));
  const m: Mapping = { hasHeader, date: -1, desc: [], amount: -1, debit: -1, credit: -1, spendSign: ACCOUNT_HINT[account].spendSign, dateOrder: 'mdy' };
  if (hasHeader) {
    const h = first.map((c) => c.toLowerCase());
    const find = (re: RegExp) => h.findIndex((c) => re.test(c));
    m.date = find(/^transaction date$|^date$/);
    if (m.date < 0) m.date = find(/date/);
    m.amount = find(/^amount$|cad\$|^cad$|amount \(cad\)|^montant/);
    if (m.amount < 0) m.amount = find(/amount/);
    m.debit = find(/debit|withdraw/);
    m.credit = find(/credit|deposit/);
    if (m.amount >= 0) { m.debit = -1; m.credit = -1; }
    const d1 = find(/description 1|^description$|merchant|^name$|^transaction$/);
    const d2 = find(/description 2|^memo$/);
    m.desc = [d1, d2].filter((i) => i >= 0);
    if (!m.desc.length) { const any = find(/desc|detail|payee/); if (any >= 0) m.desc = [any]; }
  } else {
    const sample = rows.slice(0, 10);
    const cols = Math.max(...sample.map((r) => r.length));
    let bestText = -1, bestLen = -1;
    for (let c = 0; c < cols; c++) {
      const vals = sample.map((r) => r[c] ?? '');
      if (m.date < 0 && vals.every((v) => parseDate(v))) { m.date = c; continue; }
      if (m.amount < 0 && vals.every((v) => Number.isFinite(num(v)) && /\d/.test(v)) && vals.some((v) => /[.]\d{2}$/.test(v))) { m.amount = c; continue; }
      const len = vals.reduce((a, v) => a + (/[a-z]/i.test(v) ? v.length : 0), 0);
      if (len > bestLen) { bestLen = len; bestText = c; }
    }
    if (bestText >= 0) m.desc = [bestText];
  }
  const dataRows = rows.slice(hasHeader ? 1 : 0);
  if (m.date >= 0 && dataRows.some((r) => { const p = (r[m.date] ?? '').match(/^(\d{1,2})[-/](\d{1,2})/); return p && +p[1] > 12; })) m.dateOrder = 'dmy';
  return m;
}

export interface ImportRow {
  key: string;
  date: ISODate;
  description: string;
  /** Signed as in the file */
  raw: number;
  /** Positive = money spent */
  amount: number;
  isSpend: boolean;
  categoryId: string;
  action: 'import' | 'match' | 'skip';
  dupOfManual?: Entry;
  alreadyImported?: boolean;
}

export function categorize(rules: Rule[], desc: string): string | null {
  const d = ` ${desc.toLowerCase()} `;
  // longest rule wins so "costco gas" beats "costco"
  const hit = [...rules].sort((a, b) => b.match.length - a.match.length).find((r) => r.match && d.includes(r.match.toLowerCase()));
  return hit?.categoryId ?? null;
}

export function buildRows(s: AppState, rows: string[][], map: Mapping, account: BankAccount): ImportRow[] {
  const out: ImportRow[] = [];
  const data = rows.slice(map.hasHeader ? 1 : 0);
  const usedManual = new Set<string>();
  data.forEach((r, i) => {
    const date = map.date >= 0 ? parseDate(r[map.date] ?? '', map.dateOrder) : null;
    if (!date) return;
    let raw: number;
    if (map.amount >= 0) raw = num(r[map.amount]);
    else {
      const d = num(r[map.debit]);
      const c = num(r[map.credit]);
      raw = (Number.isFinite(c) ? Math.abs(c) : 0) - (Number.isFinite(d) ? Math.abs(d) : 0);
    }
    if (!Number.isFinite(raw) || raw === 0) return;
    const description = map.desc.map((c) => r[c] ?? '').filter(Boolean).join(' · ') || '(no description)';
    const isSpend = map.amount < 0 || map.spendSign === 'negative' ? raw < 0 : raw > 0;
    const amount = Math.abs(raw);
    let categoryId = isSpend ? categorize(s.rules, description) ?? 'other' : 'ignore';
    const alreadyImported = s.entries.some(
      (e) => e.source === 'import' && e.account === account && e.date === date && Math.abs(e.amount - amount) < 0.005 && (e.description ?? '') === description,
    );
    let dupOfManual: Entry | undefined;
    if (isSpend && !alreadyImported) {
      dupOfManual = s.entries
        .filter((e) => e.source === 'manual' && !e.matchedImportId && !usedManual.has(e.id) && Math.abs(e.amount - amount) < 0.005 && Math.abs(daysBetween(e.date, date)) <= 3)
        .sort((a, b) => Math.abs(daysBetween(a.date, date)) - Math.abs(daysBetween(b.date, date)))[0];
      if (dupOfManual) { usedManual.add(dupOfManual.id); categoryId = dupOfManual.categoryId; }
    }
    const action: ImportRow['action'] = alreadyImported || categoryId === 'ignore' ? 'skip' : dupOfManual ? 'match' : 'import';
    out.push({ key: `${i}`, date, description, raw, amount, isSpend, categoryId, action, dupOfManual, alreadyImported });
  });
  return out.sort((a, b) => (a.date < b.date ? 1 : -1));
}

export function downloadText(filename: string, text: string, type = 'text/csv') {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
