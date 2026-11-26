'use client';
import { useMemo, useState } from 'react';
import { useStore } from '@/lib/store';
import { catById, spendCats } from '@/lib/calc';
import { ACCOUNT_HINT, buildRows, categorize, detectMapping, parseCSV, type ImportRow, type Mapping } from '@/lib/csv';
import { fmt, fmtDate, fmtMonth, monthBounds, monthKey, round2, shiftMonthKey, todayISO, uid } from '@/lib/format';
import type { AppState, BankAccount } from '@/lib/types';
import { Card, Empty, Seg } from '../ui';

export default function ImportScreen() {
  const { state, update, toast } = useStore();
  const [account, setAccount] = useState<BankAccount>('RBC');
  const [raw, setRaw] = useState<string[][] | null>(null);
  const [fileName, setFileName] = useState('');
  const [map, setMap] = useState<Mapping | null>(null);
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [showSkipped, setShowSkipped] = useState(false);
  const [paste, setPaste] = useState('');
  const [result, setResult] = useState<{ from: string; to: string; rows: ImportRow[] } | null>(null);

  const load = (text: string, name: string) => {
    const r = parseCSV(text);
    if (!r.length) { toast('That file looks empty'); return; }
    const m = detectMapping(r, account);
    setRaw(r); setFileName(name); setMap(m); setResult(null);
    setRows(buildRows(state, r, m, account));
  };
  const remap = (m: Mapping) => { setMap(m); if (raw) setRows(buildRows(state, raw, m, account)); };
  const setRow = (key: string, p: Partial<ImportRow>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

  const range = rows.length ? [rows[rows.length - 1].date, rows[0].date] as const : null;
  const counts = { import: rows.filter((r) => r.action === 'import').length, match: rows.filter((r) => r.action === 'match').length, skip: rows.filter((r) => r.action === 'skip').length };

  const commit = () => {
    if (!range) return;
    update((d) => {
      for (const r of rows) {
        if (r.action === 'skip') continue;
        const id = uid();
        d.entries.push({ id, date: r.date, amount: round2(r.amount), categoryId: r.categoryId, note: r.dupOfManual && r.action === 'match' ? r.dupOfManual.note : '', description: r.description, source: 'import', account, createdAt: Date.now(), matchedManualId: r.action === 'match' ? r.dupOfManual?.id : undefined });
        if (r.action === 'match' && r.dupOfManual) {
          const m = d.entries.find((e) => e.id === r.dupOfManual!.id);
          if (m) m.matchedImportId = id;
        }
      }
    });
    toast(`Imported ${counts.import + counts.match} transactions from ${account}`);
    setResult({ from: range[0], to: range[1], rows });
    setRaw(null); setRows([]); setMap(null); setPaste('');
  };

  const header = raw && map?.hasHeader ? raw[0] : raw?.[0]?.map((_, i) => `Column ${i + 1}`) ?? [];
  const visible = rows.filter((r) => showSkipped || r.action !== 'skip');

  return (
    <div className="screen">
      <header className="top"><h1>Import statements</h1></header>

      {!raw && (
        <Card title="1 · Pick the account">
          <Seg value={account} onChange={setAccount} options={[{ value: 'RBC', label: 'RBC' }, { value: 'Tangerine', label: 'Tangerine' }, { value: 'Amex', label: 'Amex' }]} />
          <p className="muted small mt">{ACCOUNT_HINT[account].help}</p>
          <label className="btn primary block mt filebtn">
            Choose CSV file
            <input type="file" accept=".csv,text/csv,text/plain" onChange={async (e) => { const f = e.target.files?.[0]; if (f) load(await f.text(), f.name); e.target.value = ''; }} />
          </label>
          <details className="mt">
            <summary className="muted small">…or paste CSV text</summary>
            <textarea rows={5} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder="Transaction Date,Description,Amount…" />
            <button className="btn ghost block" disabled={!paste.trim()} onClick={() => load(paste, 'pasted text')}>Read pasted CSV</button>
          </details>
        </Card>
      )}

      {raw && map && (
        <>
          <Card title={`2 · Review ${account} · ${fileName}`} action={<button className="link small" onClick={() => { setRaw(null); setRows([]); }}>Cancel</button>}>
            <p className="small">{rows.length} transactions{range ? ` · ${fmtDate(range[0])} – ${fmtDate(range[1])}` : ''}</p>
            <p className="muted small">{counts.import} new · {counts.match} match things you logged · {counts.skip} skipped (payments, transfers, already imported)</p>
            <details className="mt">
              <summary className="muted small">Columns & signs (auto-detected)</summary>
              <div className="grid2 mt">
                <label className="field"><span className="field-l">Date column</span>
                  <select value={map.date} onChange={(e) => remap({ ...map, date: +e.target.value })}>{header.map((h, i) => <option key={i} value={i}>{h}</option>)}</select></label>
                <label className="field"><span className="field-l">Amount column</span>
                  <select value={map.amount} onChange={(e) => remap({ ...map, amount: +e.target.value })}>
                    {map.debit >= 0 && <option value={-1}>Debit/credit columns</option>}
                    {header.map((h, i) => <option key={i} value={i}>{h}</option>)}
                  </select></label>
                <label className="field"><span className="field-l">Description</span>
                  <select value={map.desc[0] ?? 0} onChange={(e) => remap({ ...map, desc: [+e.target.value, ...map.desc.slice(1)] })}>{header.map((h, i) => <option key={i} value={i}>{h}</option>)}</select></label>
                <label className="field"><span className="field-l">Purchases are</span>
                  <select value={map.spendSign} onChange={(e) => remap({ ...map, spendSign: e.target.value as Mapping['spendSign'] })}>
                    <option value="negative">Negative (−)</option><option value="positive">Positive (+)</option>
                  </select></label>
                <label className="field"><span className="field-l">Date format</span>
                  <select value={map.dateOrder} onChange={(e) => remap({ ...map, dateOrder: e.target.value as Mapping['dateOrder'] })}>
                    <option value="mdy">Month/Day/Year</option><option value="dmy">Day/Month/Year</option>
                  </select></label>
                <label className="field"><span className="field-l">First row</span>
                  <select value={map.hasHeader ? 'h' : 'd'} onChange={(e) => remap({ ...map, hasHeader: e.target.value === 'h' })}>
                    <option value="h">Is a header</option><option value="d">Is data</option>
                  </select></label>
              </div>
            </details>
          </Card>

          {range && <ThoughtVsActual state={state} from={range[0]} to={range[1]} statement={rows} title="What I thought vs what I actually spent" />}

          <Card title="3 · Check categories" action={<button className="link small" onClick={() => setShowSkipped(!showSkipped)}>{showSkipped ? 'Hide' : 'Show'} skipped</button>}>
            <div className="list">
              {visible.map((r) => <ImportRowView key={r.key} r={r} setRow={setRow} />)}
              {!visible.length && <Empty>Nothing to import. Try “Show skipped” or check the column settings.</Empty>}
            </div>
          </Card>
          <div className="sticky-cta">
            <button className="btn primary block" disabled={!counts.import && !counts.match} onClick={commit}>Import {counts.import + counts.match} transactions</button>
          </div>
        </>
      )}

      {result && <ThoughtVsActual state={state} from={result.from} to={result.to} statement={result.rows} title="✓ Imported — thought vs actual" />}

      {!raw && <MonthlyCompare />}
      {!raw && <RulesEditor />}
    </div>
  );
}

function ImportRowView({ r, setRow }: { r: ImportRow; setRow: (k: string, p: Partial<ImportRow>) => void }) {
  const { state, update, toast } = useStore();
  const makeRule = () => {
    const guess = r.description.split('·')[0].toLowerCase().replace(/[#*\d]+/g, ' ').replace(/\s+/g, ' ').trim().split(' ').slice(0, 2).join(' ');
    const match = prompt(`Always categorize statement lines containing… as ${catById(state, r.categoryId)?.name}`, guess);
    if (!match?.trim()) return;
    update((d) => { d.rules.push({ id: uid(), match: match.trim().toLowerCase(), categoryId: r.categoryId }); });
    toast('Rule saved');
  };
  return (
    <div className={`irow ${r.action === 'skip' ? 'dim' : ''}`}>
      <div className="irow-top">
        <span className="item-m">
          <span className="item-t">{r.description}</span>
          <span className="item-s">{fmtDate(r.date)}{!r.isSpend && ' · credit/payment'}</span>
        </span>
        <span className={`item-a ${r.isSpend ? '' : 'green'}`}>{r.isSpend ? '' : '+'}{fmt(r.amount)}</span>
      </div>
      {r.dupOfManual && (
        <div className="dup">⚠ Possible duplicate of your log: {fmt(r.dupOfManual.amount)} on {fmtDate(r.dupOfManual.date)}{r.dupOfManual.note ? ` “${r.dupOfManual.note}”` : ''}</div>
      )}
      {r.alreadyImported && <div className="dup">Already imported earlier</div>}
      <div className="irow-ctl">
        <select value={r.categoryId} onChange={(e) => setRow(r.key, { categoryId: e.target.value, action: e.target.value === 'ignore' ? 'skip' : r.action === 'skip' ? 'import' : r.action })} aria-label="Category">
          {state.categories.map((c) => <option key={c.id} value={c.id}>{c.emoji} {c.name}</option>)}
        </select>
        <select value={r.action} onChange={(e) => setRow(r.key, { action: e.target.value as ImportRow['action'] })} aria-label="Action">
          <option value="import">Import</option>
          {r.dupOfManual && <option value="match">Match to my log</option>}
          <option value="skip">Skip</option>
        </select>
        <button className="link small" onClick={makeRule} title="Create rule">+ rule</button>
      </div>
    </div>
  );
}

function ThoughtVsActual({ state, from, to, statement, title }: { state: AppState; from: string; to: string; statement: ImportRow[]; title: string }) {
  const thought: Record<string, number> = {};
  for (const e of state.entries) if (e.source === 'manual' && e.date >= from && e.date <= to) thought[e.categoryId] = (thought[e.categoryId] ?? 0) + e.amount;
  const actual: Record<string, number> = {};
  for (const r of statement) if (r.isSpend && r.categoryId !== 'ignore') actual[r.categoryId] = (actual[r.categoryId] ?? 0) + r.amount;
  return <CompareTable state={state} thought={thought} actual={actual} title={title} sub={`${fmtDate(from)} – ${fmtDate(to)} · your logs vs this statement`} />;
}

function MonthlyCompare() {
  const { state } = useStore();
  const [off, setOff] = useState(0);
  const key = shiftMonthKey(monthKey(todayISO()), off);
  const [from, to] = monthBounds(key);
  const { thought, actual, hasImports } = useMemo(() => {
    const th: Record<string, number> = {}, ac: Record<string, number> = {};
    let hi = false;
    for (const e of state.entries) {
      if (e.date < from || e.date > to) continue;
      if (e.source === 'manual') th[e.categoryId] = (th[e.categoryId] ?? 0) + e.amount;
      if (e.source === 'import') hi = true;
      if (e.source === 'import' || !e.matchedImportId) ac[e.categoryId] = (ac[e.categoryId] ?? 0) + e.amount;
    }
    return { thought: th, actual: ac, hasImports: hi };
  }, [state, from, to]);
  return (
    <CompareTable
      state={state} thought={thought} actual={actual}
      title="Thought vs actual by month"
      sub={hasImports ? 'Actual = statement lines + anything you logged that isn’t on a statement (e.g. cash).' : 'Import a statement for this month to compare.'}
      nav={<span className="row"><button className="icon-btn" onClick={() => setOff(off - 1)} aria-label="Previous month">‹</button><b className="small">{fmtMonth(key)}</b><button className="icon-btn" disabled={off >= 0} onClick={() => setOff(off + 1)} aria-label="Next month">›</button></span>}
    />
  );
}

function CompareTable({ state, thought, actual, title, sub, nav }: { state: AppState; thought: Record<string, number>; actual: Record<string, number>; title: string; sub: string; nav?: React.ReactNode }) {
  const cats = spendCats(state).filter((c) => thought[c.id] || actual[c.id]);
  const tT = cats.reduce((a, c) => a + (thought[c.id] ?? 0), 0);
  const tA = cats.reduce((a, c) => a + (actual[c.id] ?? 0), 0);
  return (
    <Card title={title} action={nav}>
      <p className="muted small">{sub}</p>
      {cats.length ? (
        <table className="cmp">
          <thead><tr><th /><th>Thought</th><th>Actual</th><th>Diff</th></tr></thead>
          <tbody>
            {cats.map((c) => {
              const d = (actual[c.id] ?? 0) - (thought[c.id] ?? 0);
              return <tr key={c.id}><td>{c.emoji} {c.name}</td><td>{fmt(thought[c.id] ?? 0)}</td><td>{fmt(actual[c.id] ?? 0)}</td><td className={d > 0.5 ? 'red' : d < -0.5 ? 'green' : 'muted'}>{fmt(d, { sign: true })}</td></tr>;
            })}
            <tr className="tot"><td>Total</td><td>{fmt(tT)}</td><td>{fmt(tA)}</td><td className={tA - tT > 0.5 ? 'red' : 'muted'}>{fmt(tA - tT, { sign: true })}</td></tr>
          </tbody>
        </table>
      ) : <Empty>No spending in this range.</Empty>}
    </Card>
  );
}

function RulesEditor() {
  const { state, update } = useStore();
  const [match, setMatch] = useState('');
  const [cat, setCat] = useState('eating');
  const [test, setTest] = useState('');
  const [showAll, setShowAll] = useState(false);
  const rules = [...state.rules].reverse();
  const hit = test ? categorize(state.rules, test) : null;
  return (
    <Card title="Auto-categorize rules" action={<span className="muted small">{state.rules.length}</span>}>
      <p className="muted small">If a statement description contains the text, it gets that category. Longest match wins.</p>
      <form className="compose-row mt" onSubmit={(e) => { e.preventDefault(); if (!match.trim()) return; update((d) => { d.rules.push({ id: uid(), match: match.trim().toLowerCase(), categoryId: cat }); }); setMatch(''); }}>
        <input value={match} onChange={(e) => setMatch(e.target.value)} placeholder="e.g. golf town" aria-label="Text to match" />
        <select value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Category">{state.categories.map((c) => <option key={c.id} value={c.id}>{c.emoji} {c.name}</option>)}</select>
        <button className="btn ghost" type="submit">Add</button>
      </form>
      <input className="mt" value={test} onChange={(e) => setTest(e.target.value)} placeholder="Test: paste a statement description" aria-label="Test a description" />
      {test && <p className="small">→ {hit ? `${catById(state, hit)?.emoji} ${catById(state, hit)?.name}` : 'Other (no rule matched)'}</p>}
      <div className="rules mt">
        {(showAll ? rules : rules.slice(0, 12)).map((r) => (
          <span key={r.id} className="rule">
            <span>“{r.match}”</span><span className="muted">→ {catById(state, r.categoryId)?.emoji ?? '?'}</span>
            <select value={r.categoryId} onChange={(e) => update((d) => { const x = d.rules.find((y) => y.id === r.id); if (x) x.categoryId = e.target.value; })} aria-label={`Category for ${r.match}`}>
              {state.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <button className="x" onClick={() => update((d) => { d.rules = d.rules.filter((y) => y.id !== r.id); })} aria-label={`Delete rule ${r.match}`}>✕</button>
          </span>
        ))}
      </div>
      {rules.length > 12 && <button className="link small mt" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show fewer' : `Show all ${rules.length}`}</button>}
    </Card>
  );
}
