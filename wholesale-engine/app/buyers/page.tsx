'use client';

import { useState, useEffect } from 'react';
import { Users, Plus, Trash2, Phone, Mail, MapPin, DollarSign, X } from 'lucide-react';
import { cn, formatCurrency } from '@/lib/utils';
import Link from 'next/link';

type Buyer = {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  markets: string;
  maxPrice: number | null;
  propertyTypes: string;
  notes: string | null;
  createdAt: number;
};

const PROPERTY_TYPES = ['SFR', 'MFR', 'Condo', 'Townhouse', 'Land'];

const POPULAR_MARKETS = [
  'Memphis, TN', 'Detroit, MI', 'Cleveland, OH', 'Baltimore, MD',
  'Kansas City, MO', 'Indianapolis, IN', 'Birmingham, AL', 'St. Louis, MO',
];

export default function BuyersPage() {
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    name: '', email: '', phone: '', notes: '',
    markets: [] as string[], maxPrice: '', propertyTypes: [] as string[],
    customMarket: '',
  });

  useEffect(() => { void load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch('/api/buyers');
      const data = (await res.json()) as { ok: boolean; buyers: Buyer[] };
      if (data.ok) setBuyers(data.buyers);
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const res = await fetch('/api/buyers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name, email: form.email || undefined,
          phone: form.phone || undefined,
          markets: form.markets,
          maxPrice: form.maxPrice ? Number(form.maxPrice) : undefined,
          propertyTypes: form.propertyTypes,
          notes: form.notes || undefined,
        }),
      });
      const data = (await res.json()) as { ok: boolean };
      if (data.ok) {
        setForm({ name: '', email: '', phone: '', notes: '', markets: [], maxPrice: '', propertyTypes: [], customMarket: '' });
        setShowForm(false);
        void load();
      }
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    await fetch(`/api/buyers?id=${id}`, { method: 'DELETE' });
    void load();
  }

  const addMarket = (m: string) => {
    if (!m.trim() || form.markets.includes(m)) return;
    setForm(f => ({ ...f, markets: [...f.markets, m], customMarket: '' }));
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <header className="border-b border-gray-800 bg-[#161b22]">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/search" className="flex items-center gap-2 text-gray-400 hover:text-gray-200">
              <span className="font-bold text-lg text-gray-100">Wholesale Engine</span>
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/search" className="text-gray-500 hover:text-gray-300">Search</Link>
              <Link href="/buyers" className="text-green-400 font-medium">Buyers</Link>
              <Link href="/alerts" className="text-gray-500 hover:text-gray-300">Alerts</Link>
            </nav>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-semibold transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Buyer
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-6">
          <Users className="w-6 h-6 text-green-400" />
          <h1 className="text-xl font-bold">Cash Buyer List</h1>
          <span className="text-sm text-gray-500">({buyers.length} buyers)</span>
        </div>

        {/* Add Buyer Form */}
        {showForm && (
          <div className="bg-[#161b22] border border-gray-700 rounded-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-200">New Buyer</h2>
              <button onClick={() => setShowForm(false)}><X className="w-4 h-4 text-gray-500" /></button>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Name *</label>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500" placeholder="John Smith" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Email</label>
                <input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500" placeholder="john@example.com" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Phone</label>
                <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500" placeholder="(555) 555-5555" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Max Price</label>
                <input type="number" value={form.maxPrice} onChange={e => setForm(f => ({ ...f, maxPrice: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500" placeholder="250000" />
              </div>
            </div>

            {/* Target Markets */}
            <div className="mb-4">
              <label className="text-xs text-gray-500 mb-2 block">Target Markets</label>
              <div className="flex flex-wrap gap-2 mb-2">
                {POPULAR_MARKETS.map(m => (
                  <button key={m} onClick={() => addMarket(m)}
                    className={cn('text-xs px-2 py-1 rounded border transition-colors',
                      form.markets.includes(m) ? 'border-green-500 bg-green-500/10 text-green-400' : 'border-gray-700 text-gray-500 hover:border-gray-500')}>
                    {m}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <input value={form.customMarket} onChange={e => setForm(f => ({ ...f, customMarket: e.target.value }))}
                  onKeyDown={e => e.key === 'Enter' && addMarket(form.customMarket)}
                  className="flex-1 bg-[#0d1117] border border-gray-700 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-green-500"
                  placeholder="Custom market (e.g. Houston, TX)" />
                <button onClick={() => addMarket(form.customMarket)}
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm">Add</button>
              </div>
              {form.markets.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {form.markets.map(m => (
                    <span key={m} className="flex items-center gap-1 text-xs px-2 py-0.5 bg-green-400/10 border border-green-400/30 text-green-400 rounded">
                      {m}
                      <button onClick={() => setForm(f => ({ ...f, markets: f.markets.filter(x => x !== m) }))}><X className="w-3 h-3" /></button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Property Types */}
            <div className="mb-4">
              <label className="text-xs text-gray-500 mb-2 block">Property Types</label>
              <div className="flex gap-2 flex-wrap">
                {PROPERTY_TYPES.map(t => (
                  <label key={t} className="flex items-center gap-1.5 cursor-pointer">
                    <input type="checkbox" checked={form.propertyTypes.includes(t)}
                      onChange={e => setForm(f => ({ ...f, propertyTypes: e.target.checked ? [...f.propertyTypes, t] : f.propertyTypes.filter(x => x !== t) }))}
                      className="accent-green-500" />
                    <span className="text-sm text-gray-400">{t}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <label className="text-xs text-gray-500 mb-1 block">Notes</label>
              <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500" rows={2} placeholder="Prefers 3bd SFRs, cash closes in 14 days..." />
            </div>

            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200">Cancel</button>
              <button onClick={() => void save()} disabled={saving || !form.name.trim()}
                className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-semibold transition-colors">
                {saving ? 'Saving…' : 'Save Buyer'}
              </button>
            </div>
          </div>
        )}

        {/* Buyers table */}
        {loading ? (
          <div className="text-center py-16 text-gray-500">Loading…</div>
        ) : buyers.length === 0 ? (
          <div className="text-center py-16">
            <Users className="w-10 h-10 mx-auto mb-3 text-gray-700" />
            <p className="text-gray-500">No buyers yet. Add your first cash buyer.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {buyers.map(b => {
              const bMarkets = JSON.parse(b.markets) as string[];
              const bTypes = JSON.parse(b.propertyTypes) as string[];
              return (
                <div key={b.id} className="bg-[#161b22] border border-gray-800 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="font-semibold text-gray-200">{b.name}</span>
                        {b.maxPrice && (
                          <span className="text-xs px-2 py-0.5 bg-green-400/10 border border-green-400/30 text-green-400 rounded">
                            Max {formatCurrency(b.maxPrice)}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mb-2">
                        {b.email && <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{b.email}</span>}
                        {b.phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{b.phone}</span>}
                      </div>
                      {bMarkets.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-2">
                          {bMarkets.map(m => (
                            <span key={m} className="flex items-center gap-1 text-xs px-1.5 py-0.5 bg-blue-400/10 border border-blue-400/20 text-blue-400 rounded">
                              <MapPin className="w-2.5 h-2.5" />{m}
                            </span>
                          ))}
                        </div>
                      )}
                      {bTypes.length > 0 && (
                        <div className="flex gap-1">
                          {bTypes.map(t => <span key={t} className="text-xs px-1.5 py-0.5 bg-gray-800 text-gray-400 rounded">{t}</span>)}
                        </div>
                      )}
                      {b.notes && <p className="text-xs text-gray-600 mt-2 italic">{b.notes}</p>}
                    </div>
                    <div className="flex items-center gap-2">
                      <Link href={`/search?buyerMatch=${b.id}&markets=${encodeURIComponent(bMarkets[0] ?? '')}`}
                        className="text-xs px-3 py-1.5 bg-green-600/20 border border-green-600/40 text-green-400 hover:bg-green-600/30 rounded transition-colors">
                        <DollarSign className="w-3 h-3 inline mr-1" />Match Deals
                      </Link>
                      <button onClick={() => void remove(b.id)} className="p-1.5 text-gray-600 hover:text-red-400 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
