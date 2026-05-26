'use client';

import { useState } from 'react';

// ── Types ──────────────────────────────────────────────────────────────────

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

type DomainResult = {
  domain: string;
  sld: string;
  tld: string;
  strategy: string;
  basis: string;
  estPrice: number;
  valueLow: number;
  valueMedian: number;
  valueHigh: number;
  valueSource: 'godaddy' | 'claude';
  sellability: number;
  buyers: string;
  reasoning: string;
  score: number;
  roi: number;
};

const SOURCES = [
  { name: 'GoDaddy Auctions',     desc: 'Expiring domains with history — from $12',       url: 'https://auctions.godaddy.com/',                                              color: 'border-green-500/30 hover:border-green-500/60' },
  { name: 'Namecheap Closeouts',  desc: 'Discounted expiring domains — sometimes $1–5',   url: 'https://www.namecheap.com/domains/marketplace/closeouts/',                   color: 'border-blue-500/30 hover:border-blue-500/60' },
  { name: 'ExpiredDomains.net',   desc: 'Massive free list with backlink & age data',      url: 'https://www.expireddomains.net/',                                            color: 'border-purple-500/30 hover:border-purple-500/60' },
  { name: 'DropCatch',            desc: 'Catch domains the moment they expire',            url: 'https://www.dropcatch.com/',                                                 color: 'border-orange-500/30 hover:border-orange-500/60' },
  { name: 'SnapNames',            desc: 'Auction & backorder marketplace',                 url: 'https://www.snapnames.com/',                                                 color: 'border-yellow-500/30 hover:border-yellow-500/60' },
];

// ── Helpers ────────────────────────────────────────────────────────────────

function usd(n: number) {
  return '$' + Math.round(n).toLocaleString();
}

function Verdict({ score }: { score: number }) {
  if (score >= 60) return (
    <div className="flex items-center gap-3 bg-green-400/10 border border-green-400/30 rounded-lg px-4 py-3">
      <span className="text-xl">✅</span>
      <div>
        <p className="text-green-400 font-bold text-sm">BUY — Sell score {score}/100</p>
        <p className="text-xs text-green-400/70">Clears the 60+ threshold. Worth registering.</p>
      </div>
    </div>
  );
  if (score >= 40) return (
    <div className="flex items-center gap-3 bg-yellow-400/10 border border-yellow-400/30 rounded-lg px-4 py-3">
      <span className="text-xl">⚠️</span>
      <div>
        <p className="text-yellow-400 font-bold text-sm">RISKY — Sell score {score}/100</p>
        <p className="text-xs text-yellow-400/70">Below 60. Only buy if ROI is exceptional.</p>
      </div>
    </div>
  );
  return (
    <div className="flex items-center gap-3 bg-red-400/10 border border-red-400/30 rounded-lg px-4 py-3">
      <span className="text-xl">❌</span>
      <div>
        <p className="text-red-400 font-bold text-sm">SKIP — Sell score {score}/100</p>
        <p className="text-xs text-red-400/70">Low buyer demand. Keep looking.</p>
      </div>
    </div>
  );
}

function ValueBar({ low, median, high }: { low: number; median: number; high: number }) {
  const color = median >= 2000 ? 'bg-green-400' : median >= 500 ? 'bg-yellow-400' : 'bg-[#484f58]';
  return (
    <div>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-2xl font-bold text-[#e6edf3]">{usd(median)}</span>
        <span className="text-sm text-[#6e7681]">({usd(low)}–{usd(high)})</span>
      </div>
      <div className="w-full h-1.5 bg-[#1c2128] rounded-full mt-2">
        <div className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.min(100, (Math.log10(Math.max(median, 1)) / 5) * 100)}%` }} />
      </div>
    </div>
  );
}

// ── Hunt domain card ───────────────────────────────────────────────────────

function HuntCard({ d, rank }: { d: DomainResult; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const godaddyBuy = `https://www.godaddy.com/domainsearch/find?domainToCheck=${encodeURIComponent(d.domain)}`;
  const afternic = `https://www.afternic.com/forsale/${encodeURIComponent(d.domain)}`;

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 hover:border-[#484f58] transition-colors cursor-pointer"
      onClick={() => setExpanded(e => !e)}>
      <div className="flex items-start gap-3">
        <span className="text-[#6e7681] text-sm w-5 shrink-0 pt-0.5">#{rank}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-semibold text-[#e6edf3]">{d.domain}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded border ${
              d.sellability >= 60
                ? 'text-green-400 border-green-400/30 bg-green-400/10'
                : 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10'
            }`}>
              {d.sellability >= 60 ? '✅ BUY' : '⚠️ RISKY'} · {d.sellability}
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-sm text-[#8b949e]">
            <span>Value <span className="text-[#e6edf3]">{usd(d.valueMedian)}</span></span>
            <span>Reg <span className="text-[#e6edf3]">{usd(d.estPrice)}/yr</span></span>
            <span>ROI <span className="text-[#e6edf3]">{d.roi}x</span></span>
          </div>

          {expanded && (
            <div className="mt-3 pt-3 border-t border-[#30363d] space-y-2"
              onClick={e => e.stopPropagation()}>
              <p className="text-sm text-[#8b949e]">{d.reasoning}</p>
              <p className="text-xs text-[#6e7681]">
                Buyers: <span className="text-[#58a6ff]">{d.buyers}</span>
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                <a href={godaddyBuy} target="_blank" rel="noopener noreferrer"
                  className="text-xs px-3 py-1.5 rounded bg-[#238636] hover:bg-[#2ea043] text-white font-medium transition-colors">
                  Buy on GoDaddy ↗
                </a>
                <a href={afternic} target="_blank" rel="noopener noreferrer"
                  className="text-xs px-3 py-1.5 rounded border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors">
                  List on Afternic ↗
                </a>
              </div>
            </div>
          )}
        </div>
        <span className={`shrink-0 text-lg font-bold tabular-nums ${
          d.sellability >= 60 ? 'text-green-400' : 'text-yellow-400'
        }`}>{d.sellability}</span>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function AppraisePage() {
  const [tab, setTab] = useState<'appraise' | 'hunt'>('appraise');

  // Appraise tab
  const [input, setInput] = useState('');
  const [appraising, setAppraising] = useState(false);
  const [appraisal, setAppraisal] = useState<Appraisal | null>(null);
  const [appraiseError, setAppraiseError] = useState<string | null>(null);

  // Hunt tab
  const [huntPhase, setHuntPhase] = useState<'idle' | 'trends' | 'domains' | 'done' | 'error'>('idle');
  const [domains, setDomains] = useState<DomainResult[]>([]);
  const [huntError, setHuntError] = useState<string | null>(null);
  const [huntMeta, setHuntMeta] = useState<{ generated: number; available: number } | null>(null);

  // ── Appraise ──
  async function runAppraise() {
    const domain = input.trim();
    if (!domain || appraising) return;
    setAppraising(true);
    setAppraisal(null);
    setAppraiseError(null);
    try {
      const res = await fetch('/api/appraise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain }),
      });
      const data = await res.json() as { ok: boolean; appraisal?: Appraisal; error?: string };
      if (!data.ok) throw new Error(data.error || 'Appraisal failed');
      setAppraisal(data.appraisal!);
    } catch (err) {
      setAppraiseError((err as Error).message);
    } finally {
      setAppraising(false);
    }
  }

  // ── Hunt ──
  async function runHunt() {
    setHuntPhase('trends');
    setDomains([]);
    setHuntError(null);
    setHuntMeta(null);
    try {
      const tRes = await fetch('/api/trends', { method: 'POST' });
      const tData = await tRes.json() as { ok: boolean; trends?: unknown[]; error?: string };
      if (!tData.ok) throw new Error(tData.error || 'Trend scan failed');

      setHuntPhase('domains');
      const dRes = await fetch('/api/domains', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trends: tData.trends }),
      });
      const dData = await dRes.json() as {
        ok: boolean;
        domains?: DomainResult[];
        meta?: { generated: number; available: number };
        error?: string;
      };
      if (!dData.ok) throw new Error(dData.error || 'Domain scan failed');

      // Only keep sell score 60+
      const quality = (dData.domains || []).filter(d => d.sellability >= 60);
      setDomains(quality);
      setHuntMeta(dData.meta || null);
      setHuntPhase('done');
    } catch (err) {
      setHuntError((err as Error).message);
      setHuntPhase('error');
    }
  }

  const godaddyBuy = (d: string) => `https://www.godaddy.com/domainsearch/find?domainToCheck=${encodeURIComponent(d)}`;
  const namecheapBuy = (d: string) => `https://www.namecheap.com/domains/registration/results/?domain=${encodeURIComponent(d)}`;

  return (
    <div className="p-3 md:p-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-[#e6edf3]">Domain Appraiser</h1>
        <p className="text-sm text-[#8b949e] mt-1">Appraise a specific domain, or auto-hunt for opportunities.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#161b22] border border-[#30363d] rounded-lg p-1 mb-6">
        <button onClick={() => setTab('appraise')}
          className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
            tab === 'appraise' ? 'bg-[#238636] text-white' : 'text-[#8b949e] hover:text-[#e6edf3]'
          }`}>
          🔍 Appraise a Domain
        </button>
        <button onClick={() => setTab('hunt')}
          className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
            tab === 'hunt' ? 'bg-[#238636] text-white' : 'text-[#8b949e] hover:text-[#e6edf3]'
          }`}>
          🎯 Auto-Hunt
        </button>
      </div>

      {/* ── Appraise Tab ── */}
      {tab === 'appraise' && (
        <>
          <div className="flex gap-2 mb-6">
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runAppraise()}
              placeholder="techforge.com"
              className="flex-1 px-4 py-3 bg-[#161b22] border border-[#30363d] rounded-lg text-[#e6edf3] placeholder-[#6e7681] text-sm font-mono outline-none focus:border-[#484f58] transition-colors"
              autoCapitalize="none" autoCorrect="off" spellCheck={false} />
            <button onClick={runAppraise} disabled={!input.trim() || appraising}
              className="px-5 py-3 bg-[#238636] hover:bg-[#2ea043] disabled:bg-[#1c2128] disabled:text-[#484f58] text-white text-sm font-medium rounded-lg transition-colors shrink-0">
              {appraising ? <span className="flex items-center gap-2"><span className="animate-spin">⟳</span><span className="hidden sm:inline">Checking…</span></span> : 'Appraise →'}
            </button>
          </div>

          {appraiseError && (
            <div className="mb-6 px-4 py-3 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-sm">{appraiseError}</div>
          )}

          {appraisal && (
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-5 mb-6 space-y-4">
              <Verdict score={appraisal.sellability} />
              <h2 className="text-xl font-bold font-mono text-[#e6edf3]">{appraisal.domain}</h2>
              <ValueBar low={appraisal.valueLow} median={appraisal.valueMedian} high={appraisal.valueHigh} />
              <p className="text-sm text-[#8b949e] leading-relaxed">{appraisal.reasoning}</p>
              <div className="text-sm">
                <span className="text-[#6e7681]">Likely buyers: </span>
                <span className="text-[#58a6ff]">{appraisal.buyers}</span>
              </div>
              <p className="text-xs text-[#6e7681]">Valuation by <span className="text-[#e6edf3]">{appraisal.valueSource}</span></p>
              <div className="flex flex-wrap gap-2 pt-2 border-t border-[#30363d]">
                <a href={godaddyBuy(appraisal.domain)} target="_blank" rel="noopener noreferrer"
                  className="text-sm px-4 py-2 rounded-lg bg-[#238636] hover:bg-[#2ea043] text-white font-medium transition-colors">Buy on GoDaddy ↗</a>
                <a href={namecheapBuy(appraisal.domain)} target="_blank" rel="noopener noreferrer"
                  className="text-sm px-4 py-2 rounded-lg border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors">Namecheap ↗</a>
                <a href="/portfolio"
                  className="text-sm px-4 py-2 rounded-lg border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors">+ Portfolio</a>
              </div>
            </div>
          )}

          {/* Source links */}
          <div>
            <p className="text-xs text-[#6e7681] font-medium uppercase tracking-wider mb-3">Where to find domains</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SOURCES.map(s => (
                <a key={s.name} href={s.url} target="_blank" rel="noopener noreferrer"
                  className={`block p-3 bg-[#161b22] border rounded-lg transition-colors group ${s.color}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[#e6edf3] group-hover:text-white">{s.name}</span>
                    <span className="text-[#6e7681] text-xs">↗</span>
                  </div>
                  <p className="text-xs text-[#6e7681] mt-0.5">{s.desc}</p>
                </a>
              ))}
            </div>
          </div>
        </>
      )}

      {/* ── Hunt Tab ── */}
      {tab === 'hunt' && (
        <>
          <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 mb-6">
            <p className="text-sm text-[#8b949e] mb-3">
              Scans 7 live sources for trending topics, generates domain candidates, checks availability, and returns only domains with a <span className="text-green-400 font-medium">sell score 60+</span>.
            </p>
            <button onClick={runHunt} disabled={huntPhase === 'trends' || huntPhase === 'domains'}
              className="w-full py-2.5 bg-[#238636] hover:bg-[#2ea043] disabled:bg-[#1c2128] disabled:text-[#484f58] text-white text-sm font-medium rounded-lg transition-colors">
              {huntPhase === 'trends' ? <span className="flex items-center justify-center gap-2"><span className="animate-spin">⟳</span> Scanning trends…</span>
                : huntPhase === 'domains' ? <span className="flex items-center justify-center gap-2"><span className="animate-spin">⟳</span> Checking domains…</span>
                : '🎯 Run Hunt'}
            </button>
          </div>

          {huntError && (
            <div className="mb-4 px-4 py-3 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-sm">{huntError}</div>
          )}

          {huntPhase === 'done' && (
            <div className="mb-4 flex items-center justify-between">
              <p className="text-xs text-[#6e7681]">
                {huntMeta && `${huntMeta.generated} generated → ${huntMeta.available} available → `}
                <span className="text-green-400 font-medium">{domains.length} scored 60+</span>
              </p>
            </div>
          )}

          {huntPhase === 'done' && domains.length === 0 && (
            <div className="border border-dashed border-[#30363d] rounded-lg p-8 text-center">
              <p className="text-[#6e7681] text-sm">No domains hit 60+ this run — try again in a few minutes for different trends.</p>
            </div>
          )}

          <div className="flex flex-col gap-2">
            {domains.map((d, i) => <HuntCard key={d.domain} d={d} rank={i + 1} />)}
          </div>
        </>
      )}
    </div>
  );
}
