'use client';
import { useState } from 'react';
import { useStore } from '@/lib/store';
import { addPaycheque, deletePaycheque, toggleSplit } from '@/lib/actions';
import { buildSplit, PHASE_INFO, spendCats, catMonthly } from '@/lib/calc';
import { fmt, fmtDate, round2, todayISO } from '@/lib/format';
import type { Paycheque, WsAccount } from '@/lib/types';
import { Card, Check, Field, NumInput, Sheet } from './ui';

export function PaychequeSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { state, update, toast } = useStore();
  const [date, setDate] = useState(todayISO());
  const [amount, setAmount] = useState<number>(state.settings.paychequeAmount);
  const [note, setNote] = useState('');
  const preview = buildSplit(state);
  const save = () => {
    if (!(amount > 0)) return;
    update((d) => addPaycheque(d, date, round2(amount), note.trim()));
    toast('Paycheque logged — check off your split');
    setNote('');
    onClose();
  };
  return (
    <Sheet open={open} onClose={onClose} title="Log paycheque" footer={<button className="btn primary block" onClick={save} disabled={!(amount > 0)}>Save paycheque</button>}>
      <Field label="Amount received">
        <NumInput value={amount} onChange={setAmount} aria-label="Paycheque amount" />
      </Field>
      <Field label="Pay date">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </Field>
      <Field label="Note (optional)">
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. includes overtime" />
      </Field>
      <p className="muted small">You’re in Phase {preview.phase}: {PHASE_INFO[preview.phase].title}. The split will be: {preview.items.map((i) => `${i.label.replace(' payment', '')} ${fmt(i.amount)}`).join(' · ')}.</p>
    </Sheet>
  );
}

export function SplitCard({ pc }: { pc: Paycheque }) {
  const { state, update, toast } = useStore();
  const allocated = pc.split.reduce((a, i) => a + i.amount, 0);
  const variableHalf = spendCats(state).filter((c) => !c.fixed).reduce((a, c) => a + catMonthly(c), 0) / (state.settings.paychequesPerMonth || 2);
  const leftover = pc.amount - allocated;
  const doneCount = pc.split.filter((i) => i.done).length;
  const setAcct = (key: string, acct: WsAccount) =>
    update((d) => {
      const it = d.paycheques.find((p) => p.id === pc.id)?.split.find((i) => i.key === key);
      if (it && !it.done) it.wsAccount = acct;
    });
  return (
    <Card
      className="split"
      title={<>💸 Paycheque split <span className="muted small">· {fmtDate(pc.date)}</span></>}
      action={<span className="pill">{doneCount}/{pc.split.length} done</span>}
    >
      <div className="split-head">
        <div>
          <div className="big">{fmt(pc.amount)}</div>
          <div className="muted small">Phase {pc.phase} · half of each monthly amount</div>
        </div>
      </div>
      <div className="stack-s">
        {pc.split.map((it) => (
          <div key={it.key} className="split-row">
            <Check
              checked={it.done}
              onChange={(v) => {
                update((d) => toggleSplit(d, pc.id, it.key, v));
                if (v && it.kind !== 'bill') toast(`Logged ${fmt(it.amount)} → ${it.label.replace(' payment', '')}`);
              }}
              label={<span className="split-l"><span>{it.label}</span><b>{fmt(it.amount)}</b></span>}
              sub={it.kind === 'ws' ? `Wealthsimple ${it.wsAccount}` : it.kind === 'bill' ? 'Keep in chequing for the bill' : it.kind === 'debt' ? 'Logs a debt payment' : 'Logs a deposit'}
            />
            {it.kind === 'ws' && !it.done && (
              <div className="mini-seg">
                {(['FHSA', 'TFSA'] as WsAccount[]).map((a) => (
                  <button key={a} className={it.wsAccount === a ? 'on' : ''} onClick={() => setAcct(it.key, a)}>{a}</button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="split-foot">
        <div><span className="muted">Spending money for this half</span><b>{fmt(leftover)}</b></div>
        <div className="muted small">Budgeted day-to-day spending per half: {fmt(variableHalf)}</div>
      </div>
      <div className="row gap">
        {doneCount === pc.split.length ? <span className="green small">All done — nice.</span> : <span className="muted small">Tap each item once you’ve moved the money.</span>}
        <button
          className="link danger small"
          onClick={() => {
            if (confirm('Delete this paycheque and any payments it logged?')) update((d) => deletePaycheque(d, pc.id));
          }}
        >
          Delete
        </button>
      </div>
    </Card>
  );
}
