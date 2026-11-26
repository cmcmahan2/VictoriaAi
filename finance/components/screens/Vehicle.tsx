'use client';
import { useState } from 'react';
import { useStore } from '@/lib/store';
import { weekRange } from '@/lib/calc';
import { addDays, fmt, fmtDate, parseISO, pct, round2, todayISO, uid } from '@/lib/format';
import { downloadText, toCSV } from '@/lib/csv';
import type { AppState, Fillup, Trip } from '@/lib/types';
import { Card, Empty, Field, NumInput, Seg, Sheet, Stat } from '../ui';

export function lastOdometer(s: AppState): number | null {
  const vals = [...s.trips.map((t) => t.odoEnd ?? 0), ...s.fillups.map((f) => f.odometer ?? 0)].filter((v) => v > 0);
  return vals.length ? Math.max(...vals) : null;
}

export function yearStats(s: AppState, year: number) {
  const inY = (d: string) => parseISO(d).getFullYear() === year;
  const trips = s.trips.filter((t) => inY(t.date));
  const fills = s.fillups.filter((f) => inY(f.date));
  const businessKm = trips.filter((t) => t.business).reduce((a, t) => a + t.km, 0);
  const personalTripKm = trips.filter((t) => !t.business).reduce((a, t) => a + t.km, 0);
  const readings = [...trips.flatMap((t) => [t.odoStart, t.odoEnd]), ...fills.map((f) => f.odometer)].filter((v): v is number => !!v && v > 0);
  const startOdo = s.settings.odometerYearStart[String(year)] ?? (readings.length ? Math.min(...readings) : null);
  const endOdo = readings.length ? Math.max(...readings) : null;
  const odoKm = startOdo != null && endOdo != null ? endOdo - startOdo : 0;
  const totalKm = Math.max(odoKm, businessKm + personalTripKm);
  return { trips, fills, businessKm, totalKm, startOdo, endOdo, pct: totalKm > 0 ? businessKm / totalKm : 0, fuel: fills.reduce((a, f) => a + f.amount, 0), litres: fills.reduce((a, f) => a + f.litres, 0) };
}

export default function Vehicle() {
  const { state, update, toast } = useStore();
  const [tab, setTab] = useState<'week' | 'trips' | 'fuel'>('week');
  const [tripOpen, setTripOpen] = useState<Trip | 'new' | null>(null);
  const [fillOpen, setFillOpen] = useState<Fillup | 'new' | null>(null);
  const [wOff, setWOff] = useState(0);
  const [printing, setPrinting] = useState(false);
  const year = new Date().getFullYear();
  const ys = yearStats(state, year);
  const [wFrom, wTo] = weekRange(addDays(todayISO(), wOff * 7));
  const wTrips = state.trips.filter((t) => t.date >= wFrom && t.date <= wTo);
  const wFills = state.fillups.filter((f) => f.date >= wFrom && f.date <= wTo);
  const abby = state.settings.abbyTrip;

  const repeatAbby = () => {
    const last = [...state.trips].filter((t) => t.to === abby.to || t.from === abby.to).sort((a, b) => b.createdAt - a.createdAt)[0];
    const km = last?.km ?? abby.km;
    const odo = lastOdometer(state);
    update((d) => {
      d.trips.push({
        id: uid(), date: todayISO(), from: last?.from ?? abby.from, to: last?.to ?? abby.to, purpose: last?.purpose ?? abby.purpose,
        km, odoStart: odo ?? undefined, odoEnd: odo != null ? odo + km : undefined, business: true, createdAt: Date.now(),
      });
    });
    toast(`Trip logged: ${abby.to} · ${km} km`);
  };

  const exportCSV = () => {
    const rows: (string | number | undefined)[][] = [['Type', 'Date', 'From', 'To', 'Purpose', 'Business', 'Odometer start', 'Odometer end', 'Km', 'Station', 'Litres', 'Amount (CAD)']];
    for (const t of [...state.trips].sort((a, b) => (a.date < b.date ? -1 : 1))) rows.push(['Trip', t.date, t.from, t.to, t.purpose, t.business ? 'Yes' : 'No', t.odoStart, t.odoEnd, t.km, '', '', '']);
    for (const f of [...state.fillups].sort((a, b) => (a.date < b.date ? -1 : 1))) rows.push(['Fill-up', f.date, '', '', '', '', '', f.odometer, '', f.station, f.litres, f.amount.toFixed(2)]);
    downloadText(`vehicle-log-${year}.csv`, toCSV(rows));
  };

  const print = () => {
    setPrinting(true);
    setTimeout(() => { window.print(); setTimeout(() => setPrinting(false), 300); }, 100);
  };

  return (
    <div className="screen">
      <header className="top">
        <h1>Work vehicle</h1>
        <span className="muted small">{state.settings.vehicleName}</span>
      </header>

      <button className="cta" onClick={repeatAbby}>
        <span className="cta-e">🚗</span>
        <span><b>Log {abby.to} trip</b><span className="muted small">One tap · {abby.from} → {abby.to} · {abby.km} km</span></span>
        <span className="cta-a">＋</span>
      </button>
      <div className="grid2">
        <button className="btn ghost" onClick={() => setTripOpen('new')}>+ Other trip</button>
        <button className="btn ghost" onClick={() => setFillOpen('new')}>⛽ Fill-up</button>
      </div>

      <Card title={`${year} business use`}>
        <div className="grid2">
          <Stat label="Business use" value={pct(ys.pct, 1)} tone="green" sub={`${ys.businessKm.toFixed(0)} of ${ys.totalKm.toFixed(0)} km`} />
          <Stat label="Fuel YTD" value={fmt(ys.fuel)} sub={`${ys.fills.length} fill-ups · ${ys.litres.toFixed(1)} L`} />
        </div>
        {!state.settings.odometerYearStart[String(year)] && <p className="muted small mt">Tip: set your Jan 1 odometer in Settings so total km (and business %) are exact.</p>}
        <div className="grid2 mt">
          <button className="btn ghost" onClick={exportCSV}>Export CSV</button>
          <button className="btn ghost" onClick={print}>Year-end logbook</button>
        </div>
      </Card>

      <Seg value={tab} onChange={setTab} options={[{ value: 'week', label: 'Weekly' }, { value: 'trips', label: 'Trips' }, { value: 'fuel', label: 'Fill-ups' }]} />

      {tab === 'week' && (
        <Card>
          <div className="period">
            <button className="icon-btn" onClick={() => setWOff(wOff - 1)} aria-label="Previous week">‹</button>
            <div className="center"><b>{fmtDate(wFrom).replace(/, \d{4}/, '')} – {fmtDate(wTo)}</b></div>
            <button className="icon-btn" disabled={wOff >= 0} onClick={() => setWOff(wOff + 1)} aria-label="Next week">›</button>
          </div>
          <div className="grid4">
            <Stat label="Trips" value={wTrips.length} />
            <Stat label="Km" value={wTrips.reduce((a, t) => a + t.km, 0).toFixed(0)} />
            <Stat label="Fill-ups" value={wFills.length} />
            <Stat label="Fuel" value={fmt(wFills.reduce((a, f) => a + f.amount, 0), { whole: true })} />
          </div>
          <TripList trips={wTrips} onEdit={setTripOpen} />
          <FillList fills={wFills} onEdit={setFillOpen} />
          {!wTrips.length && !wFills.length && <Empty>Nothing logged this week.</Empty>}
        </Card>
      )}
      {tab === 'trips' && <Card>{state.trips.length ? <TripList trips={state.trips} onEdit={setTripOpen} /> : <Empty>No trips yet.</Empty>}</Card>}
      {tab === 'fuel' && <Card>{state.fillups.length ? <FillList fills={state.fillups} onEdit={setFillOpen} /> : <Empty>No fill-ups yet.</Empty>}</Card>}

      {tripOpen && <TripSheet trip={tripOpen} onClose={() => setTripOpen(null)} />}
      {fillOpen && <FillSheet fill={fillOpen} onClose={() => setFillOpen(null)} />}
      {printing && <Logbook year={year} />}
    </div>
  );
}

function TripList({ trips, onEdit }: { trips: Trip[]; onEdit: (t: Trip) => void }) {
  if (!trips.length) return null;
  return (
    <div className="list mt">
      {[...trips].sort((a, b) => (a.date < b.date ? 1 : -1)).map((t) => (
        <button key={t.id} className="item" onClick={() => onEdit(t)}>
          <span className="item-e">{t.business ? '💼' : '🏠'}</span>
          <span className="item-m"><span className="item-t">{t.from} → {t.to}</span><span className="item-s">{fmtDate(t.date)} · {t.purpose}{t.odoStart ? ` · ${t.odoStart}–${t.odoEnd}` : ''}</span></span>
          <span className="item-a">{t.km.toFixed(0)} km</span>
        </button>
      ))}
    </div>
  );
}

function FillList({ fills, onEdit }: { fills: Fillup[]; onEdit: (f: Fillup) => void }) {
  if (!fills.length) return null;
  return (
    <div className="list mt">
      {[...fills].sort((a, b) => (a.date < b.date ? 1 : -1)).map((f) => (
        <button key={f.id} className="item" onClick={() => onEdit(f)}>
          <span className="item-e">⛽</span>
          <span className="item-m"><span className="item-t">{f.station || 'Fill-up'}</span><span className="item-s">{fmtDate(f.date)} · {f.litres.toFixed(1)} L{f.litres ? ` · ${fmt(f.amount / f.litres)}/L` : ''}{f.odometer ? ` · ${f.odometer} km` : ''}</span></span>
          <span className="item-a">{fmt(f.amount)}</span>
        </button>
      ))}
    </div>
  );
}

function TripSheet({ trip, onClose }: { trip: Trip | 'new'; onClose: () => void }) {
  const { state, update, toast } = useStore();
  const isNew = trip === 'new';
  const odo = lastOdometer(state);
  const a = state.settings.abbyTrip;
  const [f, setF] = useState<Omit<Trip, 'id' | 'createdAt'>>(isNew ? { date: todayISO(), from: a.from, to: '', purpose: '', km: NaN, odoStart: odo ?? undefined, odoEnd: undefined, business: true } : { ...trip });
  const set = (p: Partial<typeof f>) => setF((x) => {
    const n = { ...x, ...p };
    if (('odoStart' in p || 'odoEnd' in p) && n.odoStart && n.odoEnd && n.odoEnd > n.odoStart) n.km = n.odoEnd - n.odoStart;
    return n;
  });
  const ok = f.km > 0 && f.to.trim();
  const save = () => {
    if (!ok) return;
    update((d) => {
      if (isNew) d.trips.push({ ...f, km: round2(f.km), id: uid(), createdAt: Date.now() });
      else { const t = d.trips.find((x) => x.id === trip.id); if (t) Object.assign(t, f); }
    });
    toast('Trip saved');
    onClose();
  };
  return (
    <Sheet open onClose={onClose} title={isNew ? 'Log trip' : 'Edit trip'} footer={
      <div className="grid2">
        {!isNew ? <button className="btn danger" onClick={() => { if (confirm('Delete trip?')) { update((d) => { d.trips = d.trips.filter((x) => x.id !== trip.id); }); onClose(); } }}>Delete</button> : <button className="btn ghost" onClick={onClose}>Cancel</button>}
        <button className="btn primary" onClick={save} disabled={!ok}>Save</button>
      </div>
    }>
      <Field label="Date"><input type="date" value={f.date} onChange={(e) => set({ date: e.target.value })} /></Field>
      <div className="grid2">
        <Field label="From"><input value={f.from} onChange={(e) => set({ from: e.target.value })} /></Field>
        <Field label="To"><input value={f.to} onChange={(e) => set({ to: e.target.value })} placeholder="Client site" /></Field>
      </div>
      <Field label="Purpose"><input value={f.purpose} onChange={(e) => set({ purpose: e.target.value })} placeholder="Site visit, delivery…" /></Field>
      <div className="grid2">
        <Field label="Odometer start"><NumInput prefix="" value={f.odoStart ?? NaN} onChange={(n) => set({ odoStart: Number.isFinite(n) ? n : undefined })} aria-label="Odometer start" /></Field>
        <Field label="Odometer end"><NumInput prefix="" value={f.odoEnd ?? NaN} onChange={(n) => set({ odoEnd: Number.isFinite(n) ? n : undefined })} aria-label="Odometer end" /></Field>
      </div>
      <Field label="Distance (km)" hint="Filled in from the odometer, or type it."><NumInput prefix="" value={f.km} onChange={(n) => set({ km: n })} aria-label="Kilometres" /></Field>
      <Seg value={f.business ? 'b' : 'p'} onChange={(v) => set({ business: v === 'b' })} options={[{ value: 'b', label: '💼 Business' }, { value: 'p', label: '🏠 Personal' }]} />
    </Sheet>
  );
}

function FillSheet({ fill, onClose }: { fill: Fillup | 'new'; onClose: () => void }) {
  const { state, update, toast } = useStore();
  const isNew = fill === 'new';
  const [f, setF] = useState<Omit<Fillup, 'id' | 'createdAt' | 'entryId'>>(isNew ? { date: todayISO(), station: '', litres: NaN, amount: NaN, odometer: lastOdometer(state) ?? undefined } : { ...fill });
  const [asSpend, setAsSpend] = useState(isNew ? true : !!fill.entryId);
  const set = (p: Partial<typeof f>) => setF((x) => ({ ...x, ...p }));
  const ok = f.amount > 0;
  const save = () => {
    if (!ok) return;
    update((d) => {
      let rec: Fillup;
      if (isNew) { rec = { ...f, litres: f.litres || 0, id: uid(), createdAt: Date.now() }; d.fillups.push(rec); }
      else { rec = d.fillups.find((x) => x.id === fill.id)!; Object.assign(rec, f, { litres: f.litres || 0 }); }
      const existing = rec.entryId ? d.entries.find((e) => e.id === rec.entryId) : undefined;
      if (asSpend) {
        if (existing) Object.assign(existing, { date: rec.date, amount: round2(rec.amount), note: `Fill-up${rec.station ? ' · ' + rec.station : ''}` });
        else {
          const id = uid();
          d.entries.push({ id, date: rec.date, amount: round2(rec.amount), categoryId: 'gas', note: `Fill-up${rec.station ? ' · ' + rec.station : ''}`, source: 'manual', fillupId: rec.id, createdAt: Date.now() });
          rec.entryId = id;
        }
      } else if (existing) {
        d.entries = d.entries.filter((e) => e.id !== existing.id);
        rec.entryId = undefined;
      }
    });
    toast('Fill-up saved');
    onClose();
  };
  return (
    <Sheet open onClose={onClose} title={isNew ? 'Log fill-up' : 'Edit fill-up'} footer={
      <div className="grid2">
        {!isNew ? <button className="btn danger" onClick={() => { if (confirm('Delete fill-up?')) { update((d) => { d.fillups = d.fillups.filter((x) => x.id !== fill.id); if (fill.entryId) d.entries = d.entries.filter((e) => e.id !== fill.entryId); }); onClose(); } }}>Delete</button> : <button className="btn ghost" onClick={onClose}>Cancel</button>}
        <button className="btn primary" onClick={save} disabled={!ok}>Save</button>
      </div>
    }>
      <Field label="Date"><input type="date" value={f.date} onChange={(e) => set({ date: e.target.value })} /></Field>
      <Field label="Station"><input value={f.station} onChange={(e) => set({ station: e.target.value })} placeholder="Costco Abbotsford" /></Field>
      <div className="grid2">
        <Field label="Total $"><NumInput value={f.amount} onChange={(n) => set({ amount: n })} aria-label="Total cost" /></Field>
        <Field label="Litres"><NumInput prefix="" value={f.litres} onChange={(n) => set({ litres: n })} aria-label="Litres" /></Field>
      </div>
      <Field label="Odometer"><NumInput prefix="" value={f.odometer ?? NaN} onChange={(n) => set({ odometer: Number.isFinite(n) ? n : undefined })} aria-label="Odometer" /></Field>
      <label className="row-check"><input type="checkbox" checked={asSpend} onChange={(e) => setAsSpend(e.target.checked)} /> Also log as Gas spending</label>
    </Sheet>
  );
}

/** Print-only CRA-style logbook. */
function Logbook({ year }: { year: number }) {
  const { state } = useStore();
  const ys = yearStats(state, year);
  const trips = [...ys.trips].sort((a, b) => (a.date < b.date ? -1 : 1));
  const fills = [...ys.fills].sort((a, b) => (a.date < b.date ? -1 : 1));
  return (
    <div className="print-only logbook">
      <h1>Vehicle logbook — {year}</h1>
      <p>Vehicle: {state.settings.vehicleName}</p>
      <table>
        <tbody>
          <tr><td>Odometer, start of year</td><td>{ys.startOdo ?? '—'} km</td></tr>
          <tr><td>Odometer, latest reading</td><td>{ys.endOdo ?? '—'} km</td></tr>
          <tr><td>Total km driven</td><td>{ys.totalKm.toFixed(0)} km</td></tr>
          <tr><td>Business km</td><td>{ys.businessKm.toFixed(0)} km</td></tr>
          <tr><td>Business-use percentage</td><td>{pct(ys.pct, 1)}</td></tr>
          <tr><td>Fuel</td><td>{fmt(ys.fuel)} ({ys.litres.toFixed(1)} L, {ys.fills.length} fill-ups)</td></tr>
        </tbody>
      </table>
      <h2>Trips</h2>
      <table>
        <thead><tr><th>Date</th><th>From</th><th>To</th><th>Purpose</th><th>Odo start</th><th>Odo end</th><th>Km</th><th>Type</th></tr></thead>
        <tbody>
          {trips.map((t) => <tr key={t.id}><td>{fmtDate(t.date)}</td><td>{t.from}</td><td>{t.to}</td><td>{t.purpose}</td><td>{t.odoStart ?? ''}</td><td>{t.odoEnd ?? ''}</td><td>{t.km.toFixed(0)}</td><td>{t.business ? 'Business' : 'Personal'}</td></tr>)}
        </tbody>
      </table>
      <h2>Fill-ups</h2>
      <table>
        <thead><tr><th>Date</th><th>Station</th><th>Litres</th><th>Amount</th><th>Odometer</th></tr></thead>
        <tbody>
          {fills.map((f) => <tr key={f.id}><td>{fmtDate(f.date)}</td><td>{f.station}</td><td>{f.litres.toFixed(1)}</td><td>{fmt(f.amount)}</td><td>{f.odometer ?? ''}</td></tr>)}
        </tbody>
      </table>
      <p className="small">Generated {fmtDate(todayISO())}. Keep fuel receipts with this log.</p>
    </div>
  );
}
