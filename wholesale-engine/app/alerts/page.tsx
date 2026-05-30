'use client';

import { useState, useEffect } from 'react';
import { Bell, Plus, Trash2, X } from 'lucide-react';
import Link from 'next/link';

type Alert = {
  id: number;
  email: string;
  market: string;
  minScore: number;
  maxPrice: number | null;
  frequency: string;
  active: number;
  createdAt: number;
};

const POPULAR_MARKETS = [
  'Memphis, TN', 'Detroit, MI', 'Houston, TX', 'Atlanta, GA',
  'Dallas, TX', 'Tampa, FL', 'Cleveland, OH', 'Indianapolis, IN',
  'Charlotte, NC', 'Columbus, OH', 'Jacksonville, FL', 'Birmingham, AL',
  'Baltimore, MD', 'Kansas City, MO', 'Austin, TX', 'Phoenix, AZ', 'St. Louis, MO',
];

export default function AlertsPage() {
  const [alertList, setAlertList] = useState<Alert[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dbError, setDbError] = useState(false);

  const [form, setForm] = useState({
    email: '', market: '', minScore: '75', maxPrice: '', frequency: 'daily',
  });

  useEffect(() => { void load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch('/api/alerts');
      const data = (await res.json()) as { ok: boolean; alerts: Alert[] };
      if (data.ok) setAlertList(data.alerts);
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    if (!form.email.trim() || !form.market.trim()) return;
    setSaving(true);
    setDbError(false);
    try {
      const res = await fetch('/api/alerts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: form.email, market: form.market,
          minScore: Number(form.minScore),
          maxPrice: form.maxPrice ? Number(form.maxPrice) : undefined,
          frequency: form.frequency,
        }),
      });
      const data = (await res.json()) as { ok: boolean; error?: string };
      if (data.ok) {
        setForm({ email: '', market: '', minScore: '75', maxPrice: '', frequency: 'daily' });
        setShowForm(false);
        void load();
      } else if (data.error?.includes('Database not configured')) {
        setDbError(true);
      }
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    await fetch(`/api/alerts?id=${id}`, { method: 'DELETE' });
    void load();
  }

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <header className="border-b border-gray-800 bg-[#161b22]">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/search" className="font-bold text-lg text-gray-100">Wholesale Engine</Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/search" className="text-gray-500 hover:text-gray-300">Search</Link>
              <Link href="/deals" className="text-gray-500 hover:text-gray-300">Pipeline</Link>
              <Link href="/buyers" className="text-gray-500 hover:text-gray-300">Buyers</Link>
              <Link href="/alerts" className="text-green-400 font-medium">Alerts</Link>
            </nav>
          </div>
          <button onClick={() => setShowForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-semibold transition-colors">
            <Plus className="w-4 h-4" /> New Alert
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-2">
          <Bell className="w-6 h-6 text-green-400" />
          <h1 className="text-xl font-bold">Deal Alerts</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          Get notified when new deals hit your target markets.
          {' '}<span className="text-yellow-500">Requires RESEND_API_KEY + DB_PATH in .env for email delivery.</span>
        </p>

        {dbError && (
          <div className="mb-4 p-3 bg-yellow-900/20 border border-yellow-700/50 rounded text-yellow-400 text-sm">
            Database not configured — add <code>DB_PATH=./wholesale.db</code> to your .env file to save alerts.
          </div>
        )}

        {showForm && (
          <div className="bg-[#161b22] border border-gray-700 rounded-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-200">New Alert</h2>
              <button onClick={() => setShowForm(false)}><X className="w-4 h-4 text-gray-500" /></button>
            </div>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="col-span-2">
                <label className="text-xs text-gray-500 mb-1 block">Email *</label>
                <input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500"
                  placeholder="you@example.com" type="email" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Market *</label>
                <select value={form.market} onChange={e => setForm(f => ({ ...f, market: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500">
                  <option value="">Select market…</option>
                  {POPULAR_MARKETS.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Min Deal Score</label>
                <select value={form.minScore} onChange={e => setForm(f => ({ ...f, minScore: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500">
                  <option value="75">75+ (Hot Deals only)</option>
                  <option value="50">50+ (Potential deals)</option>
                  <option value="25">25+ (Any deal)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Max Price</label>
                <input type="number" value={form.maxPrice} onChange={e => setForm(f => ({ ...f, maxPrice: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500"
                  placeholder="No limit" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Frequency</label>
                <select value={form.frequency} onChange={e => setForm(f => ({ ...f, frequency: e.target.value }))}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-green-500">
                  <option value="instant">Instant</option>
                  <option value="daily">Daily digest</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200">Cancel</button>
              <button onClick={() => void save()} disabled={saving || !form.email.trim() || !form.market}
                className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-semibold transition-colors">
                {saving ? 'Saving…' : 'Create Alert'}
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="text-center py-16 text-gray-500">Loading…</div>
        ) : alertList.length === 0 ? (
          <div className="text-center py-16">
            <Bell className="w-10 h-10 mx-auto mb-3 text-gray-700" />
            <p className="text-gray-500">No alerts yet. Create one to get notified of new deals.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alertList.map(a => (
              <div key={a.id} className="bg-[#161b22] border border-gray-800 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-medium text-gray-200">{a.market}</span>
                    <span className={`text-xs px-2 py-0.5 rounded border ${a.active ? 'text-green-400 bg-green-400/10 border-green-400/30' : 'text-gray-500 bg-gray-800 border-gray-700'}`}>
                      {a.active ? 'Active' : 'Paused'}
                    </span>
                    <span className="text-xs text-gray-500">{a.frequency}</span>
                  </div>
                  <div className="text-xs text-gray-500 flex gap-4">
                    <span>{a.email}</span>
                    <span>Min score: {a.minScore}</span>
                    {a.maxPrice && <span>Max: ${a.maxPrice.toLocaleString()}</span>}
                  </div>
                </div>
                <button onClick={() => void remove(a.id)} className="p-1.5 text-gray-600 hover:text-red-400 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
