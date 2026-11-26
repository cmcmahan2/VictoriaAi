'use client';
import { useMemo, useState } from 'react';
import { useStore } from '@/lib/store';
import { deleteEntry } from '@/lib/actions';
import { catById, catMonthly, catWeekly, countsTowardBudget, spendCats, totalsByCat, weekRange } from '@/lib/calc';
import { addDays, fmt, fmtDate, fmtMonth, monthBounds, monthKey, relDay, round2, shiftMonthKey, todayISO, uid } from '@/lib/format';
import type { Entry } from '@/lib/types';
import { BudgetRow, Card, Empty, Field, NumInput, Seg, Sheet } from '../ui';

export default function Spending() {
  const { state } = useStore();
  const [view, setView] = useState<'week' | 'month'>('week');
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState('');
  const [catFilter, setCatFilter] = useState<string | null>(null);
  const [editing, setEditing] = useState<Entry | 'new' | null>(null);
  const t = todayISO();

  const [from, to, label] = useMemo(() => {
    if (view === 'week') {
      const [a, b] = weekRange(addDays(t, offset * 7));
      return [a, b, offset === 0 ? 'This week' : offset === -1 ? 'Last week' : `${fmtDate(a).replace(/, \d{4}/, '')} – ${fmtDate(b)}`];
    }
    const k = shiftMonthKey(monthKey(t), offset);
    const [a, b] = monthBounds(k);
    return [a, b, fmtMonth(k)];
  }, [view, offset, t]);

  const inRange = state.entries.filter((e) => e.date >= from && e.date <= to);
  const counted = inRange.filter((e) => countsTowardBudget(state, e));
  const totals = totalsByCat(counted);
  const cats = spendCats(state).filter((c) => (view === 'month' || !c.fixed) && (c.amount > 0 || totals[c.id]));
  const totalSpent = counted.reduce((a, e) => a + e.amount, 0);
  const totalBudget = cats.reduce((a, c) => a + (view === 'week' ? catWeekly(c) : catMonthly(c)), 0);

  const ql = q.trim().toLowerCase();
  const list = (ql ? state.entries : inRange)
    .filter((e) => !catFilter || e.categoryId === catFilter)
    .filter((e) => !ql || `${e.note} ${e.description ?? ''} ${catById(state, e.categoryId)?.name ?? ''} ${e.amount.toFixed(2)}`.toLowerCase().includes(ql))
    .sort((a, b) => (a.date === b.date ? b.createdAt - a.createdAt : a.date < b.date ? 1 : -1));
  const groups: [string, Entry[]][] = [];
  for (const e of list) {
    const g = groups[groups.length - 1];
    if (g && g[0] === e.date) g[1].push(e);
    else groups.push([e.date, [e]]);
  }

  return (
    <div className="screen">
      <header className="top">
        <h1>Spending</h1>
        <button className="btn small primary" onClick={() => setEditing('new')}>+ Add</button>
      </header>
      <Seg value={view} onChange={(v) => { setView(v); setOffset(0); }} options={[{ value: 'week', label: 'Weekly' }, { value: 'month', label: 'Monthly' }]} />
      <div className="period">
        <button className="icon-btn" onClick={() => setOffset(offset - 1)} aria-label="Previous">‹</button>
        <div className="center">
          <b>{label}</b>
          <div className="muted small">{fmt(totalSpent)} of {fmt(totalBudget)}</div>
        </div>
        <button className="icon-btn" onClick={() => setOffset(Math.min(0, offset + 1))} disabled={offset >= 0} aria-label="Next">›</button>
      </div>

      <Card>
        <div className="stack">
          {cats.map((c) => (
            <button key={c.id} className={`plain ${catFilter === c.id ? 'sel' : ''}`} onClick={() => setCatFilter(catFilter === c.id ? null : c.id)}>
              <BudgetRow emoji={c.emoji} name={c.name} spent={totals[c.id] ?? 0} budget={view === 'week' ? catWeekly(c) : catMonthly(c)} color={c.color} />
            </button>
          ))}
        </div>
        {catFilter && <button className="link small mt" onClick={() => setCatFilter(null)}>Show all categories</button>}
      </Card>

      <div className="search">
        <input type="search" placeholder="Search all spending…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
      </div>

      {groups.length === 0 && <Empty>{ql ? 'No matches.' : 'Nothing logged in this period.'}</Empty>}
      {groups.map(([d, items]) => (
        <div key={d} className="group">
          <div className="group-h">
            <span>{relDay(d)}{relDay(d).startsWith('To') || relDay(d).startsWith('Ye') ? '' : ''}</span>
            <span className="muted">{fmt(items.filter((e) => countsTowardBudget(state, e)).reduce((a, e) => a + e.amount, 0))}</span>
          </div>
          <div className="list">
            {items.map((e) => {
              const c = catById(state, e.categoryId);
              const dim = !countsTowardBudget(state, e);
              return (
                <button key={e.id} className={`item ${dim ? 'dim' : ''}`} onClick={() => setEditing(e)}>
                  <span className="item-e" style={{ background: `${c?.color ?? '#666'}22` }}>{c?.emoji ?? '•'}</span>
                  <span className="item-m">
                    <span className="item-t">{e.note || e.description || c?.name}</span>
                    <span className="item-s">
                      {c?.name}
                      {e.source === 'import' && <span className="tag">{e.account}</span>}
                      {e.matchedImportId && <span className="tag green">✓ on statement</span>}
                      {e.matchedManualId && <span className="tag">matched</span>}
                      {ql && <> · {fmtDate(e.date)}</>}
                    </span>
                  </span>
                  <span className="item-a">{fmt(e.amount)}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
      <EntrySheet entry={editing} onClose={() => setEditing(null)} />
    </div>
  );
}

export function EntrySheet({ entry, onClose }: { entry: Entry | 'new' | null; onClose: () => void }) {
  const open = entry != null;
  return open ? <EntryForm key={entry === 'new' ? 'new' : entry.id} entry={entry} onClose={onClose} /> : null;
}

function EntryForm({ entry, onClose }: { entry: Entry | 'new'; onClose: () => void }) {
  const { state, update, toast } = useStore();
  const isNew = entry === 'new';
  const [amount, setAmount] = useState<number>(isNew ? NaN : entry.amount);
  const [date, setDate] = useState(isNew ? todayISO() : entry.date);
  const [cat, setCat] = useState(isNew ? 'eating' : entry.categoryId);
  const [note, setNote] = useState(isNew ? '' : entry.note);
  const save = () => {
    if (!(amount > 0)) return;
    update((d) => {
      if (isNew) d.entries.push({ id: uid(), date, amount: round2(amount), categoryId: cat, note: note.trim(), source: 'manual', createdAt: Date.now() });
      else {
        const e = d.entries.find((x) => x.id === entry.id);
        if (e) Object.assign(e, { date, amount: round2(amount), categoryId: cat, note: note.trim() });
      }
    });
    toast(isNew ? 'Added' : 'Saved');
    onClose();
  };
  const del = () => {
    if (isNew) return;
    if (!confirm('Delete this item?')) return;
    update((d) => deleteEntry(d, entry.id));
    toast('Deleted');
    onClose();
  };
  return (
    <Sheet
      open
      onClose={onClose}
      title={isNew ? 'Add spending' : 'Edit spending'}
      footer={
        <div className="grid2">
          {!isNew ? <button className="btn danger" onClick={del}>Delete</button> : <button className="btn ghost" onClick={onClose}>Cancel</button>}
          <button className="btn primary" onClick={save} disabled={!(amount > 0)}>Save</button>
        </div>
      }
    >
      <Field label="Amount"><NumInput value={amount} onChange={setAmount} autoFocus={isNew} aria-label="Amount" /></Field>
      <Field label="Category">
        <div className="chips">
          {state.categories.map((c) => (
            <button key={c.id} type="button" className={`chip ${cat === c.id ? 'on' : ''}`} style={cat === c.id ? { borderColor: c.color, background: `${c.color}22` } : undefined} onClick={() => setCat(c.id)}>
              <span>{c.emoji}</span>{c.name}
            </button>
          ))}
        </div>
      </Field>
      <Field label="Note"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="bowling + drinks" /></Field>
      <Field label="Date"><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      {!isNew && entry.source === 'import' && <p className="muted small">From {entry.account} statement: “{entry.description}”</p>}
      {!isNew && entry.matchedImportId && <p className="muted small">✓ Matched to a statement line, so it isn’t counted twice.</p>}
    </Sheet>
  );
}
