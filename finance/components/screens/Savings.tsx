'use client';
import { useState } from 'react';
import { useStore } from '@/lib/store';
import { defaultWsAccount, efBalance, project, wsContributed, wsTotal, wsValue } from '@/lib/calc';
import { daysBetween, fmt, fmtDate, pct, round2, todayISO, uid } from '@/lib/format';
import type { WsAccount } from '@/lib/types';
import { Bar, Card, Check, Empty, Field, NumInput, Seg, Sheet, Stat } from '../ui';

export default function Savings() {
  const { state, update } = useStore();
  const [efOpen, setEfOpen] = useState(false);
  const [wsOpen, setWsOpen] = useState(false);
  const [newItem, setNewItem] = useState('');
  const ef = efBalance(state);
  const target = state.settings.emergencyTarget;
  const year = new Date().getFullYear();
  const proj = project(state);
  const efTx = [...state.efTxns].sort((a, b) => (a.date < b.date ? 1 : -1));
  const wsTx = [...state.wsContributions].sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <div className="screen">
      <header className="top">
        <h1>Savings & investing</h1>
      </header>

      <Card title="🛟 Emergency fund" action={<span className="pill">{pct(ef / target)}</span>}>
        <div className="row">
          <div className="big">{fmt(ef)}</div>
          <div className="right muted small">target {fmt(target)}<br />{ef >= target ? 'Full ✓' : `full ≈ ${fmtDate(proj.efFull)}`}</div>
        </div>
        <Bar value={ef} max={target} color="#34d399" tone="none" />
        <button className="btn primary block mt" onClick={() => setEfOpen(true)}>Deposit / withdraw</button>
        {efTx.length > 0 && (
          <div className="list mt">
            {efTx.slice(0, 8).map((t) => (
              <div className="item" key={t.id}>
                <span className="item-m"><span className="item-t">{fmt(t.amount, { sign: true })}</span><span className="item-s">{fmtDate(t.date)}{t.note ? ` · ${t.note}` : ''}</span></span>
                <button className="link danger small" onClick={() => confirm('Delete this entry?') && update((d) => { d.efTxns = d.efTxns.filter((x) => x.id !== t.id); unlinkSplit(d, t.id); })}>Delete</button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="📈 Wealthsimple" action={<span className="pill">{fmt(wsTotal(state))}</span>}>
        <div className="stack">
          {(['FHSA', 'TFSA'] as WsAccount[]).map((a) => {
            const contrib = wsContributed(state, a);
            const thisYear = wsContributed(state, a, year);
            const val = state.settings.wsValue[a];
            const gain = val != null ? val - contrib : null;
            const limit = a === 'FHSA' ? state.settings.fhsaAnnualLimit : state.settings.tfsaRoom;
            return (
              <div key={a} className="sub">
                <div className="row">
                  <b>{a}{a === 'FHSA' && !state.settings.fhsaOpened && <span className="tag yellow">not opened</span>}</b>
                  <span className="muted small">{a === 'FHSA' ? `${fmt(thisYear)} of ${fmt(limit, { whole: true })} in ${year}` : `${fmt(thisYear)} of ${fmt(limit, { whole: true })} room`}</span>
                </div>
                <Bar value={thisYear} max={limit} color={a === 'FHSA' ? '#818cf8' : '#60a5fa'} />
                <div className="grid2 mt">
                  <Field label="Current value">
                    <NumInput
                      value={val ?? NaN}
                      placeholder={contrib.toFixed(2)}
                      onChange={(n) => update((d) => { d.settings.wsValue[a] = Number.isFinite(n) ? n : null; d.settings.wsValueUpdated = todayISO(); })}
                      aria-label={`${a} current value`}
                    />
                  </Field>
                  <Stat label="Contributed" value={fmt(contrib)} sub={gain != null ? <span className={gain >= 0 ? 'green' : 'red'}>{fmt(gain, { sign: true })} growth</span> : 'enter value from app'} />
                </div>
                {a === 'FHSA' && <p className="muted small">Lifetime: {fmt(contrib)} of {fmt(state.settings.fhsaLifetimeLimit, { whole: true })}. Unused room carries forward (max {fmt(state.settings.fhsaAnnualLimit, { whole: true })}) only once the account is open.</p>}
                {a === 'TFSA' && <p className="muted small">Room is editable in Settings — check CRA My Account for your exact number.</p>}
              </div>
            );
          })}
        </div>
        <button className="btn primary block mt" onClick={() => setWsOpen(true)}>Log contribution</button>
        {wsTx.length > 0 ? (
          <div className="list mt">
            {wsTx.slice(0, 12).map((t) => (
              <div className="item" key={t.id}>
                <span className="item-m"><span className="item-t">{fmt(t.amount)} <span className="tag">{t.account}</span></span><span className="item-s">{fmtDate(t.date)}{t.note ? ` · ${t.note}` : ''}</span></span>
                <button className="link danger small" onClick={() => confirm('Delete this contribution?') && update((d) => { d.wsContributions = d.wsContributions.filter((x) => x.id !== t.id); unlinkSplit(d, t.id); })}>Delete</button>
              </div>
            ))}
          </div>
        ) : <Empty>No contributions logged yet.</Empty>}
      </Card>

      <Card title="✅ Checklist">
        <div className="stack-s">
          {state.checklist.map((c) => {
            const days = c.due ? daysBetween(todayISO(), c.due) : null;
            return (
              <div key={c.id} className="split-row">
                <Check
                  checked={c.done}
                  onChange={(v) => update((d) => {
                    const x = d.checklist.find((y) => y.id === c.id);
                    if (x) x.done = v;
                    if (c.id === 'fhsa') d.settings.fhsaOpened = v;
                  })}
                  label={c.text}
                  sub={c.due && !c.done ? (days! < 0 ? <span className="red">overdue</span> : <span className={days! <= 14 ? 'yellow' : ''}>{days} days left</span>) : undefined}
                />
                {c.id !== 'fhsa' && <button className="link danger small" onClick={() => update((d) => { d.checklist = d.checklist.filter((y) => y.id !== c.id); })} aria-label="Remove">✕</button>}
              </div>
            );
          })}
        </div>
        <form className="compose-row mt" onSubmit={(e) => { e.preventDefault(); if (!newItem.trim()) return; update((d) => { d.checklist.push({ id: uid(), text: newItem.trim(), done: false }); }); setNewItem(''); }}>
          <input value={newItem} onChange={(e) => setNewItem(e.target.value)} placeholder="Add a to-do…" />
          <button className="btn ghost" type="submit">Add</button>
        </form>
      </Card>

      {efOpen && <EfSheet onClose={() => setEfOpen(false)} />}
      {wsOpen && <WsSheet onClose={() => setWsOpen(false)} />}
    </div>
  );
}

function unlinkSplit(d: import('@/lib/types').AppState, recordId: string) {
  for (const pc of d.paycheques) for (const it of pc.split) if (it.recordId === recordId) { it.done = false; it.recordId = undefined; }
}

function EfSheet({ onClose }: { onClose: () => void }) {
  const { update, toast } = useStore();
  const [dir, setDir] = useState<'in' | 'out'>('in');
  const [amount, setAmount] = useState<number>(NaN);
  const [date, setDate] = useState(todayISO());
  const [note, setNote] = useState('');
  const save = () => {
    if (!(amount > 0)) return;
    update((d) => { d.efTxns.push({ id: uid(), date, amount: round2(dir === 'in' ? amount : -amount), note: note.trim(), createdAt: Date.now() }); });
    toast(dir === 'in' ? 'Deposit logged' : 'Withdrawal logged');
    onClose();
  };
  return (
    <Sheet open onClose={onClose} title="Emergency fund" footer={<button className="btn primary block" onClick={save} disabled={!(amount > 0)}>Save</button>}>
      <Seg value={dir} onChange={setDir} options={[{ value: 'in', label: 'Deposit' }, { value: 'out', label: 'Withdraw' }]} />
      <Field label="Amount"><NumInput value={amount} onChange={setAmount} autoFocus aria-label="Amount" /></Field>
      <Field label="Date"><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      <Field label="Note"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="optional" /></Field>
    </Sheet>
  );
}

function WsSheet({ onClose }: { onClose: () => void }) {
  const { state, update, toast } = useStore();
  const [account, setAccount] = useState<WsAccount>(defaultWsAccount(state));
  const [amount, setAmount] = useState<number>(NaN);
  const [date, setDate] = useState(todayISO());
  const [note, setNote] = useState('');
  const year = new Date().getFullYear();
  const fhsaLeft = state.settings.fhsaAnnualLimit - wsContributed(state, 'FHSA', year);
  const over = account === 'FHSA' && amount > fhsaLeft;
  const save = () => {
    if (!(amount > 0)) return;
    update((d) => { d.wsContributions.push({ id: uid(), date, account, amount: round2(amount), note: note.trim(), createdAt: Date.now() }); });
    toast(`${account} contribution logged`);
    onClose();
  };
  return (
    <Sheet open onClose={onClose} title="Wealthsimple contribution" footer={<button className="btn primary block" onClick={save} disabled={!(amount > 0)}>Save</button>}>
      <Seg value={account} onChange={setAccount} options={[{ value: 'FHSA', label: 'FHSA' }, { value: 'TFSA', label: 'TFSA' }]} />
      <Field label="Amount" hint={account === 'FHSA' ? <span className={over ? 'red' : ''}>{fmt(Math.max(0, fhsaLeft))} FHSA room left in {year}</span> : undefined}>
        <NumInput value={amount} onChange={setAmount} autoFocus aria-label="Amount" />
      </Field>
      <Field label="Date"><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      <Field label="Note"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="optional" /></Field>
      {account === 'FHSA' && !state.settings.fhsaOpened && <p className="yellow small">Your FHSA isn’t marked as opened yet — tick it off in the checklist once it is.</p>}
    </Sheet>
  );
}
