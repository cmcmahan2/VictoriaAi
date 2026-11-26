'use client';
import { useEffect, useState } from 'react';
import { useStore } from '@/lib/store';
import { autoPhase, catMonthly, catWeekly, debtBalance, monthlyIncome, phaseAllocations, currentPhase, spendBudgetMonthly } from '@/lib/calc';
import { fmt, fmtDate, monthKey, pct, round2, todayISO, toISO, uid } from '@/lib/format';
import { downloadText } from '@/lib/csv';
import { hydrate, makeDefaultState } from '@/lib/defaults';
import { copyText, monthlySummary } from '@/lib/summary';
import type { AppState, Category, Debt } from '@/lib/types';
import { Card, Field, Seg } from '../ui';

/** Number field with local text so clearing/typing doesn't fight the store. */
function Num({ value, onCommit, prefix = '$', label, suffix }: { value: number; onCommit: (n: number) => void; prefix?: string; label: string; suffix?: string }) {
  const [t, setT] = useState(String(value));
  useEffect(() => { if (parseFloat(t) !== value) setT(Number.isFinite(value) ? String(value) : ''); }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="num">
      {prefix && <span className="num-p">{prefix}</span>}
      <input type="number" inputMode="decimal" step="any" aria-label={label} value={t} onFocus={(e) => e.target.select()}
        onChange={(e) => { setT(e.target.value); const n = parseFloat(e.target.value); if (Number.isFinite(n)) onCommit(n); }} />
      {suffix && <span className="num-s">{suffix}</span>}
    </div>
  );
}

export default function Settings() {
  const { state, update, replace, toast } = useStore();
  const s = state.settings;
  const income = monthlyIncome(state);
  const set = (fn: (d: AppState) => void) => update(fn);
  const phase = currentPhase(state);
  const allocs = phaseAllocations(state, phase).filter((a) => a.kind !== 'bill');
  const planned = spendBudgetMonthly(state) + allocs.reduce((a, x) => a + x.monthly, 0);

  const exportJSON = () => {
    downloadText(`pocketplan-backup-${todayISO()}.json`, JSON.stringify(state, null, 2), 'application/json');
    set((d) => { d.settings.lastBackupAt = Date.now(); });
    toast('Backup downloaded');
  };
  const importJSON = async (file: File) => {
    try {
      const data = JSON.parse(await file.text());
      if (!data || typeof data !== 'object' || !('settings' in data)) throw new Error('bad');
      if (!confirm('Replace ALL current data with this backup?')) return;
      replace(hydrate(data));
      toast('Backup restored');
    } catch {
      toast('That isn’t a valid backup file');
    }
  };

  return (
    <div className="screen settings">
      <header className="top"><h1>Settings</h1></header>

      <Card title="Income">
        <div className="grid2">
          <Field label="Per paycheque"><Num label="Paycheque amount" value={s.paychequeAmount} onCommit={(n) => set((d) => { d.settings.paychequeAmount = n; })} /></Field>
          <Field label="Paycheques / month"><Num label="Paycheques per month" prefix="" value={s.paychequesPerMonth} onCommit={(n) => set((d) => { d.settings.paychequesPerMonth = Math.max(1, Math.round(n)); })} /></Field>
        </div>
        <p className="muted small">= {fmt(income)}/month. Paydays: 15th and last day of the month.</p>
      </Card>

      <Card title="Spending budgets" action={<span className="muted small">{fmt(spendBudgetMonthly(state))}/mo</span>}>
        <div className="stack">
          {state.categories.filter((c) => !c.ignore).map((c) => <CatEditor key={c.id} c={c} income={income} />)}
        </div>
        <button className="btn ghost block mt" onClick={() => set((d) => { d.categories.splice(d.categories.length - 2, 0, { id: uid(), name: 'New category', emoji: '✨', color: '#22d3ee', amount: 0, period: 'month', fixed: false, keywords: [] }); })}>+ Add category</button>
        <p className="muted small mt">Weekly budgets convert to monthly as weekly × 52 ÷ 12.</p>
      </Card>

      <Card title="Plan amounts">
        <div className="grid2">
          <Field label="Student loan / mo" hint={pct(s.studentLoanPayment / income)}><Num label="Student loan payment" value={s.studentLoanPayment} onCommit={(n) => set((d) => { d.settings.studentLoanPayment = n; })} /></Field>
          <Field label="Loan minimum (Phase 1)"><Num label="Student loan minimum" value={s.studentLoanMinimum} onCommit={(n) => set((d) => { d.settings.studentLoanMinimum = n; })} /></Field>
          <Field label="Emergency fund / mo" hint={pct(s.emergencyMonthly / income)}><Num label="Emergency fund monthly" value={s.emergencyMonthly} onCommit={(n) => set((d) => { d.settings.emergencyMonthly = n; })} /></Field>
          <Field label="Wealthsimple / mo" hint={pct(s.wealthsimpleMonthly / income)}><Num label="Wealthsimple monthly" value={s.wealthsimpleMonthly} onCommit={(n) => set((d) => { d.settings.wealthsimpleMonthly = n; })} /></Field>
          <Field label="Emergency fund target"><Num label="Emergency fund target" value={s.emergencyTarget} onCommit={(n) => set((d) => { d.settings.emergencyTarget = n; })} /></Field>
        </div>
        <Field label="Phase">
          <Seg value={String(s.phaseOverride)} onChange={(v) => set((d) => { d.settings.phaseOverride = Number(v) as 0 | 1 | 2 | 3; })}
            options={[{ value: '0', label: `Auto (${autoPhase(state)})` }, { value: '1', label: '1' }, { value: '2', label: '2' }, { value: '3', label: '3' }]} />
        </Field>
        <p className={`small ${Math.abs(planned - income) > 1 ? 'yellow' : 'muted'}`}>
          Phase {phase} plan uses {fmt(planned)} of {fmt(income)}{Math.abs(planned - income) > 1 ? ` — ${fmt(income - planned, { sign: true })} unassigned` : ' — every dollar has a job.'}
        </p>
      </Card>

      <Card title="Debts">
        <div className="stack">{state.debts.map((d) => <DebtEditor key={d.id} d={d} />)}</div>
        <button className="btn ghost block mt" onClick={() => set((x) => { x.debts.push({ id: uid(), name: 'New debt', kind: 'card', apr: 19.99, color: '#f87171', originalBalance: 0, balance: 0, balanceSetAt: Date.now(), note: '' }); })}>+ Add debt</button>
        <p className="muted small mt">Cards are paid off first (highest APR first) in Phase 1. Loans get the student-loan payment.</p>
      </Card>

      <Card title="Savings & investing">
        <div className="grid2">
          <Field label="Emergency fund start"><Num label="Emergency fund starting balance" value={s.efStartBalance} onCommit={(n) => set((d) => { d.settings.efStartBalance = n; })} /></Field>
          <Field label="TFSA room (this year)"><Num label="TFSA room" value={s.tfsaRoom} onCommit={(n) => set((d) => { d.settings.tfsaRoom = n; })} /></Field>
          <Field label="FHSA annual limit"><Num label="FHSA annual limit" value={s.fhsaAnnualLimit} onCommit={(n) => set((d) => { d.settings.fhsaAnnualLimit = n; })} /></Field>
          <Field label="FHSA lifetime limit"><Num label="FHSA lifetime limit" value={s.fhsaLifetimeLimit} onCommit={(n) => set((d) => { d.settings.fhsaLifetimeLimit = n; })} /></Field>
          <Field label="Other cash (net worth)"><Num label="Other cash" value={s.otherCash} onCommit={(n) => set((d) => { d.settings.otherCash = n; })} /></Field>
        </div>
        <label className="row-check"><input type="checkbox" checked={s.fhsaOpened} onChange={(e) => set((d) => { d.settings.fhsaOpened = e.target.checked; const c = d.checklist.find((x) => x.id === 'fhsa'); if (c) c.done = e.target.checked; })} /> FHSA is open (new contributions default to FHSA until the yearly limit)</label>
      </Card>

      <Card title="Vehicle">
        <Field label="Vehicle"><input value={s.vehicleName} onChange={(e) => set((d) => { d.settings.vehicleName = e.target.value; })} /></Field>
        <Field label={`Odometer on Jan 1, ${new Date().getFullYear()}`}><Num label="Odometer at start of year" prefix="" suffix="km" value={s.odometerYearStart[String(new Date().getFullYear())] ?? NaN} onCommit={(n) => set((d) => { d.settings.odometerYearStart[String(new Date().getFullYear())] = n; })} /></Field>
        <div className="grid2">
          <Field label="Quick trip from"><input value={s.abbyTrip.from} onChange={(e) => set((d) => { d.settings.abbyTrip.from = e.target.value; })} /></Field>
          <Field label="Quick trip to"><input value={s.abbyTrip.to} onChange={(e) => set((d) => { d.settings.abbyTrip.to = e.target.value; })} /></Field>
          <Field label="Purpose"><input value={s.abbyTrip.purpose} onChange={(e) => set((d) => { d.settings.abbyTrip.purpose = e.target.value; })} /></Field>
          <Field label="Round-trip km"><Num label="Quick trip km" prefix="" suffix="km" value={s.abbyTrip.km} onCommit={(n) => set((d) => { d.settings.abbyTrip.km = n; })} /></Field>
        </div>
      </Card>

      <Card title="Data & backup">
        <p className="muted small">Everything lives only in this browser. {s.lastBackupAt ? `Last backup: ${fmtDate(toISO(new Date(s.lastBackupAt)))}.` : <span className="yellow">You haven’t made a backup yet.</span>}</p>
        <div className="stack mt">
          <button className="btn primary block" onClick={exportJSON}>⬇ Export JSON backup</button>
          <label className="btn ghost block filebtn">⬆ Restore from backup<input type="file" accept=".json,application/json" onChange={(e) => { const f = e.target.files?.[0]; if (f) importJSON(f); e.target.value = ''; }} /></label>
          <button className="btn ghost block" onClick={async () => toast((await copyText(monthlySummary(state, monthKey(todayISO())))) ? 'Summary copied' : 'Copy failed')}>📋 Copy monthly summary</button>
          <button className="btn danger block" onClick={() => { if (confirm('Erase everything and start over? Export a backup first!') && confirm('Really erase all data?')) { replace(makeDefaultState()); toast('Reset'); } }}>Erase all data</button>
        </div>
        <p className="muted small mt">On iPhone: Share → Add to Home Screen. Safari can clear website data that goes unused for a while, so export a backup every week or two.</p>
      </Card>
    </div>
  );
}

function CatEditor({ c, income }: { c: Category; income: number }) {
  const { update } = useStore();
  const [open, setOpen] = useState(false);
  const up = (p: Partial<Category>) => update((d) => { const x = d.categories.find((y) => y.id === c.id); if (x) Object.assign(x, p); });
  return (
    <div className="sub">
      <button className="row plain" onClick={() => setOpen(!open)}>
        <span><span className="emoji">{c.emoji}</span>{c.name}{c.fixed && <span className="tag">fixed</span>}</span>
        <span className="right small">
          <b>{c.period === 'week' ? `${fmt(c.amount)}/wk` : `${fmt(c.amount)}/mo`}</b>
          <span className="muted block">{c.period === 'week' ? `${fmt(catMonthly(c))}/mo` : `${fmt(catWeekly(c))}/wk`} · {pct(catMonthly(c) / income)}</span>
        </span>
      </button>
      {open && (
        <div className="mt">
          <div className="grid2">
            <Field label="Name"><input value={c.name} onChange={(e) => up({ name: e.target.value })} /></Field>
            <Field label="Emoji / colour">
              <div className="row gap-s"><input className="emoji-in" value={c.emoji} onChange={(e) => up({ emoji: e.target.value })} aria-label="Emoji" /><input type="color" value={c.color} onChange={(e) => up({ color: e.target.value })} aria-label="Colour" /></div>
            </Field>
            <Field label="Budget"><Num label={`${c.name} budget`} value={c.amount} onCommit={(n) => up({ amount: round2(n) })} /></Field>
            <Field label="Per">
              <Seg value={c.period} onChange={(v) => up({ period: v })} options={[{ value: 'week', label: 'Week' }, { value: 'month', label: 'Month' }]} />
            </Field>
          </div>
          <Field label="Note keywords (for the check-in guess)"><input value={c.keywords.join(', ')} onChange={(e) => up({ keywords: e.target.value.split(',').map((k) => k.trim()).filter(Boolean) })} /></Field>
          <div className="row">
            <label className="row-check"><input type="checkbox" checked={c.fixed} onChange={(e) => up({ fixed: e.target.checked })} /> Fixed monthly bill</label>
            {!['eating', 'drinks', 'gas', 'lifestyle', 'insurance', 'other'].includes(c.id) && (
              <button className="link danger small" onClick={() => confirm(`Delete ${c.name}? Its spending moves to Other.`) && update((d) => { d.categories = d.categories.filter((y) => y.id !== c.id); d.entries.forEach((e) => { if (e.categoryId === c.id) e.categoryId = 'other'; }); d.rules = d.rules.filter((r) => r.categoryId !== c.id); })}>Delete</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DebtEditor({ d }: { d: Debt }) {
  const { state, update } = useStore();
  const [open, setOpen] = useState(false);
  const bal = debtBalance(state, d);
  const up = (p: Partial<Debt>) => update((x) => { const y = x.debts.find((z) => z.id === d.id); if (y) Object.assign(y, p); });
  return (
    <div className="sub">
      <button className="row plain" onClick={() => setOpen(!open)}>
        <span><span className="dot" style={{ background: d.color }} />{d.name}</span>
        <span className="right small"><b>{fmt(bal)}</b><span className="muted block">{d.apr}% APR</span></span>
      </button>
      {open && (
        <div className="mt">
          <div className="grid2">
            <Field label="Name"><input value={d.name} onChange={(e) => up({ name: e.target.value })} /></Field>
            <Field label="APR"><Num label="APR" prefix="" suffix="%" value={d.apr} onCommit={(n) => up({ apr: n })} /></Field>
            <Field label="Current balance"><Num label="Current balance" value={bal} onCommit={(n) => up({ balance: round2(n), balanceSetAt: Date.now(), originalBalance: Math.max(d.originalBalance, round2(n)) })} /></Field>
            <Field label="Starting balance"><Num label="Starting balance" value={d.originalBalance} onCommit={(n) => up({ originalBalance: round2(n) })} /></Field>
            <Field label="Type"><Seg value={d.kind} onChange={(v) => up({ kind: v })} options={[{ value: 'card', label: 'Card' }, { value: 'loan', label: 'Loan' }]} /></Field>
            <Field label="Payoff deadline"><input type="date" value={d.deadline ?? ''} onChange={(e) => up({ deadline: e.target.value || undefined })} /></Field>
          </div>
          <div className="row">
            <input type="color" value={d.color} onChange={(e) => up({ color: e.target.value })} aria-label="Colour" />
            {!['amex', 'tangerine', 'student'].includes(d.id) && <button className="link danger small" onClick={() => confirm(`Delete ${d.name}?`) && update((x) => { x.debts = x.debts.filter((y) => y.id !== d.id); x.debtPayments = x.debtPayments.filter((p) => p.debtId !== d.id); })}>Delete</button>}
          </div>
        </div>
      )}
    </div>
  );
}
