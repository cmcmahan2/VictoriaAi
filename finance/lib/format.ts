import type { ISODate } from './types';

const money = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money0 = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', minimumFractionDigits: 0, maximumFractionDigits: 0 });

/** $1,234.56 (negative as −$1,234.56) */
export function fmt(n: number, opts?: { whole?: boolean; sign?: boolean }): string {
  if (!Number.isFinite(n)) return '—';
  const f = opts?.whole ? money0 : money;
  const s = f.format(Math.abs(n)).replace('CA', '').replace('US', '');
  if (n < -0.004) return `−${s}`;
  if (opts?.sign && n > 0.004) return `+${s}`;
  return s;
}

export const pct = (n: number, digits = 0) => (Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : '—');

export const round2 = (n: number) => Math.round(n * 100) / 100;

/* ---------- dates (all local time, ISO YYYY-MM-DD) ---------- */

export function toISO(d: Date): ISODate {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function parseISO(s: ISODate): Date {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

export const todayISO = () => toISO(new Date());

export function addDays(s: ISODate, n: number): ISODate {
  const d = parseISO(s);
  d.setDate(d.getDate() + n);
  return toISO(d);
}

export function addMonths(s: ISODate, n: number): ISODate {
  const d = parseISO(s);
  const day = d.getDate();
  d.setDate(1);
  d.setMonth(d.getMonth() + n);
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  d.setDate(Math.min(day, last));
  return toISO(d);
}

/** Monday of the week containing `s`. Weeks run Mon–Sun. */
export function weekStart(s: ISODate): ISODate {
  const d = parseISO(s);
  const dow = (d.getDay() + 6) % 7; // Mon=0
  d.setDate(d.getDate() - dow);
  return toISO(d);
}

export const monthKey = (s: ISODate) => s.slice(0, 7);

export function monthBounds(key: string): [ISODate, ISODate] {
  const [y, m] = key.split('-').map(Number);
  return [toISO(new Date(y, m - 1, 1)), toISO(new Date(y, m, 0))];
}

export function shiftMonthKey(key: string, n: number): string {
  return monthKey(addMonths(`${key}-01`, n));
}

export const daysBetween = (a: ISODate, b: ISODate) => Math.round((parseISO(b).getTime() - parseISO(a).getTime()) / 86400000);

/** Nov 24, 2026 */
export function fmtDate(s: ISODate | undefined | null): string {
  if (!s) return '—';
  return parseISO(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Nov 24 */
export function fmtShort(s: ISODate): string {
  return parseISO(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export function fmtWeekday(s: ISODate): string {
  return parseISO(s).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export function fmtMonth(key: string): string {
  return parseISO(`${key}-01`).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

export function fmtMonthShort(s: ISODate): string {
  return parseISO(s).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

export function relDay(s: ISODate): string {
  const t = todayISO();
  if (s === t) return 'Today';
  if (s === addDays(t, -1)) return 'Yesterday';
  return fmtWeekday(s);
}

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);

export function parseMoney(s: string): number {
  const n = parseFloat(String(s).replace(/[^0-9.\-]/g, ''));
  return Number.isFinite(n) ? n : 0;
}
