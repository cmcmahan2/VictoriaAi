'use client';

import { useState, useEffect } from 'react';

type Status = 'listed' | 'unlisted' | 'offer' | 'sold';

type Domain = {
  id: string;
  domain: string;
  registrar: string;
  costBasis: number;
  askPrice: number | null;
  marketplace: string;
  status: Status;
  soldPrice: number | null;
  addedAt: number;
  notes: string;
};

const STATUS_STYLES: Record<Status, string> = {
  unlisted: 'text-[#8b949e] bg-[#8b949e]/10 border-[#8b949e]/30',
  listed:   'text-blue-400 bg-blue-400/10 border-blue-400/30',
  offer:    'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  sold:     'text-green-400 bg-green-400/10 border-green-400/30',
};

const STATUS_LABELS: Record<Status, string> = {
  unlisted: 'Unlisted',
  listed:   'Listed',
  offer:    'Offer In',
  sold:     'Sold',
};

const GODADDY_URL = (d: string) =>
  `https://www.godaddy.com/domainsearch/find?domainToCheck=${encodeURIComponent(d)}`;
const AFTERNIC_URL = (d: string) =>
  `https://www.afternic.com/forsale/${encodeURIComponent(d)}`;

function usd(n: number) {
  return '$' + Math.round(n).toLocaleString();
}

const STORAGE_KEY = 'victoria_portfolio';

function load(): Domain[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function save(domains: Domain[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(domains));
}

const BLANK: Omit<Domain, 'id' | 'addedAt'> = {
  domain: '',
  registrar: 'GoDaddy',
  costBasis: 0,
  askPrice: null,
  marketplace: 'Afternic',
  status: 'listed',
  soldPrice: null,
  notes: '',
};

export default function PortfolioPage() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [editId, setEditId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => { setDomains(load()); }, []);

  function persist(next: Domain[]) {
    setDomains(next);
    save(next);
  }

  function openAdd() {
    setForm(BLANK);
    setEditId(null);
    setShowForm(true);
  }

  function openEdit(d: Domain) {
    setForm({ ...d });
    setEditId(d.id);
    setShowForm(true);
  }

  function submit() {
    if (!form.domain.trim()) return;
    if (editId) {
      persist(domains.map((d) => (d.id === editId ? { ...form, id: editId, addedAt: d.addedAt } : d)));
    } else {
      const next: Domain = { ...form, id: crypto.randomUUID(), addedAt: Date.now() };
      persist([next, ...domains]);
    }
    setShowForm(false);
  }

  function remove(id: string) {
    if (!confirm('Remove this domain from your portfolio?')) return;
    persist(domains.filter((d) => d.id !== id));
  }

  // Stats
  const active = domains.filter((d) => d.status !== 'sold');
  const sold = domains.filter((d) => d.status === 'sold');
  const totalInvested = domains.reduce((s, d) => s + d.costBasis, 0);
  const totalSaleValue = sold.reduce((s, d) => s + (d.soldPrice ?? 0), 0);
  const totalCostSold = sold.reduce((s, d) => s + d.costBasis, 0);
  const profit = totalSaleValue - totalCostSold;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e6edf3]">Portfolio</h1>
          <p className="text-sm text-[#8b949e] mt-0.5">{domains.length} domain{domains.length !== 1 ? 's' : ''} tracked</p>
        </div>
        <button
          onClick={openAdd}
          className="px-4 py-2 bg-[#238636] hover:bg-[#2ea043] text-white text-sm font-medium rounded-md transition-colors"
        >
          + Add Domain
        </button>
      </div>

      {/* Stats row */}
      {domains.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total Invested', value: usd(totalInvested) },
            { label: 'Active Listings', value: active.length },
            { label: 'Domains Sold', value: sold.length },
            { label: 'Total Profit', value: usd(profit), color: profit >= 0 ? 'text-green-400' : 'text-red-400' },
          ].map((s) => (
            <div key={s.label} className="bg-[#161b22] border border-[#30363d] rounded-lg p-3">
              <p className="text-xs text-[#6e7681] mb-1">{s.label}</p>
              <p className={`text-lg font-semibold ${s.color ?? 'text-[#e6edf3]'}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Add / Edit form */}
      {showForm && (
        <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-5 mb-6">
          <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">
            {editId ? 'Edit Domain' : 'Add Domain'}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[#8b949e]">Domain *</label>
              <input
                value={form.domain}
                onChange={(e) => setForm({ ...form, domain: e.target.value.toLowerCase().trim() })}
                placeholder="hbmhub.com"
                className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] placeholder-[#6e7681] outline-none focus:border-[#484f58]"
              />
            </div>
            <div>
              <label className="text-xs text-[#8b949e]">Registrar</label>
              <select
                value={form.registrar}
                onChange={(e) => setForm({ ...form, registrar: e.target.value })}
                className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] outline-none focus:border-[#484f58]"
              >
                {['GoDaddy', 'Namecheap', 'Dynadot', 'Name.com', 'Porkbun', 'Other'].map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-[#8b949e]">Cost Paid ($)</label>
              <input
                type="number"
                value={form.costBasis || ''}
                onChange={(e) => setForm({ ...form, costBasis: parseFloat(e.target.value) || 0 })}
                placeholder="4.99"
                className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] placeholder-[#6e7681] outline-none focus:border-[#484f58]"
              />
            </div>
            <div>
              <label className="text-xs text-[#8b949e]">Asking Price ($)</label>
              <input
                type="number"
                value={form.askPrice ?? ''}
                onChange={(e) => setForm({ ...form, askPrice: parseFloat(e.target.value) || null })}
                placeholder="500"
                className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] placeholder-[#6e7681] outline-none focus:border-[#484f58]"
              />
            </div>
            <div>
              <label className="text-xs text-[#8b949e]">Marketplace</label>
              <select
                value={form.marketplace}
                onChange={(e) => setForm({ ...form, marketplace: e.target.value })}
                className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] outline-none focus:border-[#484f58]"
              >
                {['Afternic', 'Sedo', 'Dan.com', 'Flippa', 'Self', 'None'].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-[#8b949e]">Status</label>
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as Status })}
                className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] outline-none focus:border-[#484f58]"
              >
                <option value="unlisted">Unlisted</option>
                <option value="listed">Listed</option>
                <option value="offer">Offer In</option>
                <option value="sold">Sold</option>
              </select>
            </div>
            {form.status === 'sold' && (
              <div>
                <label className="text-xs text-[#8b949e]">Sale Price ($)</label>
                <input
                  type="number"
                  value={form.soldPrice ?? ''}
                  onChange={(e) => setForm({ ...form, soldPrice: parseFloat(e.target.value) || null })}
                  placeholder="500"
                  className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] placeholder-[#6e7681] outline-none focus:border-[#484f58]"
                />
              </div>
            )}
            <div className="sm:col-span-2">
              <label className="text-xs text-[#8b949e]">Notes</label>
              <input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="HBM chip / memory space, target buyers: SK Hynix partners"
                className="w-full mt-1 px-3 py-2 bg-[#0d1117] border border-[#30363d] rounded text-sm text-[#e6edf3] placeholder-[#6e7681] outline-none focus:border-[#484f58]"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={submit}
              className="px-4 py-2 bg-[#238636] hover:bg-[#2ea043] text-white text-sm font-medium rounded transition-colors"
            >
              {editId ? 'Save Changes' : 'Add to Portfolio'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] text-sm rounded transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Domain list */}
      {domains.length === 0 && !showForm && (
        <div className="border border-dashed border-[#30363d] rounded-lg p-12 text-center">
          <p className="text-[#6e7681] text-sm">No domains yet — click Add Domain to track your first one.</p>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {domains.map((d) => {
          const roi = d.soldPrice ? ((d.soldPrice - d.costBasis) / d.costBasis * 100).toFixed(0) : null;
          const isExpanded = expandedId === d.id;
          return (
            <div
              key={d.id}
              className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 hover:border-[#484f58] transition-colors cursor-pointer"
              onClick={() => setExpandedId(isExpanded ? null : d.id)}
            >
              <div className="flex items-center gap-3 flex-wrap">
                <span className="font-mono font-semibold text-[#e6edf3]">{d.domain}</span>
                <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_STYLES[d.status]}`}>
                  {STATUS_LABELS[d.status]}
                </span>
                <span className="text-xs text-[#6e7681]">{d.marketplace}</span>
                <div className="flex-1" />
                <span className="text-sm text-[#8b949e]">
                  Paid <span className="text-[#e6edf3] font-medium">{usd(d.costBasis)}</span>
                </span>
                {d.askPrice && d.status !== 'sold' && (
                  <span className="text-sm text-[#8b949e]">
                    Ask <span className="text-[#e6edf3] font-medium">{usd(d.askPrice)}</span>
                  </span>
                )}
                {d.status === 'sold' && d.soldPrice && (
                  <span className="text-sm text-green-400 font-medium">
                    Sold {usd(d.soldPrice)} (+{roi}%)
                  </span>
                )}
              </div>

              {isExpanded && (
                <div
                  className="mt-3 pt-3 border-t border-[#30363d] space-y-3"
                  onClick={(e) => e.stopPropagation()}
                >
                  {d.notes && (
                    <p className="text-xs text-[#8b949e]">{d.notes}</p>
                  )}
                  <p className="text-xs text-[#6e7681]">
                    Registrar: <span className="text-[#e6edf3]">{d.registrar}</span>
                    {' · '}Added {new Date(d.addedAt).toLocaleDateString()}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <a
                      href={GODADDY_URL(d.domain)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs px-3 py-1 rounded bg-[#238636] hover:bg-[#2ea043] text-white transition-colors"
                    >
                      GoDaddy ↗
                    </a>
                    <a
                      href={AFTERNIC_URL(d.domain)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs px-3 py-1 rounded border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors"
                    >
                      Afternic ↗
                    </a>
                    <button
                      onClick={() => openEdit(d)}
                      className="text-xs px-3 py-1 rounded border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => remove(d.id)}
                      className="text-xs px-3 py-1 rounded border border-red-500/30 hover:border-red-500/60 text-red-400/70 hover:text-red-400 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
