'use client';
import { useMemo, useState } from 'react';
import { useStore } from '@/lib/store';
import {
  PHASE_INFO, catMonthly, catWeekly, currentPhase, debtBalance, efBalance, entriesIn, monthlyIncome, netWorth, nextPayday,
  phaseAllocations, project, spendCats, streak, totalDebt, totalsByCat, weekRange, wsTotal,
} from '@/lib/calc';
import { fmt, fmtDate, fmtMonth, monthBounds, monthKey, pct, todayISO } from '@/lib/format';
import { monthlySummary, copyText } from '@/lib/summary';
import { BudgetRow, Card, Empty, Stat } from '../ui';
import { Donut, DualDonut, Legend, type Slice } from '../charts';
import { PaychequeSheet, SplitCard } from '../Paycheque';
import type { Tab } from '../Shell';

export default function Dashboard({ go }: { go: (t: Tab) => void }) {
  const { state, toast } = useStore();
  const [pcOpen, setPcOpen] = useState(false);
  const t = todayISO();
  const mk = monthKey(t);
  const [mFrom, mTo] = monthBounds(mk);
  const [wFrom, wTo] = weekRange(t);
  const phase = currentPhase(state);
  const proj = useMemo(() => project(state), [state]);
  const st = streak(state);
  const income = monthlyIncome(state);

  const monthTotals = totalsByCat(entriesIn(state, mFrom, mTo));
  const weekTotals = totalsByCat(entriesIn(state, wFrom, wTo));
  const cats = spendCats(state);
  const spendSlices: Slice[] = cats.map((c) => ({ label: c.name, value: monthTotals[c.id] ?? 0, color: c.color })).filter((s) => s.value > 0);
  const monthSpent = spendSlices.reduce((a, s) => a + s.value, 0);

  // planned vs actual share of income
  const allocs = phaseAllocations(state, phase).filter((a) => a.kind !== 'bill');
  const inMonth = (d: string) => d >= mFrom && d <= mTo;
  const student = state.debts.find((d) => d.kind === 'loan');
  const actualAlloc = (key: string, kind: string) => {
    if (kind === 'ef') return state.efTxns.filter((x) => inMonth(x.date) && x.amount > 0).reduce((a, x) => a + x.amount, 0);
    if (kind === 'ws') return state.wsContributions.filter((x) => inMonth(x.date)).reduce((a, x) => a + x.amount, 0);
    if (key === 'cards') return state.debtPayments.filter((p) => inMonth(p.date) && state.debts.find((d) => d.id === p.debtId)?.kind === 'card').reduce((a, p) => a + p.amount, 0);
    if (student && key === `debt:${student.id}`) return state.debtPayments.filter((p) => inMonth(p.date) && p.debtId === student.id).reduce((a, p) => a + p.amount, 0);
    return 0;
  };
  const planned: Slice[] = [
    ...cats.map((c) => ({ label: c.name, value: catMonthly(c), color: c.color })),
    ...allocs.map((a) => ({ label: a.label, value: a.monthly, color: a.color })),
  ].filter((s) => s.value > 0);
  const actual: Slice[] = [
    ...cats.map((c) => ({ label: c.name, value: monthTotals[c.id] ?? 0, color: c.color })),
    ...allocs.map((a) => ({ label: a.label, value: actualAlloc(a.key, a.kind), color: a.color })),
  ];
  const loggedIncome = state.paycheques.filter((p) => inMonth(p.date)).reduce((a, p) => a + p.amount, 0);
  const base = Math.max(income, loggedIncome, actual.reduce((a, s) => a + s.value, 0));

  const openSplits = [...state.paycheques].sort((a, b) => (a.date < b.date ? 1 : -1)).filter((p) => p.split.some((i) => !i.done)).slice(0, 2);
  const lastPc = [...state.paycheques].sort((a, b) => (a.date < b.date ? 1 : -1))[0];
  const payday = nextPayday(t);
  const paydayLogged = state.paycheques.some((p) => p.date === payday);
  const wsT = wsTotal(state);
  const ef = efBalance(state);

  const copy = async () => {
    const ok = await copyText(monthlySummary(state, mk));
    toast(ok ? 'Summary copied — paste it to Claude' : 'Copy failed');
  };

  return (
    <div className="screen">
      <header className="top">
        <div>
          <div className="muted small">{fmtDate(t)}</div>
          <h1>Money</h1>
        </div>
        <button className="streak" onClick={() => go('checkin')} aria-label="Open today's check-in">
          🔥 <b>{st.count}</b><span>day{st.count === 1 ? '' : 's'}</span>
        </button>
      </header>

      {!st.today && (
        <button className="cta" onClick={() => go('checkin')}>
          <span className="cta-e">🌙</span>
          <span><b>What did you spend today?</b><span className="muted small">30-second check-in{st.count ? ` · keep your ${st.count}-day streak` : ''}</span></span>
          <span className="cta-a">›</span>
        </button>
      )}

      {openSplits.map((p) => <SplitCard key={p.id} pc={p} />)}

      {(
        <Card>
          <div className="row">
            <div>
              <div className="muted small">Next payday</div>
              <div className="big">{fmtDate(payday)}</div>
              <div className="muted small">{lastPc ? `Last logged: ${fmt(lastPc.amount)} on ${fmtDate(lastPc.date)}` : 'No paycheques logged yet'}</div>
            </div>
            <button className="btn primary" onClick={() => setPcOpen(true)}>{paydayLogged ? 'Log another' : 'Log paycheque'}</button>
          </div>
        </Card>
      )}

      <Card title={`Phase ${phase} of 3`} action={<button className="link small" onClick={() => go('debt')}>Plan ›</button>}>
        <div className="phases">
          {[1, 2, 3].map((n) => <div key={n} className={`ph ${n < phase ? 'done' : n === phase ? 'now' : ''}`} />)}
        </div>
        <h3 className="ph-title">{PHASE_INFO[phase].title}</h3>
        <p className="muted small">{PHASE_INFO[phase].blurb}</p>
        <div className="grid2 mt">
          <Stat label="Debt-free date" value={proj.debtFree ? fmtDate(proj.debtFree) : '—'} sub={`${fmt(totalDebt(state))} owing`} />
          <Stat label="Net worth" value={fmt(netWorth(state))} tone={netWorth(state) >= 0 ? 'green' : 'red'} />
          <button className="plain" onClick={() => go('savings')}><Stat label="Emergency fund ›" value={fmt(ef)} sub={`${pct(ef / state.settings.emergencyTarget)} of ${fmt(state.settings.emergencyTarget, { whole: true })}`} /></button>
          <button className="plain" onClick={() => go('savings')}><Stat label="Wealthsimple ›" value={fmt(wsT)} sub={state.settings.wsValueUpdated ? `value as of ${fmtDate(state.settings.wsValueUpdated)}` : 'contributions'} /></button>
        </div>
      </Card>

      <Card title="Left this week" action={<span className="muted small">{fmtDate(wFrom).replace(/, \d{4}/, '')} – {fmtDate(wTo).replace(/, \d{4}/, '')}</span>}>
        <div className="stack">
          {cats.filter((c) => !c.fixed && (c.amount > 0 || weekTotals[c.id])).map((c) => (
            <BudgetRow key={c.id} emoji={c.emoji} name={c.name} spent={weekTotals[c.id] ?? 0} budget={catWeekly(c)} color={c.color} sub={c.period === 'month' ? `${fmt(catMonthly(c), { whole: true })}/mo` : undefined} />
          ))}
        </div>
      </Card>

      <Card title={`${fmtMonth(mk)} spending`} action={<button className="link small" onClick={() => go('spending')}>All ›</button>}>
        {monthSpent > 0 ? (
          <div className="chart-row">
            <Donut slices={spendSlices} center={fmt(monthSpent, { whole: true })} sub="spent" />
            <Legend items={spendSlices.sort((a, b) => b.value - a.value).map((s) => ({ label: s.label, color: s.color, value: fmt(s.value) }))} />
          </div>
        ) : (
          <Empty>No spending logged this month yet.</Empty>
        )}
      </Card>

      <Card title="Planned vs actual — % of income">
        <div className="chart-col">
          <DualDonut planned={planned} actual={actual} total={base} />
          <table className="pa">
            <thead><tr><th /><th>Plan</th><th>Actual</th></tr></thead>
            <tbody>
              {planned.map((p) => {
                const a = actual.find((x) => x.label === p.label)?.value ?? 0;
                return (
                  <tr key={p.label}>
                    <td><span className="dot" style={{ background: p.color }} />{p.label}</td>
                    <td>{pct(p.value / income)}</td>
                    <td className={a > p.value + 0.01 && cats.some((c) => c.name === p.label) ? 'red' : ''}>{pct(a / income)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="muted small mt">Percent of {fmt(income)} monthly income. Savings and debt “actuals” come from payments you’ve logged this month.</p>
      </Card>

      <Card title="Debts">
        <div className="stack">
          {state.debts.map((d) => {
            const bal = debtBalance(state, d);
            return (
              <div key={d.id} className="row">
                <span><span className="dot" style={{ background: d.color }} />{d.name}</span>
                <span className="right"><b>{fmt(bal)}</b><span className="muted small block">{bal <= 0 ? 'Paid off 🎉' : `payoff ${fmtDate(proj.payoff[d.id])}`}</span></span>
              </div>
            );
          })}
        </div>
      </Card>

      <button className="btn ghost block" onClick={copy}>📋 Copy monthly summary for Claude</button>
      <PaychequeSheet open={pcOpen} onClose={() => setPcOpen(false)} />
    </div>
  );
}
