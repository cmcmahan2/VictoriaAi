'use client';

import { useEffect, useState } from 'react';

type OwnedDomain = {
  id: number;
  domain: string;
  registrar: string;
  registeredAt: number;
  costBasis: number;
  currentValuation: number | null;
  renewalDate: number | null;
  renewalCost: number | null;
  listingStatus: 'unlisted' | 'listed' | 'sold';
  soldAt: number | null;
  salePrice: number | null;
  netProfit: number | null;
};

type Summary = {
  count: number;
  invested: number;
  estValue: number;
  realizedProfit: number;
};

function usd(n: number | null | undefined): string {
  return '$' + Math.round(n || 0).toLocaleString();
}

function dateStr(ts: number | null): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

const STATUS_STYLE: Record<OwnedDomain['listingStatus'], string> = {
  unlisted: 'text-[#8b949e] border-[#30363d]',
  listed: 'text-blue-400 border-blue-400/30 bg-blue-400/10',
  sold: 'text-green-400 border-green-400/30 bg-green-400/10',
};

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 flex-1 min-w-[140px]">
      <p className="text-xs text-[#6e7681]">{label}</p>
      <p className={`text-2xl font-bold mt-1 tabular-nums ${accent || 'text-[#e6edf3]'}`}>{value}</p>
    </div>
  );
}

export default function PortfolioPage() {
  const [loading, setLoading] = useState(true);
  const [dbConfigured, setDbConfigured] = useState(true);
  const [domains, setDomains] = useState<OwnedDomain[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/portfolio');
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Failed to load portfolio');
      setDbConfigured(data.dbConfigured !== false);
      setDomains(data.domains || []);
      setSummary(data.summary || null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function patch(id: number, action: string, extra: Record<string, unknown> = {}) {
    const res = await fetch('/api/portfolio', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, action, ...extra }),
    });
    const data = await res.json();
    if (!data.ok) {
      setError(data.error);
      return;
    }
    load();
  }

  async function remove(id: number) {
    const res = await fetch('/api/portfolio', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    const data = await res.json();
    if (!data.ok) {
      setError(data.error);
      return;
    }
    load();
  }

  async function markSold(d: OwnedDomain) {
    const input = window.prompt(`Sale price for ${d.domain}?`, String(d.currentValuation || d.costBasis));
    if (input === null) return;
    const salePrice = Number(input);
    if (Number.isNaN(salePrice)) {
      setError('Sale price must be a number.');
      return;
    }
    patch(d.id, 'sold', { salePrice });
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e6edf3]">Portfolio</h1>
          <p className="text-sm text-[#8b949e] mt-0.5">Domains you own — cost, value, renewals, and profit</p>
        </div>
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-md text-sm text-[#8b949e] border border-[#30363d] hover:text-[#e6edf3] hover:border-[#484f58] transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {!dbConfigured && (
        <div className="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-4 mb-6">
          <p className="text-yellow-400 text-sm font-medium">Portfolio storage not enabled</p>
          <p className="text-yellow-200/80 text-sm mt-1">
            Create a free database at{' '}
            <a href="https://turso.tech" target="_blank" rel="noopener noreferrer" className="underline">
              turso.tech
            </a>{' '}
            and add <code className="text-[#e6edf3]">TURSO_DATABASE_URL</code> and{' '}
            <code className="text-[#e6edf3]">TURSO_AUTH_TOKEN</code> in your Vercel environment variables to start
            tracking domains you buy.
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-3 mb-4">
          <p className="text-red-300 text-sm font-mono">{error}</p>
        </div>
      )}

      {summary && summary.count > 0 && (
        <div className="flex flex-wrap gap-3 mb-6">
          <Stat label="Domains" value={String(summary.count)} />
          <Stat label="Invested" value={usd(summary.invested)} />
          <Stat label="Est. value" value={usd(summary.estValue)} accent="text-blue-400" />
          <Stat
            label="Realized profit"
            value={usd(summary.realizedProfit)}
            accent={summary.realizedProfit >= 0 ? 'text-green-400' : 'text-red-400'}
          />
        </div>
      )}

      {loading ? (
        <p className="text-[#6e7681] text-center py-12">Loading…</p>
      ) : domains.length === 0 ? (
        <div className="border border-dashed border-[#30363d] rounded-lg p-12 text-center">
          <p className="text-[#6e7681] text-sm">No domains yet.</p>
          <p className="text-xs text-[#484f58] mt-2">
            Run a hunt, then click “Add to Portfolio” on any domain to track it here.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {domains.map((d) => (
            <div key={d.id} className="bg-[#161b22] border border-[#30363d] rounded-lg p-4">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-[#e6edf3] font-semibold font-mono">{d.domain}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_STYLE[d.listingStatus]}`}>
                      {d.listingStatus}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-[#8b949e]">
                    <span>Cost <span className="text-[#e6edf3] font-medium">{usd(d.costBasis)}</span></span>
                    <span>Value <span className="text-[#e6edf3] font-medium">{usd(d.currentValuation)}</span></span>
                    <span>Renews <span className="text-[#e6edf3] font-medium">{dateStr(d.renewalDate)}</span></span>
                    {d.listingStatus === 'sold' && (
                      <span>
                        Sold{' '}
                        <span className="text-green-400 font-medium">{usd(d.salePrice)}</span>{' '}
                        (profit{' '}
                        <span className={(d.netProfit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {usd(d.netProfit)}
                        </span>
                        )
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {d.listingStatus !== 'sold' && (
                    <>
                      {d.listingStatus === 'unlisted' ? (
                        <button
                          onClick={() => patch(d.id, 'list')}
                          className="text-xs px-2.5 py-1 rounded border border-[#30363d] text-blue-400 hover:border-blue-400/50 transition-colors"
                        >
                          List
                        </button>
                      ) : (
                        <button
                          onClick={() => patch(d.id, 'unlist')}
                          className="text-xs px-2.5 py-1 rounded border border-[#30363d] text-[#8b949e] hover:border-[#484f58] transition-colors"
                        >
                          Unlist
                        </button>
                      )}
                      <button
                        onClick={() => markSold(d)}
                        className="text-xs px-2.5 py-1 rounded border border-green-400/30 text-green-400 hover:bg-green-400/10 transition-colors"
                      >
                        Mark sold
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => remove(d.id)}
                    className="text-xs px-2.5 py-1 rounded border border-[#30363d] text-[#8b949e] hover:text-red-400 hover:border-red-400/50 transition-colors"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
