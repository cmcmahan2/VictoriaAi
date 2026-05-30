'use client';

import { useState, useEffect } from 'react';
import {
  Briefcase, Trash2, ExternalLink, FileText, FileSignature, Download,
  ChevronDown, ChevronUp, AlertTriangle, X,
} from 'lucide-react';
import Link from 'next/link';
import { cn, formatCurrency } from '@/lib/utils';
import { PURCHASE_AGREEMENT_TEMPLATE, ASSIGNMENT_OF_CONTRACT_TEMPLATE } from '@/lib/templates';

type Deal = {
  id: number;
  externalId: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  price: number;
  propertyType: string | null;
  wholesaleScore: number | null;
  arvEstimate: number | null;
  mao: number | null;
  projectedProfit: number | null;
  source: string | null;
  listingUrl: string | null;
  status: string;
  notes: string | null;
  createdAt: number;
  updatedAt: number;
};

// Ordered pipeline stages. 'dead' is shown last as a parking lot.
const STAGES: { key: string; label: string; color: string }[] = [
  { key: 'lead', label: 'Lead', color: 'border-gray-600 text-gray-300' },
  { key: 'contacted', label: 'Contacted', color: 'border-blue-500 text-blue-400' },
  { key: 'offer-sent', label: 'Offer Sent', color: 'border-purple-500 text-purple-400' },
  { key: 'under-contract', label: 'Under Contract', color: 'border-yellow-500 text-yellow-400' },
  { key: 'assigned', label: 'Assigned', color: 'border-green-500 text-green-400' },
  { key: 'closed', label: 'Closed', color: 'border-emerald-500 text-emerald-400' },
  { key: 'dead', label: 'Dead', color: 'border-red-500/50 text-red-400/70' },
];

function download(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDocs, setShowDocs] = useState(false);

  useEffect(() => { void load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch('/api/deals');
      const data = (await res.json()) as { ok: boolean; deals: Deal[] };
      if (data.ok) setDeals(data.deals);
    } finally {
      setLoading(false);
    }
  }

  async function updateDeal(id: number, patch: { status?: string; notes?: string }) {
    // Optimistic update so the board feels instant
    setDeals(ds => ds.map(d => (d.id === id ? { ...d, ...patch } : d)));
    await fetch('/api/deals', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, ...patch }),
    });
  }

  async function remove(id: number) {
    setDeals(ds => ds.filter(d => d.id !== id));
    await fetch(`/api/deals?id=${id}`, { method: 'DELETE' });
  }

  const totalProfit = deals
    .filter(d => d.status !== 'dead')
    .reduce((s, d) => s + (d.projectedProfit ?? 0), 0);

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <header className="border-b border-gray-800 bg-[#161b22]">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/search" className="flex items-center gap-2">
              <span className="font-bold text-lg text-gray-100">Wholesale Engine</span>
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/search" className="text-gray-500 hover:text-gray-300">Search</Link>
              <Link href="/deals" className="text-green-400 font-medium">Pipeline</Link>
              <Link href="/buyers" className="text-gray-500 hover:text-gray-300">Buyers</Link>
              <Link href="/alerts" className="text-gray-500 hover:text-gray-300">Alerts</Link>
            </nav>
          </div>
          <button onClick={() => setShowDocs(s => !s)}
            className="flex items-center gap-2 px-4 py-2 border border-gray-700 hover:border-gray-500 rounded-lg text-sm font-semibold transition-colors">
            <FileSignature className="w-4 h-4 text-green-400" /> Contract Documents
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-2">
          <Briefcase className="w-6 h-6 text-green-400" />
          <h1 className="text-xl font-bold">Deal Pipeline</h1>
          <span className="text-sm text-gray-500">({deals.length} deals)</span>
          {totalProfit > 0 && (
            <span className="ml-auto text-sm text-green-400 font-semibold">
              {formatCurrency(totalProfit)} projected profit in pipeline
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-6">
          Track each property from first contact to assignment. Add deals with the
          “Track Deal” button on the <Link href="/search" className="text-green-400 hover:underline">Search</Link> page.
        </p>

        {/* Documents panel */}
        {showDocs && <DocumentsPanel onClose={() => setShowDocs(false)} />}

        {loading ? (
          <div className="text-center py-16 text-gray-500">Loading…</div>
        ) : deals.length === 0 ? (
          <div className="text-center py-16">
            <Briefcase className="w-10 h-10 mx-auto mb-3 text-gray-700" />
            <p className="text-gray-500 mb-2">No deals in your pipeline yet.</p>
            <Link href="/search" className="text-green-400 hover:underline text-sm">
              Find properties and click “Track Deal” to start →
            </Link>
          </div>
        ) : (
          <div className="flex gap-4 overflow-x-auto pb-4">
            {STAGES.map(stage => {
              const col = deals.filter(d => d.status === stage.key);
              return (
                <div key={stage.key} className="shrink-0 w-72">
                  <div className={cn('flex items-center justify-between mb-3 pb-2 border-b-2', stage.color)}>
                    <span className="text-sm font-semibold">{stage.label}</span>
                    <span className="text-xs text-gray-500">{col.length}</span>
                  </div>
                  <div className="space-y-3">
                    {col.map(d => (
                      <DealCard key={d.id} deal={d} onUpdate={updateDeal} onRemove={remove} />
                    ))}
                    {col.length === 0 && (
                      <div className="text-xs text-gray-700 text-center py-6 border border-dashed border-gray-800 rounded-lg">
                        Empty
                      </div>
                    )}
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

function DealCard({ deal, onUpdate, onRemove }: {
  deal: Deal;
  onUpdate: (id: number, patch: { status?: string; notes?: string }) => void;
  onRemove: (id: number) => void;
}) {
  const [notes, setNotes] = useState(deal.notes ?? '');
  const [editingNotes, setEditingNotes] = useState(false);

  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="min-w-0">
          {deal.listingUrl ? (
            <a href={deal.listingUrl} target="_blank" rel="noopener noreferrer"
              className="group inline-flex items-center gap-1 text-sm font-semibold text-gray-200 hover:text-green-400 max-w-full">
              <span className="truncate">{deal.address}</span>
              <ExternalLink className="w-3 h-3 shrink-0 opacity-0 group-hover:opacity-100" />
            </a>
          ) : (
            <span className="text-sm font-semibold text-gray-200 truncate block">{deal.address}</span>
          )}
          <p className="text-xs text-gray-500">{deal.city}, {deal.state} {deal.zip}</p>
        </div>
        {deal.wholesaleScore != null && (
          <span className={cn('shrink-0 px-1.5 py-0.5 rounded text-xs font-bold border',
            deal.wholesaleScore >= 75 ? 'text-green-400 border-green-400/30 bg-green-400/10'
              : deal.wholesaleScore >= 50 ? 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10'
              : 'text-red-400 border-red-400/30 bg-red-400/10')}>
            {deal.wholesaleScore}
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-gray-500 mb-2">
        <span>List {formatCurrency(deal.price)}</span>
        {deal.mao != null && <span>MAO {formatCurrency(deal.mao)}</span>}
        {deal.projectedProfit != null && (
          <span className={deal.projectedProfit > 0 ? 'text-green-400' : 'text-red-400/70'}>
            {deal.projectedProfit > 0 ? '+' : ''}{formatCurrency(deal.projectedProfit)}
          </span>
        )}
      </div>

      {/* Notes */}
      {editingNotes ? (
        <textarea
          value={notes}
          autoFocus
          onChange={e => setNotes(e.target.value)}
          onBlur={() => { setEditingNotes(false); onUpdate(deal.id, { notes }); }}
          rows={2}
          placeholder="Add a note — agent name, callback time, offer amount…"
          className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-green-500 mb-2"
        />
      ) : (
        <button onClick={() => setEditingNotes(true)}
          className="w-full text-left text-xs text-gray-500 hover:text-gray-300 italic mb-2 min-h-[1.25rem]">
          {notes || '+ Add note'}
        </button>
      )}

      <div className="flex items-center gap-1.5">
        <select
          value={deal.status}
          onChange={e => onUpdate(deal.id, { status: e.target.value })}
          className="flex-1 bg-[#0d1117] border border-gray-700 rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-green-500"
        >
          {STAGES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <button onClick={() => onRemove(deal.id)} className="p-1 text-gray-600 hover:text-red-400" title="Remove from pipeline">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

function DocumentsPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="bg-[#161b22] border border-gray-700 rounded-lg p-5 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-gray-200 flex items-center gap-2">
          <FileSignature className="w-4 h-4 text-green-400" /> Contract Documents
        </h2>
        <button onClick={onClose}><X className="w-4 h-4 text-gray-500" /></button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Templates */}
        <div>
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Templates</p>
          <div className="space-y-2">
            <button
              onClick={() => download('wholesale-purchase-agreement.txt', PURCHASE_AGREEMENT_TEMPLATE)}
              className="w-full flex items-center gap-2 px-3 py-2 bg-[#0d1117] border border-gray-700 hover:border-green-500 rounded text-sm text-gray-300 transition-colors">
              <FileText className="w-4 h-4 text-green-400" />
              Purchase &amp; Sale Agreement (assignable)
              <Download className="w-3.5 h-3.5 ml-auto text-gray-500" />
            </button>
            <button
              onClick={() => download('assignment-of-contract.txt', ASSIGNMENT_OF_CONTRACT_TEMPLATE)}
              className="w-full flex items-center gap-2 px-3 py-2 bg-[#0d1117] border border-gray-700 hover:border-green-500 rounded text-sm text-gray-300 transition-colors">
              <FileText className="w-4 h-4 text-green-400" />
              Assignment of Contract
              <Download className="w-3.5 h-3.5 ml-auto text-gray-500" />
            </button>
          </div>
        </div>

        {/* E-sign services */}
        <div>
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">E-Sign Services</p>
          <div className="space-y-2">
            <a href="https://www.docusign.com" target="_blank" rel="noopener noreferrer"
              className="w-full flex items-center gap-2 px-3 py-2 bg-[#0d1117] border border-gray-700 hover:border-green-500 rounded text-sm text-gray-300 transition-colors">
              <FileSignature className="w-4 h-4 text-blue-400" />
              DocuSign
              <ExternalLink className="w-3.5 h-3.5 ml-auto text-gray-500" />
            </a>
            <a href="https://sign.dropbox.com" target="_blank" rel="noopener noreferrer"
              className="w-full flex items-center gap-2 px-3 py-2 bg-[#0d1117] border border-gray-700 hover:border-green-500 rounded text-sm text-gray-300 transition-colors">
              <FileSignature className="w-4 h-4 text-blue-400" />
              Dropbox Sign (HelloSign)
              <ExternalLink className="w-3.5 h-3.5 ml-auto text-gray-500" />
            </a>
          </div>
        </div>
      </div>

      <div className="mt-4 p-3 bg-yellow-900/10 border border-yellow-700/30 rounded text-xs text-yellow-500/80 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <span>
          These templates are generic and for educational use only — not legal advice.
          Real estate contract law is state-specific. Have a licensed attorney or title
          company in the property’s state review any contract before you sign it or
          present it to a seller.
        </span>
      </div>
    </div>
  );
}
