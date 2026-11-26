'use client';
import { useRef, useState } from 'react';
import { useStore } from '@/lib/store';
import { addEntries, markCheckin } from '@/lib/actions';
import { catById, entriesIn, guessCategory, loggedDays, parseQuick, spendCats, streak } from '@/lib/calc';
import { addDays, fmt, relDay, round2, todayISO } from '@/lib/format';
import type { Tab } from '../Shell';

interface Pending { key: number; amount: number; categoryId: string; note: string }

export default function CheckIn({ go }: { go: (t: Tab) => void }) {
  const { state, update, toast } = useStore();
  const t = todayISO();
  const [date, setDate] = useState(t);
  const [text, setText] = useState('');
  const [picked, setPicked] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const [done, setDone] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const cats = spendCats(state);
  const parsed = parseQuick(text);
  const guessed = parsed.note ? guessCategory(state, parsed.note) : null;
  const cat = picked ?? guessed ?? null;
  const canAdd = parsed.amount != null && parsed.amount > 0 && !!cat;
  const logged = entriesIn(state, date, date).filter((e) => e.source === 'manual');
  const days = loggedDays(state);
  const s = streak(state);

  const add = () => {
    if (!canAdd || !cat) return;
    setPending((p) => [...p, { key: Date.now() + Math.random(), amount: round2(parsed.amount!), categoryId: cat, note: parsed.note }]);
    setText('');
    setPicked(null);
    input.current?.focus();
  };

  const save = () => {
    const items = [...pending];
    if (canAdd && cat) items.push({ key: 0, amount: round2(parsed.amount!), categoryId: cat, note: parsed.note });
    if (!items.length) return;
    update((d) => {
      addEntries(d, items.map((i) => ({ date, amount: i.amount, categoryId: i.categoryId, note: i.note })));
      markCheckin(d, date);
    });
    const total = items.reduce((a, i) => a + i.amount, 0);
    toast(`Saved ${items.length} item${items.length > 1 ? 's' : ''} · ${fmt(total)}`);
    setPending([]);
    setText('');
    setPicked(null);
    setDone(true);
  };

  const nothing = () => {
    update((d) => markCheckin(d, date));
    toast('Nothing spent — streak kept 🔥');
    setDone(true);
  };

  if (done) {
    const ns = streak(state);
    return (
      <div className="screen center-screen">
        <div className="celebrate">🔥</div>
        <h1>{ns.count}-day streak</h1>
        <p className="muted">Logged for {relDay(date).toLowerCase()}. See you tomorrow night.</p>
        <div className="stack mt">
          <button className="btn primary block" onClick={() => go('home')}>Back to dashboard</button>
          <button className="btn ghost block" onClick={() => { setDone(false); }}>Add something else</button>
        </div>
      </div>
    );
  }

  return (
    <div className="screen checkin">
      <header className="top">
        <div>
          <div className="muted small">Nightly check-in · 🔥 {s.count} day{s.count === 1 ? '' : 's'}</div>
          <h1>What did you spend {date === t ? 'today' : relDay(date).toLowerCase()}?</h1>
        </div>
      </header>

      <div className="daypick">
        {[0, -1, -2].map((n) => {
          const d = addDays(t, n);
          return (
            <button key={d} className={date === d ? 'on' : ''} onClick={() => setDate(d)}>
              {relDay(d)}{days.has(d) ? ' ✓' : ''}
            </button>
          );
        })}
        <input type="date" value={date} max={t} onChange={(e) => e.target.value && setDate(e.target.value)} aria-label="Pick another day" />
      </div>

      <div className="chat">
        <div className="bubble them">Hey! Anything today? Type it like <b>“35 bowling + drinks”</b> — one item at a time.</div>
        {logged.map((e) => (
          <div key={e.id} className="bubble me old">
            {fmt(e.amount)} · {catById(state, e.categoryId)?.emoji} {e.note || catById(state, e.categoryId)?.name}
          </div>
        ))}
        {pending.map((p) => (
          <div key={p.key} className="bubble me">
            <span>{fmt(p.amount)} · {catById(state, p.categoryId)?.emoji} {p.note || catById(state, p.categoryId)?.name}</span>
            <button className="x" aria-label="Remove" onClick={() => setPending((x) => x.filter((y) => y.key !== p.key))}>✕</button>
          </div>
        ))}
      </div>

      <div className="composer">
        <div className="compose-row">
          <input
            ref={input}
            className="quick"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && add()}
            placeholder="$35 bowling + drinks"
            autoComplete="off"
            enterKeyHint="done"
            aria-label="Amount and note"
          />
          <button className="btn primary add" onClick={add} disabled={!canAdd} aria-label="Add item">＋</button>
        </div>
        <div className="parse muted small">
          {parsed.amount != null ? (
            <>→ <b className="text">{fmt(parsed.amount)}</b> · {cat ? <>{catById(state, cat)?.emoji} {catById(state, cat)?.name}</> : <span className="yellow">tap a category</span>}{parsed.note ? ` · ${parsed.note}` : ''}</>
          ) : text ? <span className="yellow">Start with an amount, e.g. 12.50 lunch</span> : 'Category is guessed from your note — tap to change.'}
        </div>
        <div className="chips">
          {cats.map((c) => (
            <button key={c.id} className={`chip ${cat === c.id ? 'on' : ''}`} style={cat === c.id ? { borderColor: c.color, background: `${c.color}22` } : undefined} onClick={() => setPicked(c.id)}>
              <span>{c.emoji}</span>{c.name}
            </button>
          ))}
        </div>
        <div className="grid2">
          <button className="btn ghost big-btn" onClick={nothing}>🙌 Nothing {date === t ? 'today' : 'that day'}</button>
          <button className="btn primary big-btn" onClick={save} disabled={!pending.length && !canAdd}>
            Save{pending.length + (canAdd ? 1 : 0) ? ` ${pending.length + (canAdd ? 1 : 0)}` : ''} ✓
          </button>
        </div>
      </div>
    </div>
  );
}
