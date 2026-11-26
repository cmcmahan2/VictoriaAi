'use client';
import { useMemo, useState } from 'react';
import { useStore } from '@/lib/store';
import { PHASE_INFO, autoPhase, currentPhase, debtBalance, phaseAllocations, project, requiredMonthly, totalDebt, type Phase } from '@/lib/calc';
import { fmt, fmtDate, round2, todayISO, uid } from '@/lib/format';
import type { Debt } from '@/lib/types';
import { Bar, Card, Field, NumInput, Sheet, Stat } from '../ui';
import { LineChart, Legend } from '../charts';

export default function DebtScreen() {
  const { state } = useStore();
  const proj = useMemo(() => project(state), [state]);
  const phase = currentPhase(state);
  const [pay, setPay] = useState<Debt | null>(null);
  const [setBal, setSetBal] = useState<Debt | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const lastDate = proj.debtFree ?? proj.points[proj.points.length - 1]?.date;
  const pts = proj.points.filter((p) => !lastDate || p.date <= lastDate || p === proj.points[0]);
  // include one point past payoff so lines visibly land at $0
  const tail = proj.points.find((p) => lastDate && p.date > lastDate);
  const chartPts = tail ? [...pts, tail] : pts;
  const series = state.debts.map((d) => ({ label: d.name, color: d.color, points: chartPts.map((p) => ({ x: p.date, y: p.balances[d.id] ?? 0 })) }));
  const markers = state.debts.filter((d) => d.deadline && debtBalance(state, d) > 0).map((d) => ({ x: d.deadline!, label: 'deadline', color: '#ff5d6c' }));

  return (
    <div className="screen">
      <header className="top">
        <h1>Debt</h1>
        <span className="muted">{fmt(totalDebt(state))} total</span>
      </header>

      <Card title="The plan">
        <ol className="plan">
          {([1, 2, 3] as Phase[]).map((n) => {
            const allocs = phaseAllocations(state, n).filter((a) => a.kind !== 'bill');
            return (
              <li key={n} className={n < phase ? 'done' : n === phase ? 'now' : ''}>
                <div className="plan-n">{n < phase ? '✓' : n}</div>
                <div>
                  <b>Phase {n}: {PHASE_INFO[n].title}</b>
                  <div className="muted small">{allocs.map((a) => `${a.label} ${fmt(a.monthly, { whole: true })}`).join(' · ')}</div>
                  {n === 2 && proj.phase3 && <div className="small">Phase 3 starts ≈ {fmtDate(proj.phase3)}</div>}
                </div>
              </li>
            );
          })}
        </ol>
        {state.settings.phaseOverride ? <p className="yellow small">Phase is manually set to {phase} in Settings (auto would be {autoPhase(state)}).</p> : <p className="muted small">Advances automatically when the cards hit $0 and the emergency fund hits its target.</p>}
      </Card>

      <Card title="Payoff timeline">
        <LineChart series={series} markers={markers} />
        <Legend items={state.debts.map((d) => ({ label: d.name, color: d.color, value: proj.payoff[d.id] ? fmtDate(proj.payoff[d.id]) : 'not on track' }))} />
        <div className="grid2 mt">
          <Stat label="Debt-free" value={proj.debtFree ? fmtDate(proj.debtFree) : '—'} tone="green" />
          <Stat label="Emergency fund full" value={proj.efFull ? fmtDate(proj.efFull) : '—'} />
        </div>
        <p className="muted small mt">Projection follows your phase plan paycheque by paycheque (15th + last day), with interest charged monthly.</p>
      </Card>

      {state.debts.map((d) => {
        const bal = debtBalance(state, d);
        const paid = Math.max(0, d.originalBalance - bal);
        const payments = state.debtPayments.filter((p) => p.debtId === d.id).sort((a, b) => (a.date < b.date ? 1 : -1));
        const need = d.deadline && bal > 0 ? requiredMonthly(bal, d.apr, d.deadline) : 0;
        const plannedLoan = state.settings.studentLoanPayment;
        const onTrack = !d.deadline || !proj.payoff[d.id] || proj.payoff[d.id]! <= d.deadline;
        return (
          <Card key={d.id} title={<><span className="dot" style={{ background: d.color }} />{d.name}</>} action={<span className="pill">{d.apr}% APR</span>}>
            <div className="row">
              <div>
                <div className="big">{fmt(bal)}</div>
                <div className="muted small">of {fmt(d.originalBalance)} · {fmt(paid)} paid</div>
              </div>
              <div className="right">
                <div className="muted small">Projected payoff</div>
                <b className={bal <= 0 ? 'green' : ''}>{bal <= 0 ? 'Paid off 🎉' : fmtDate(proj.payoff[d.id])}</b>
              </div>
            </div>
            <Bar value={paid} max={d.originalBalance} color={d.color} tone="none" />
            {d.deadline && bal > 0 && (
              <p className={`small mt ${onTrack ? 'green' : 'red'}`}>
                {onTrack ? '✓ On track' : '⚠ Behind'} for {fmtDate(d.deadline)} deadline — needs {fmt(need)}/month (plan: {fmt(plannedLoan)}).
              </p>
            )}
            {d.note && <p className="muted small">{d.note}</p>}
            <div className="grid2 mt">
              <button className="btn primary" onClick={() => setPay(d)}>Log payment</button>
              <button className="btn ghost" onClick={() => setSetBal(d)}>Update balance</button>
            </div>
            {payments.length > 0 && (
              <>
                <button className="link small mt" onClick={() => setOpen(open === d.id ? null : d.id)}>
                  {open === d.id ? 'Hide' : 'Show'} {payments.length} payment{payments.length > 1 ? 's' : ''}
                </button>
                {open === d.id && <PaymentList debtId={d.id} />}
              </>
            )}
          </Card>
        );
      })}

      {pay && <PaySheet debt={pay} onClose={() => setPay(null)} />}
      {setBal && <BalanceSheet debt={setBal} onClose={() => setSetBal(null)} />}
    </div>
  );
}

function PaymentList({ debtId }: { debtId: string }) {
  const { state, update } = useStore();
  const items = state.debtPayments.filter((p) => p.debtId === debtId).sort((a, b) => (a.date < b.date ? 1 : -1));
  return (
    <div className="list mt">
      {items.map((p) => (
        <div key={p.id} className="item">
          <span className="item-m"><span className="item-t">{fmt(p.amount)}</span><span className="item-s">{fmtDate(p.date)}{p.note ? ` · ${p.note}` : ''}</span></span>
          <button className="link danger small" onClick={() => confirm('Delete this payment?') && update((d) => {
            d.debtPayments = d.debtPayments.filter((x) => x.id !== p.id);
            for (const pc of d.paycheques) for (const it of pc.split) if (it.recordId === p.id) { it.done = false; it.recordId = undefined; }
          })}>Delete</button>
        </div>
      ))}
    </div>
  );
}

function PaySheet({ debt, onClose }: { debt: Debt; onClose: () => void }) {
  const { state, update, toast } = useStore();
  const bal = debtBalance(state, debt);
  const [amount, setAmount] = useState<number>(NaN);
  const [date, setDate] = useState(todayISO());
  const [note, setNote] = useState('');
  const save = () => {
    if (!(amount > 0)) return;
    update((d) => { d.debtPayments.push({ id: uid(), debtId: debt.id, date, amount: round2(amount), note: note.trim(), createdAt: Date.now() }); });
    toast(`Payment logged to ${debt.name}`);
    onClose();
  };
  return (
    <Sheet open onClose={onClose} title={`Pay ${debt.name}`} footer={<button className="btn primary block" onClick={save} disabled={!(amount > 0)}>Log payment</button>}>
      <Field label="Amount" hint={<button className="link small" type="button" onClick={() => setAmount(bal)}>Pay full balance ({fmt(bal)})</button>}>
        <NumInput value={amount} onChange={setAmount} autoFocus aria-label="Payment amount" />
      </Field>
      <Field label="Date"><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      <Field label="Note"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="optional" /></Field>
    </Sheet>
  );
}

function BalanceSheet({ debt, onClose }: { debt: Debt; onClose: () => void }) {
  const { state, update, toast } = useStore();
  const [amount, setAmount] = useState<number>(debtBalance(state, debt));
  const [resetOriginal, setResetOriginal] = useState(false);
  const save = () => {
    if (!(amount >= 0)) return;
    update((d) => {
      const x = d.debts.find((y) => y.id === debt.id);
      if (!x) return;
      x.balance = round2(amount);
      x.balanceSetAt = Date.now();
      if (resetOriginal || amount > x.originalBalance) x.originalBalance = round2(amount);
    });
    toast('Balance updated');
    onClose();
  };
  return (
    <Sheet open onClose={onClose} title={`${debt.name} balance`} footer={<button className="btn primary block" onClick={save}>Save balance</button>}>
      <p className="muted small">Enter the balance from your latest statement or app. New charges aren’t tracked here, so update this whenever it changes.</p>
      <Field label="Current balance"><NumInput value={amount} onChange={setAmount} autoFocus aria-label="Balance" /></Field>
      <label className="row-check"><input type="checkbox" checked={resetOriginal} onChange={(e) => setResetOriginal(e.target.checked)} /> Restart progress bar from this balance</label>
    </Sheet>
  );
}
