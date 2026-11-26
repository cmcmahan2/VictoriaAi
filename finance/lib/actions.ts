import type { AppState, Entry, ISODate, SplitItem } from './types';
import { buildSplit } from './calc';
import { todayISO, uid } from './format';

/** All mutations take a draft (already cloned by the store). */

export function addPaycheque(d: AppState, date: ISODate, amount: number, note: string) {
  const { phase, items } = buildSplit(d);
  const id = uid();
  d.paycheques.push({ id, date, amount, note, phase, split: items, createdAt: Date.now() });
  return id;
}

export function deletePaycheque(d: AppState, id: string) {
  const p = d.paycheques.find((x) => x.id === id);
  if (!p) return;
  for (const it of p.split) if (it.done) unlinkSplit(d, it);
  d.paycheques = d.paycheques.filter((x) => x.id !== id);
}

function unlinkSplit(d: AppState, it: SplitItem) {
  if (!it.recordId) return;
  d.debtPayments = d.debtPayments.filter((x) => x.id !== it.recordId);
  d.efTxns = d.efTxns.filter((x) => x.id !== it.recordId);
  d.wsContributions = d.wsContributions.filter((x) => x.id !== it.recordId);
  it.recordId = undefined;
}

/** Checking a split item logs the matching payment / deposit / contribution. Unchecking removes it. */
export function toggleSplit(d: AppState, pcId: string, key: string, done: boolean) {
  const p = d.paycheques.find((x) => x.id === pcId);
  const it = p?.split.find((x) => x.key === key);
  if (!p || !it) return;
  it.done = done;
  if (!done) return unlinkSplit(d, it);
  const rid = uid();
  const base = { id: rid, date: p.date > todayISO() ? todayISO() : p.date, amount: it.amount, note: 'Paycheque split', paychequeId: p.id, createdAt: Date.now() };
  if (it.kind === 'debt' && it.debtId) d.debtPayments.push({ ...base, debtId: it.debtId });
  else if (it.kind === 'ef') d.efTxns.push(base);
  else if (it.kind === 'ws') d.wsContributions.push({ ...base, account: it.wsAccount ?? 'TFSA' });
  else return; // bills: just a reminder
  it.recordId = rid;
}

export function addEntries(d: AppState, items: Omit<Entry, 'id' | 'createdAt' | 'source'>[]) {
  for (const it of items) d.entries.push({ ...it, id: uid(), source: 'manual', createdAt: Date.now() });
}

export function deleteEntry(d: AppState, id: string) {
  const e = d.entries.find((x) => x.id === id);
  if (!e) return;
  if (e.matchedManualId) {
    const m = d.entries.find((x) => x.id === e.matchedManualId);
    if (m) m.matchedImportId = undefined;
  }
  if (e.matchedImportId) {
    const m = d.entries.find((x) => x.id === e.matchedImportId);
    if (m) m.matchedManualId = undefined;
  }
  if (e.fillupId) {
    const f = d.fillups.find((x) => x.id === e.fillupId);
    if (f) f.entryId = undefined;
  }
  d.entries = d.entries.filter((x) => x.id !== id);
}

export function markCheckin(d: AppState, date: ISODate) {
  if (!d.checkins.includes(date)) d.checkins.push(date);
}
