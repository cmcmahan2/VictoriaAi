'use client';

import { useState } from 'react';

type Appraisal = {
  domain: string;
  valueLow: number;
  valueMedian: number;
  valueHigh: number;
  valueSource: 'godaddy' | 'claude';
  sellability: number;
  buyers: string;
  reasoning: string;
};

const SOURCES = [
  {
    name: 'GoDaddy Auctions',
    desc: 'Expiring domains with history — from $12',
    url: 'https://auctions.godaddy.com/',
    color: 'border-green-500/30 hover:border-green-500/60',
  },
  {
    name: 'Namecheap Closeouts',
    desc: 'Discounted expiring domains — sometimes $1–5',
    url: 'https://www.namecheap.com/domains/marketplace/closeouts/',
    color: 'border-blue-500/30 hover:border-blue-500/60',
  },
  {
    name: 'ExpiredDomains.net',
    desc: 'Massive free list with backlink & age data',
    url: 'https://www.expireddomains.net/',
    color: 'border-purple-500/30 hover:border-purple-500/60',
  },
  {
    name: 'DropCatch',
    desc: 'Catch domains the moment they expire',
    url: 'https://www.dropcatch.com/',
    color: 'border-orange-500/30 hover:border-orange-500/60',
  },
  {
    name: 'SnapNames',
    desc: 'Auction & backorder marketplace',
    url: 'https://www.snapnames.com/',
    color: 'border-yellow-500/30 hover:border-yellow-500/60',
  },
];

function usd(n: number) {
  return '$' + Math.round(n).toLocaleString();
}


function ValueBar({ low, median, high }: { low: number; median: number; high: number }) {
  const color =
    median >= 2000 ? 'bg-green-400' : median >= 500 ? 'bg-yellow-400' : 'bg-[#484f58]';
  return (
    <div className="flex items-baseline gap-2 flex-wrap">
      <span className="text-2xl font-bold text-[#e6edf3]">{usd(median)}</span>
      <span className="text-sm text-[#6e7681]">
        estimated value ({usd(low)}–{usd(high)})
      </span>
      <div className="w-full h-1.5 bg-[#1c2128] rounded-full mt-1">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.min(100, (Math.log10(Math.max(median, 1)) / 5) * 100)}%` }}
        />
      </div>
    </div>
  );
}

export default function AppraisePage() {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Appraisal | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function appraise() {
    const domain = input.trim();
    if (!domain || loading) return;
    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await fetch('/api/appraise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain }),
      });
      const data = (await res.json()) as { ok: boolean; appraisal?: Appraisal; error?: string };
      if (!data.ok) throw new Error(data.error || 'Appraisal failed');
      setResult(data.appraisal!);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') appraise();
  }

  const godaddyBuy = (d: string) =>
    `https://www.godaddy.com/domainsearch/find?domainToCheck=${encodeURIComponent(d)}`;
  const namecheapBuy = (d: string) =>
    `https://www.namecheap.com/domains/registration/results/?domain=${encodeURIComponent(d)}`;

  return (
    <div className="p-3 md:p-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#e6edf3]">Domain Appraiser</h1>
        <p className="text-sm text-[#8b949e] mt-1">
          Find a domain on the sources below, paste it here — get a buy/skip verdict in seconds.
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-2 mb-6">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="techforge.com"
          className="flex-1 px-4 py-3 bg-[#161b22] border border-[#30363d] rounded-lg text-[#e6edf3] placeholder-[#6e7681] text-sm font-mono outline-none focus:border-[#484f58] transition-colors"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <button
          onClick={appraise}
          disabled={!input.trim() || loading}
          className="px-5 py-3 bg-[#238636] hover:bg-[#2ea043] disabled:bg-[#1c2128] disabled:text-[#484f58] text-white text-sm font-medium rounded-lg transition-colors shrink-0"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin inline-block">⟳</span>
              <span className="hidden sm:inline">Checking…</span>
            </span>
          ) : (
            'Appraise →'
          )}
        </button>
      </div>

      {/* Result */}
      {result && (
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 mb-6 space-y-4">
          {/* Big verdict banner */}
          {result.sellability >= 60 ? (
            <div className="flex items-center gap-3 bg-green-400/10 border border-green-400/30 rounded-lg px-4 py-3">
              <span className="text-2xl">✅</span>
              <div>
                <p className="text-green-400 font-bold text-sm">BUY — Sell score {result.sellability}/100</p>
                <p className="text-xs text-green-400/70">Clears the 60+ threshold. Worth registering.</p>
              </div>
            </div>
          ) : result.sellability >= 40 ? (
            <div className="flex items-center gap-3 bg-yellow-400/10 border border-yellow-400/30 rounded-lg px-4 py-3">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="text-yellow-400 font-bold text-sm">RISKY — Sell score {result.sellability}/100</p>
                <p className="text-xs text-yellow-400/70">Below 60. Only buy if ROI is very high.</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 bg-red-400/10 border border-red-400/30 rounded-lg px-4 py-3">
              <span className="text-2xl">❌</span>
              <div>
                <p className="text-red-400 font-bold text-sm">SKIP — Sell score {result.sellability}/100</p>
                <p className="text-xs text-red-400/70">Low buyer demand. Keep looking.</p>
              </div>
            </div>
          )}

          {/* Domain name */}
          <h2 className="text-xl font-bold font-mono text-[#e6edf3]">{result.domain}</h2>

          {/* Value bar */}
          <ValueBar low={result.valueLow} median={result.valueMedian} high={result.valueHigh} />

          {/* Reasoning */}
          <p className="text-sm text-[#8b949e] leading-relaxed">{result.reasoning}</p>

          {/* Buyers */}
          <div className="text-sm">
            <span className="text-[#6e7681]">Likely buyers: </span>
            <span className="text-[#58a6ff]">{result.buyers}</span>
          </div>

          {/* Valuation source */}
          <p className="text-xs text-[#6e7681]">
            Valuation by <span className="text-[#e6edf3]">{result.valueSource}</span>
          </p>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-[#30363d]">
            <a
              href={godaddyBuy(result.domain)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm px-4 py-2 rounded-lg bg-[#238636] hover:bg-[#2ea043] text-white font-medium transition-colors"
            >
              Buy on GoDaddy ↗
            </a>
            <a
              href={namecheapBuy(result.domain)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm px-4 py-2 rounded-lg border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors"
            >
              Namecheap ↗
            </a>
            <a
              href="/portfolio"
              className="text-sm px-4 py-2 rounded-lg border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors"
            >
              + Add to Portfolio
            </a>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-6 px-4 py-3 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Source marketplaces */}
      <div>
        <p className="text-xs text-[#6e7681] font-medium uppercase tracking-wider mb-3">
          Where to find domains
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {SOURCES.map((s) => (
            <a
              key={s.name}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`block p-3 bg-[#161b22] border rounded-lg transition-colors group ${s.color}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-[#e6edf3] group-hover:text-white">
                  {s.name}
                </span>
                <span className="text-[#6e7681] text-xs">↗</span>
              </div>
              <p className="text-xs text-[#6e7681] mt-0.5">{s.desc}</p>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
