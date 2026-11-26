import type { AppState, Category, Debt, Entry, ISODate, SplitItem, WsAccount } from './types';
import { addDays, addMonths, monthBounds, monthKey, parseISO, round2, todayISO, toISO, weekStart } from './format';

/* ---------------- budgets ---------------- */

export const catMonthly = (c: Category) => (c.period === 'week' ? (c.amount * 52) / 12 : c.amount);
export const catWeekly = (c: Category) => (c.period === 'week' ? c.amount : (c.amount * 12) / 52);

export const spendCats = (s: AppState) => s.categories.filter((c) => !c.ignore);
export const catById = (s: AppState, id: string) => s.categories.find((c) => c.id === id);

export const monthlyIncome = (s: AppState) => s.settings.paychequeAmount * s.settings.paychequesPerMonth;
export const spendBudgetMonthly = (s: AppState) => spendCats(s).reduce((a, c) => a + catMonthly(c), 0);

/** A manual entry confirmed by a statement line is represented by that line, so it isn't double counted. */
export const countsTowardBudget = (s: AppState, e: Entry) => {
  if (e.source === 'manual' && e.matchedImportId) return false;
  const c = catById(s, e.categoryId);
  return !c?.ignore;
};

export function entriesIn(s: AppState, from: ISODate, to: ISODate): Entry[] {
  return s.entries.filter((e) => e.date >= from && e.date <= to && countsTowardBudget(s, e));
}

export function totalsByCat(entries: Entry[]): Record<string, number> {
  const t: Record<string, number> = {};
  for (const e of entries) t[e.categoryId] = (t[e.categoryId] ?? 0) + e.amount;
  return t;
}

export const weekRange = (d: ISODate): [ISODate, ISODate] => {
  const ws = weekStart(d);
  return [ws, addDays(ws, 6)];
};

export const barTone = (spent: number, budget: number): 'ok' | 'warn' | 'over' => {
  if (budget <= 0) return spent > 0 ? 'over' : 'ok';
  if (spent > budget + 0.001) return 'over';
  if (spent >= budget * 0.8) return 'warn';
  return 'ok';
};

/* ---------------- balances ---------------- */

export function debtBalance(s: AppState, d: Debt): number {
  const paid = s.debtPayments
    .filter((p) => p.debtId === d.id && p.createdAt > d.balanceSetAt)
    .reduce((a, p) => a + p.amount, 0);
  return Math.max(0, round2(d.balance - paid));
}

export const debtPaidTotal = (s: AppState, d: Debt) =>
  s.debtPayments.filter((p) => p.debtId === d.id).reduce((a, p) => a + p.amount, 0);

export const totalDebt = (s: AppState) => s.debts.reduce((a, d) => a + debtBalance(s, d), 0);

export const efBalance = (s: AppState) => round2(s.settings.efStartBalance + s.efTxns.reduce((a, t) => a + t.amount, 0));

export const wsContributed = (s: AppState, acct?: WsAccount, year?: number) =>
  s.wsContributions
    .filter((c) => (!acct || c.account === acct) && (!year || parseISO(c.date).getFullYear() === year))
    .reduce((a, c) => a + c.amount, 0);

/** Manual current value when entered, otherwise contributions. */
export const wsValue = (s: AppState, acct: WsAccount) => s.settings.wsValue[acct] ?? wsContributed(s, acct);
export const wsTotal = (s: AppState) => wsValue(s, 'FHSA') + wsValue(s, 'TFSA');

export const netWorth = (s: AppState) => efBalance(s) + wsTotal(s) + s.settings.otherCash - totalDebt(s);

/* ---------------- plan phases ---------------- */

export type Phase = 1 | 2 | 3;

export function autoPhase(s: AppState): Phase {
  const cards = s.debts.filter((d) => d.kind === 'card');
  if (cards.some((d) => debtBalance(s, d) > 0.009)) return 1;
  if (efBalance(s) < s.settings.emergencyTarget) return 2;
  return 3;
}
export const currentPhase = (s: AppState): Phase => (s.settings.phaseOverride || autoPhase(s)) as Phase;

export const PHASE_INFO: Record<Phase, { title: string; blurb: string }> = {
  1: { title: 'Kill the credit cards', blurb: 'Everything left after spending goes to Amex, then Tangerine, plus the student loan minimum.' },
  2: { title: 'Build the emergency fund', blurb: 'Student loan, emergency fund and Wealthsimple each month until the fund hits its target.' },
  3: { title: 'Invest', blurb: 'Emergency fund is full — that money now goes to Wealthsimple.' },
};

export interface Allocation { key: string; label: string; monthly: number; kind: SplitItem['kind']; debtId?: string; color: string }

/** Monthly plan amounts for a given phase (excludes day-to-day spending). */
export function phaseAllocations(s: AppState, phase: Phase): Allocation[] {
  const st = s.settings;
  const student = s.debts.find((d) => d.kind === 'loan');
  const studentLeft = student ? debtBalance(s, student) : 0;
  const fixed = spendCats(s).filter((c) => c.fixed);
  const out: Allocation[] = fixed.map((c) => ({ key: `bill:${c.id}`, label: c.name, monthly: catMonthly(c), kind: 'bill', color: c.color }));
  const loanAmt = phase === 1 ? st.studentLoanMinimum : st.studentLoanPayment;
  let toWs = 0;
  if (student && studentLeft > 0) out.push({ key: `debt:${student.id}`, label: student.name, monthly: loanAmt, kind: 'debt', debtId: student.id, color: student.color });
  else toWs += loanAmt;
  if (phase === 1) {
    const extra = Math.max(0, monthlyIncome(s) - spendBudgetMonthly(s) - st.studentLoanMinimum);
    out.push({ key: 'cards', label: 'Credit card payoff', monthly: extra, kind: 'debt', color: '#60a5fa' });
  } else if (phase === 2) {
    out.push({ key: 'ef', label: 'Emergency fund', monthly: st.emergencyMonthly, kind: 'ef', color: '#34d399' });
    out.push({ key: 'ws', label: 'Wealthsimple', monthly: st.wealthsimpleMonthly + toWs, kind: 'ws', color: '#818cf8' });
  } else {
    out.push({ key: 'ws', label: 'Wealthsimple', monthly: st.wealthsimpleMonthly + st.emergencyMonthly + toWs, kind: 'ws', color: '#818cf8' });
  }
  return out;
}

export function defaultWsAccount(s: AppState, amount = 0): WsAccount {
  if (!s.settings.fhsaOpened) return 'TFSA';
  const year = new Date().getFullYear();
  return wsContributed(s, 'FHSA', year) + amount <= s.settings.fhsaAnnualLimit + 0.001 ? 'FHSA' : 'TFSA';
}

/** Build the per-paycheque checklist: half of every monthly plan amount. */
export function buildSplit(s: AppState): { phase: Phase; items: SplitItem[] } {
  const phase = currentPhase(s);
  const per = s.settings.paychequesPerMonth || 2;
  const items: SplitItem[] = [];
  for (const a of phaseAllocations(s, phase)) {
    const amt = round2(a.monthly / per);
    if (amt <= 0) continue;
    if (a.key === 'cards') {
      // highest interest first, overflow to the next card, then to the emergency fund
      let pool = amt;
      const cards = s.debts.filter((d) => d.kind === 'card').sort((x, y) => y.apr - x.apr);
      for (const d of cards) {
        const bal = debtBalance(s, d);
        const pay = round2(Math.min(pool, bal));
        if (pay > 0) items.push({ key: `debt:${d.id}`, label: `${d.name} payment`, amount: pay, done: false, kind: 'debt', debtId: d.id });
        pool = round2(pool - pay);
      }
      if (pool > 0) items.push({ key: 'ef', label: 'Emergency fund (cards cleared!)', amount: pool, done: false, kind: 'ef' });
    } else if (a.kind === 'ef') {
      const room = Math.max(0, s.settings.emergencyTarget - efBalance(s));
      const toEf = round2(Math.min(amt, room));
      if (toEf > 0) items.push({ key: 'ef', label: 'Emergency fund deposit', amount: toEf, done: false, kind: 'ef' });
      if (amt - toEf > 0) items.push({ key: 'ws-ef', label: 'Wealthsimple (fund is full)', amount: round2(amt - toEf), done: false, kind: 'ws', wsAccount: defaultWsAccount(s, amt - toEf) });
    } else if (a.kind === 'ws') {
      items.push({ key: 'ws', label: 'Wealthsimple contribution', amount: amt, done: false, kind: 'ws', wsAccount: defaultWsAccount(s, amt) });
    } else if (a.kind === 'debt') {
      const d = s.debts.find((x) => x.id === a.debtId);
      const pay = d ? round2(Math.min(amt, debtBalance(s, d))) : amt;
      if (pay > 0) items.push({ key: a.key, label: `${a.label} payment`, amount: pay, done: false, kind: 'debt', debtId: a.debtId });
    } else {
      items.push({ key: a.key, label: `${a.label} (set aside)`, amount: amt, done: false, kind: 'bill' });
    }
  }
  return { phase, items };
}

/* ---------------- paydays & projection ---------------- */

/** Paydays are the 15th and the last day of each month. */
export function nextPayday(from: ISODate): ISODate {
  const d = parseISO(from);
  if (d.getDate() <= 15) return toISO(new Date(d.getFullYear(), d.getMonth(), 15));
  return toISO(new Date(d.getFullYear(), d.getMonth() + 1, 0));
}

export interface Projection {
  points: { date: ISODate; balances: Record<string, number>; ef: number; ws: number }[];
  payoff: Record<string, ISODate | null>;
  debtFree: ISODate | null;
  efFull: ISODate | null;
  phase3: ISODate | null;
}

/** Simulate paycheque by paycheque (15th + last day) following the phase rules. */
export function project(s: AppState, maxMonths = 72): Projection {
  const st = s.settings;
  const per = st.paychequesPerMonth || 2;
  const bal: Record<string, number> = {};
  for (const d of s.debts) bal[d.id] = debtBalance(s, d);
  let ef = efBalance(s);
  let ws = wsTotal(s);
  const payoff: Record<string, ISODate | null> = {};
  for (const d of s.debts) payoff[d.id] = bal[d.id] <= 0 ? todayISO() : null;
  let efFull: ISODate | null = ef >= st.emergencyTarget ? todayISO() : null;
  let phase3: ISODate | null = null;

  const lastPc = s.paycheques.reduce<ISODate>((m, p) => (p.date > m ? p.date : m), '0000-00-00');
  const start = lastPc >= todayISO() ? addDays(lastPc, 1) : todayISO();
  let day = nextPayday(start);
  const points: Projection['points'] = [{ date: todayISO(), balances: { ...bal }, ef, ws }];
  const spendBudget = spendBudgetMonthly(s);
  const income = monthlyIncome(s);
  const cards = s.debts.filter((d) => d.kind === 'card').sort((a, b) => b.apr - a.apr);
  const loans = s.debts.filter((d) => d.kind === 'loan');
  const end = addMonths(todayISO(), maxMonths);

  while (day <= end) {
    const isMonthEnd = parseISO(addDays(day, 1)).getDate() === 1;
    if (isMonthEnd) for (const d of s.debts) bal[d.id] = round2(bal[d.id] * (1 + d.apr / 100 / 12));
    const cardsLeft = cards.some((d) => bal[d.id] > 0.009);
    const phase: Phase = cardsLeft ? 1 : ef < st.emergencyTarget ? 2 : 3;
    if (phase === 3 && !phase3) phase3 = day;
    let spare = 0;
    const loanAmt = (phase === 1 ? st.studentLoanMinimum : st.studentLoanPayment) / per;
    let loanPool = loanAmt;
    for (const d of loans) {
      const pay = Math.min(loanPool, bal[d.id]);
      bal[d.id] = round2(bal[d.id] - pay);
      loanPool -= pay;
    }
    spare += loanPool;
    if (phase === 1) {
      let pool = Math.max(0, income - spendBudget - st.studentLoanMinimum) / per;
      for (const d of cards) {
        const pay = Math.min(pool, bal[d.id]);
        bal[d.id] = round2(bal[d.id] - pay);
        pool -= pay;
      }
      ef += pool;
      ws += spare;
    } else if (phase === 2) {
      const toEf = Math.min(st.emergencyMonthly / per, st.emergencyTarget - ef);
      ef += toEf;
      ws += st.wealthsimpleMonthly / per + (st.emergencyMonthly / per - toEf) + spare;
    } else {
      ws += (st.wealthsimpleMonthly + st.emergencyMonthly) / per + spare;
    }
    if (!efFull && ef >= st.emergencyTarget - 0.01) efFull = day;
    for (const d of s.debts) if (!payoff[d.id] && bal[d.id] <= 0.009) payoff[d.id] = day;
    if (isMonthEnd) points.push({ date: day, balances: { ...bal }, ef, ws });
    if (Object.values(payoff).every(Boolean) && efFull && points.length > 3 && phase3) break;
    day = nextPayday(addDays(day, 1));
  }
  const allPaid = Object.values(payoff).every(Boolean);
  const debtFree = allPaid ? Object.values(payoff).reduce<ISODate>((m, d) => (d! > m ? d! : m), '0000-00-00') : null;
  return { points, payoff, debtFree, efFull, phase3 };
}

/** Monthly payment needed to clear a balance by a deadline. */
export function requiredMonthly(balance: number, apr: number, deadline: ISODate): number {
  const t = todayISO();
  const months = Math.max(1, Math.round((parseISO(deadline).getTime() - parseISO(t).getTime()) / (86400000 * 30.4375)));
  const r = apr / 100 / 12;
  if (r === 0) return balance / months;
  return (balance * r) / (1 - Math.pow(1 + r, -months));
}

/* ---------------- streak ---------------- */

export function loggedDays(s: AppState): Set<ISODate> {
  const set = new Set<ISODate>(s.checkins);
  for (const e of s.entries) if (e.source === 'manual') set.add(e.date);
  return set;
}

export function streak(s: AppState): { count: number; today: boolean } {
  const set = loggedDays(s);
  const t = todayISO();
  const today = set.has(t);
  let d = today ? t : addDays(t, -1);
  let count = 0;
  while (set.has(d)) {
    count++;
    d = addDays(d, -1);
  }
  return { count, today };
}

/* ---------------- note → category guess ---------------- */

export function guessCategory(s: AppState, text: string): string | null {
  const t = ` ${text.toLowerCase()} `;
  let best: { id: string; idx: number } | null = null;
  for (const c of s.categories) {
    for (const k of c.keywords) {
      const kw = k.toLowerCase().trim();
      if (!kw) continue;
      const idx = t.indexOf(kw);
      if (idx >= 0 && (!best || idx < best.idx)) best = { id: c.id, idx };
    }
  }
  if (best) return best.id;
  for (const r of s.rules) if (t.includes(r.match.toLowerCase())) return r.categoryId;
  return null;
}

/** "35 bowling + drinks" → { amount: 35, note: "bowling + drinks" } */
export function parseQuick(text: string): { amount: number | null; note: string } {
  const m = text.match(/\$?\s*(\d+(?:[.,]\d{1,2})?)/);
  if (!m) return { amount: null, note: text.trim() };
  const amount = parseFloat(m[1].replace(',', '.'));
  const note = (text.slice(0, m.index) + text.slice((m.index ?? 0) + m[0].length)).replace(/\s+/g, ' ').replace(/^\s*(on|for|-|—|:)\s*/i, '').trim();
  return { amount, note };
}

export function monthRangeOf(d: ISODate): [ISODate, ISODate] {
  return monthBounds(monthKey(d));
}
