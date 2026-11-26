import type { AppState } from './types';
import {
  PHASE_INFO, catMonthly, currentPhase, debtBalance, efBalance, entriesIn, monthlyIncome, netWorth, phaseAllocations, project,
  requiredMonthly, spendCats, streak, totalsByCat, wsContributed, wsValue,
} from './calc';
import { fmt, fmtDate, fmtMonth, monthBounds, parseISO, pct } from './format';

export function monthlySummary(s: AppState, key: string): string {
  const [from, to] = monthBounds(key);
  const entries = entriesIn(s, from, to);
  const totals = totalsByCat(entries);
  const paid = s.paycheques.filter((p) => p.date >= from && p.date <= to);
  const actualIncome = paid.reduce((a, p) => a + p.amount, 0);
  const income = monthlyIncome(s);
  const phase = currentPhase(s);
  const proj = project(s);
  const L: string[] = [];
  const spent = entries.reduce((a, e) => a + e.amount, 0);

  L.push(`MONTHLY MONEY SUMMARY — ${fmtMonth(key)}`);
  L.push(`Context: 24, Vancouver BC, live at home (no rent/groceries). Currency CAD.`);
  L.push('');
  L.push(`INCOME`);
  L.push(`- Planned: ${fmt(income)} (${s.settings.paychequesPerMonth} × ${fmt(s.settings.paychequeAmount)})`);
  L.push(`- Logged paycheques: ${paid.length} totalling ${fmt(actualIncome)}${paid.length ? ' (' + paid.map((p) => `${fmtDate(p.date)} ${fmt(p.amount)}`).join(', ') + ')' : ''}`);
  L.push('');
  L.push(`SPENDING vs BUDGET (total ${fmt(spent)})`);
  for (const c of spendCats(s)) {
    const b = catMonthly(c);
    const t = totals[c.id] ?? 0;
    if (b === 0 && t === 0) continue;
    const flag = b > 0 && t > b ? ' ⚠ OVER' : b > 0 && t >= 0.8 * b ? ' (80%+)' : '';
    L.push(`- ${c.name}: ${fmt(t)} of ${fmt(b)}${b ? ` (${pct(t / b)})` : ''}${flag}`);
  }
  const top = [...entries].sort((a, b) => b.amount - a.amount).slice(0, 5);
  if (top.length) {
    L.push('');
    L.push('BIGGEST PURCHASES');
    for (const e of top) L.push(`- ${fmtDate(e.date)}: ${fmt(e.amount)} — ${s.categories.find((c) => c.id === e.categoryId)?.name ?? e.categoryId}${e.note || e.description ? ` (${e.note || e.description})` : ''}`);
  }
  L.push('');
  L.push(`PLAN: Phase ${phase} — ${PHASE_INFO[phase].title}`);
  for (const a of phaseAllocations(s, phase)) L.push(`- ${a.label}: ${fmt(a.monthly)}/month (${pct(a.monthly / income)} of income)`);
  L.push('');
  L.push('DEBTS');
  for (const d of s.debts) {
    const bal = debtBalance(s, d);
    const pm = s.debtPayments.filter((p) => p.debtId === d.id && p.date >= from && p.date <= to).reduce((a, p) => a + p.amount, 0);
    let line = `- ${d.name} (${d.apr}% APR): ${fmt(bal)} left, paid ${fmt(pm)} this month, projected payoff ${fmtDate(proj.payoff[d.id])}`;
    if (d.deadline && bal > 0) line += `; deadline ${fmtDate(d.deadline)} needs ${fmt(requiredMonthly(bal, d.apr, d.deadline))}/month`;
    L.push(line);
  }
  L.push(`- Debt-free date (projected): ${fmtDate(proj.debtFree)}`);
  L.push('');
  L.push('SAVINGS & INVESTING');
  const efM = s.efTxns.filter((t) => t.date >= from && t.date <= to).reduce((a, t) => a + t.amount, 0);
  L.push(`- Emergency fund: ${fmt(efBalance(s))} of ${fmt(s.settings.emergencyTarget)} target (${fmt(efM, { sign: true })} this month); projected full ${fmtDate(proj.efFull)}`);
  const y = parseISO(from).getFullYear();
  for (const a of ['FHSA', 'TFSA'] as const) {
    const m = s.wsContributions.filter((c) => c.account === a && c.date >= from && c.date <= to).reduce((x, c) => x + c.amount, 0);
    L.push(`- Wealthsimple ${a}: value ${fmt(wsValue(s, a))}, contributed ${fmt(wsContributed(s, a))} total / ${fmt(wsContributed(s, a, y))} in ${y} / ${fmt(m)} this month`);
  }
  L.push(`- FHSA opened: ${s.settings.fhsaOpened ? 'yes' : 'NO — deadline Dec 31, 2026'}`);
  L.push(`- Net worth: ${fmt(netWorth(s))}`);
  const trips = s.trips.filter((t) => t.date >= from && t.date <= to);
  const fills = s.fillups.filter((f) => f.date >= from && f.date <= to);
  if (trips.length || fills.length) {
    L.push('');
    L.push('WORK VEHICLE');
    L.push(`- ${trips.length} trips, ${trips.reduce((a, t) => a + t.km, 0).toFixed(0)} km business; ${fills.length} fill-ups ${fmt(fills.reduce((a, f) => a + f.amount, 0))}`);
  }
  L.push('');
  L.push(`Logging streak: ${streak(s).count} days.`);
  L.push('');
  L.push('Question for you: based on this, what should I adjust next month?');
  return L.join('\n');
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}
