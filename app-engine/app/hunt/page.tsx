'use client';

import { useState } from 'react';

type Trend = {
  name: string;
  velocity: 'rising' | 'peak' | 'declining';
  commercialScore: number;
  sources: string[];
  keywords: string[];
  summary: string;
};

type RunMeta = {
  signalCount: number;
  sourceBreakdown: Record<string, number>;
  durationMs: number;
  savedTrends: number;
};

type DomainResult = {
  domain: string;
  sld: string;
  tld: string;
  strategy: string;
  basis: string;
  estPrice: number;
  priceConfirmed: boolean;
  availabilitySource: 'godaddy' | 'rdap';
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

type DomainMeta = {
  generated: number;
  checked: number;
  available: number;
  appraised: number;
  durationMs: number;
  valuationSource: 'godaddy' | 'claude' | 'mixed';
  availabilitySource: 'godaddy' | 'rdap' | 'mixed';
};

type Phase = 'idle' | 'trends' | 'domains' | 'done' | 'error';

const VELOCITY_COLORS = {
  rising: 'text-green-400 bg-green-400/10 border-green-400/30',
  peak: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  declining: 'text-red-400 bg-red-400/10 border-red-400/30',
} as const;

const VELOCITY_ICONS = { rising: '↑', peak: '→', declining: '↓' } as const;

const TOP_N = 10;

function usd(n: number): string {
  return '$' + Math.round(n).toLocaleString();
}

// All registrar links — always shown so users can instantly buy.
function buyLinks(domain: string): { label: string; note: string; url: string }[] {
  const d = encodeURIComponent(domain);
  return [
    {
      label: 'Porkbun',
      note: 'often cheapest',
      url: `https://porkbun.com/checkout/search?q=${d}`,
    },
    {
      label: 'Namecheap',
      note: 'competitive',
      url: `https://www.namecheap.com/domains/registration/results/?domain=${d}`,
    },
    {
      label: 'GoDaddy',
      note: 'largest',
      url: `https://www.godaddy.com/domainsearch/find?domainToCheck=${d}`,
    },
  ];
}

// Marketplace links — the main places to list and sell a domain once you own it.
function sellLinks(domain: string): { label: string; note: string; url: string }[] {
  const d = encodeURIComponent(domain);
  return [
    {
      label: 'Afternic',
      note: 'largest reach',
      url: `https://www.afternic.com/forsale/${d}`,
    },
    {
      label: 'Dan.com',
      note: 'clean checkout',
      url: `https://dan.com/buy-domain/${d}`,
    },
    {
      label: 'Sedo',
      note: 'global',
      url: `https://sedo.com/search/?keyword=${d}`,
    },
    {
      label: 'Flippa',
      note: 'startup buyers',
      url: `https://flippa.com/domains?search[query]=${d}`,
    },
  ];
}

function LinkPill({ label, note, url }: { label: string; note: string; url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className="inline-flex flex-col items-start px-3 py-1.5 rounded border border-[#30363d] hover:border-[#58a6ff] hover:bg-[#58a6ff]/10 transition-colors group"
    >
      <span className="text-xs font-medium text-[#58a6ff] group-hover:text-[#79c0ff] leading-tight">
        {label} ↗
      </span>
      <span className="text-[10px] text-[#6e7681] leading-tight">{note}</span>
    </a>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? 'text-green-400' : score >= 40 ? 'text-yellow-400' : 'text-red-400';
  return <span className={`text-lg font-bold tabular-nums ${color}`}>{score}</span>;
}

function DomainCard({ d, rank }: { d: DomainResult; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'exists' | 'error'>('idle');
  const sellColor =
    d.sellability >= 70 ? 'text-green-400' : d.sellability >= 40 ? 'text-yellow-400' : 'text-red-400';

  async function addToPortfolio(e: React.MouseEvent) {
    e.stopPropagation();
    if (saveState === 'saving' || saveState === 'saved' || saveState === 'exists') return;
    setSaveState('saving');
    try {
      const res = await fetch('/api/portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domain: d.domain,
          registrar: 'unknown',
          costBasis: d.estPrice,
          currentValuation: d.valueMedian,
        }),
      });
      const data = await res.json();
      if (res.status === 409) setSaveState('exists');
      else if (!data.ok) setSaveState('error');
      else setSaveState('saved');
    } catch {
      setSaveState('error');
    }
  }

  const saveLabel = {
    idle: '+ Add to Portfolio',
    saving: 'Adding…',
    saved: '✓ In Portfolio',
    exists: '✓ Already added',
    error: 'Failed — retry',
  }[saveState];

  const buy = buyLinks(d.domain);
  const sell = sellLinks(d.domain);

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 hover:border-[#484f58] transition-colors">
      {/* Header row */}
      <div className="flex items-start gap-4">
        <span className="text-[#6e7681] text-sm w-6 text-right shrink-0 pt-0.5">#{rank}</span>

        <div className="flex-1 min-w-0">
          {/* Domain name + badges */}
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-[#e6edf3] font-semibold font-mono text-base">{d.domain}</h3>
            <span className="text-xs px-2 py-0.5 rounded border border-[#30363d] text-[#8b949e]">
              {d.strategy}
            </span>
            {d.availabilitySource === 'godaddy' ? (
              <span
                title="Confirmed available by GoDaddy registrar API"
                className="text-xs px-2 py-0.5 rounded border border-green-400/30 text-green-400 bg-green-400/10"
              >
                ✓ confirmed available
              </span>
            ) : (
              <span
                title="Unregistered per RDAP — verify at checkout"
                className="text-xs px-2 py-0.5 rounded border border-yellow-400/30 text-yellow-400 bg-yellow-400/10"
              >
                likely available
              </span>
            )}
          </div>

          {/* Stats row */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
            <span className="text-[#8b949e]">
              Est. value{' '}
              <span className="text-[#e6edf3] font-medium">{usd(d.valueMedian)}</span>
              <span className="text-[#6e7681]"> ({usd(d.valueLow)}–{usd(d.valueHigh)})</span>
            </span>
            <span className="text-[#8b949e]">
              Reg.{' '}
              <span className="text-[#e6edf3] font-medium">{usd(d.estPrice)}/yr</span>
              {!d.priceConfirmed && <span className="text-[#6e7681]"> est.</span>}
            </span>
            <span className="text-[#8b949e]">
              ROI <span className="text-blue-400 font-bold">{d.roi}x</span>
            </span>
            <span className="text-[#8b949e]">
              Sellability <span className={`font-medium ${sellColor}`}>{d.sellability}/100</span>
            </span>
          </div>

          {/* Buy links — always visible */}
          <div className="mt-3">
            <p className="text-[10px] text-[#6e7681] uppercase tracking-wide mb-1.5 font-medium">
              Register at
            </p>
            <div className="flex flex-wrap gap-2">
              {buy.map((l) => (
                <LinkPill key={l.label} {...l} />
              ))}
            </div>
          </div>

          {/* Sell links — always visible */}
          <div className="mt-3">
            <p className="text-[10px] text-[#6e7681] uppercase tracking-wide mb-1.5 font-medium">
              Sell on marketplace
            </p>
            <div className="flex flex-wrap gap-2">
              {sell.map((l) => (
                <LinkPill key={l.label} {...l} />
              ))}
            </div>
          </div>

          {/* Portfolio button + detail toggle */}
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <button
              onClick={addToPortfolio}
              disabled={saveState === 'saving' || saveState === 'saved' || saveState === 'exists'}
              className={`text-xs font-medium px-3 py-1.5 rounded-md border transition-colors ${
                saveState === 'saved' || saveState === 'exists'
                  ? 'border-green-400/30 text-green-400 bg-green-400/10 cursor-default'
                  : saveState === 'error'
                    ? 'border-red-400/40 text-red-400 hover:bg-red-400/10'
                    : 'border-[#30363d] text-[#8b949e] hover:text-[#e6edf3] hover:border-[#484f58]'
              }`}
            >
              {saveLabel}
            </button>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-[#6e7681] hover:text-[#8b949e] transition-colors"
            >
              {expanded ? '▲ Less detail' : '▾ More detail'}
            </button>
          </div>

          {/* Expanded detail */}
          {expanded && (
            <div className="mt-3 pt-3 border-t border-[#30363d] space-y-2">
              <p className="text-sm text-[#8b949e] leading-relaxed">{d.reasoning}</p>
              <p className="text-xs text-[#6e7681]">
                Likely buyers: <span className="text-[#58a6ff]">{d.buyers}</span>
              </p>
              <p className="text-xs text-[#6e7681]">
                Trend: <span className="text-[#e6edf3]">{d.basis || '—'}</span> · valuation by{' '}
                <span className="text-[#e6edf3]">{d.valueSource}</span> · availability via{' '}
                <span className="text-[#e6edf3]">{d.availabilitySource}</span>
              </p>
            </div>
          )}
        </div>

        {/* Score badge */}
        <div className="shrink-0 text-right">
          <ScoreBadge score={d.score} />
          <p className="text-xs text-[#6e7681] mt-0.5">score</p>
        </div>
      </div>
    </div>
  );
}

// Best-practice guide for buying and selling domains.
function BuySellGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-6 border border-[#30363d] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#161b22] text-sm text-[#e6edf3] hover:bg-[#1c2128] transition-colors"
      >
        <span className="font-medium">How to buy & sell domains for profit</span>
        <span className="text-[#6e7681]">{open ? '▲' : '▾'}</span>
      </button>
      {open && (
        <div className="bg-[#0d1117] border-t border-[#30363d] px-5 py-4 space-y-4 text-sm text-[#8b949e]">
          <section>
            <h3 className="text-[#e6edf3] font-semibold mb-1">Buying — where and how</h3>
            <ul className="space-y-1.5 list-disc list-inside marker:text-[#6e7681]">
              <li>
                <span className="text-[#e6edf3]">Porkbun</span> and{' '}
                <span className="text-[#e6edf3]">Namecheap</span> are consistently the cheapest
                registrars for .com (~$8–$10/yr). GoDaddy's first-year promos look cheap but
                renewals are higher — lock in multi-year at Porkbun instead.
              </li>
              <li>
                Enable <span className="text-[#e6edf3]">auto-renewal</span> immediately so you
                never accidentally lose the domain.
              </li>
              <li>
                Enable <span className="text-[#e6edf3]">WHOIS privacy</span> (free at most
                registrars) to protect your identity from spam and competing investors.
              </li>
              <li>
                <span className="text-[#e6edf3]">Lock the domain</span> (registrar lock) after
                purchase to prevent unauthorized transfers.
              </li>
              <li>
                If a .com you want is taken but the owner isn't using it, check{' '}
                <span className="text-[#e6edf3]">Afternic</span> or{' '}
                <span className="text-[#e6edf3]">Sedo</span> for a buy-now or make-offer listing —
                sometimes sellers accept low offers on parked names.
              </li>
            </ul>
          </section>

          <section>
            <h3 className="text-[#e6edf3] font-semibold mb-1">Selling — where to list</h3>
            <ul className="space-y-1.5 list-disc list-inside marker:text-[#6e7681]">
              <li>
                <span className="text-[#e6edf3]">Afternic</span> (GoDaddy's marketplace) has the
                largest buyer network — list here first. It syndicates to 100+ registrar search
                results, so buyers find you when they search for the domain anywhere. Commission
                is 15–20%.
              </li>
              <li>
                <span className="text-[#e6edf3]">Dan.com</span> has the cleanest buyer checkout
                and charges 9% commission. It's better for $500–$10k names where friction matters.
              </li>
              <li>
                <span className="text-[#e6edf3]">Sedo</span> reaches European buyers and
                corporations who prefer it for formal negotiations and escrow. Good for premium
                names above $5k.
              </li>
              <li>
                <span className="text-[#e6edf3]">Flippa</span> is strong when the domain has any
                history, traffic, or existing backlinks — startup buyers pay a premium for that.
              </li>
            </ul>
          </section>

          <section>
            <h3 className="text-[#e6edf3] font-semibold mb-1">Pricing strategy</h3>
            <ul className="space-y-1.5 list-disc list-inside marker:text-[#6e7681]">
              <li>
                List at <span className="text-[#e6edf3]">3–5× your target price</span>. Buyers
                negotiate; starting high gives room to close at your real target.
              </li>
              <li>
                Set a <span className="text-[#e6edf3]">BIN (Buy It Now)</span> price for faster
                sales on lower-value names. Negotiation-only listings sell slower but for more.
              </li>
              <li>
                Domain investing is a <span className="text-[#e6edf3]">long game</span> — average
                sell time is 6–24 months. Hold costs are just the renewal fee; patience wins.
              </li>
              <li>
                If a domain hasn't sold in 12 months, lower the price by 30% or drop it to avoid
                another renewal fee on a weak asset.
              </li>
            </ul>
          </section>

          <section>
            <h3 className="text-[#e6edf3] font-semibold mb-1">What makes a domain valuable</h3>
            <ul className="space-y-1.5 list-disc list-inside marker:text-[#6e7681]">
              <li>
                <span className="text-[#e6edf3]">.com always commands a premium</span> — end-user
                companies want .com for credibility. .io and .ai are accepted by tech startups.
              </li>
              <li>
                Short, one-word, or two-word compounds sell fastest. Under 10 characters is ideal.
              </li>
              <li>
                <span className="text-[#e6edf3]">Exact-match commercial terms</span> (e.g. a
                product category) sell for more because buyers have immediate clear use cases.
              </li>
              <li>
                Avoid hyphens, numbers, and misspellings — they're very hard to sell.
              </li>
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}

export default function HuntPage() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [trends, setTrends] = useState<Trend[]>([]);
  const [trendMeta, setTrendMeta] = useState<RunMeta | null>(null);
  const [domains, setDomains] = useState<DomainResult[]>([]);
  const [domainMeta, setDomainMeta] = useState<DomainMeta | null>(null);
  const [showTrends, setShowTrends] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const running = phase === 'trends' || phase === 'domains';

  // Sort by ROI desc (most profitable first) and keep the top 10.
  const top10 = [...domains].sort((a, b) => b.roi - a.roi).slice(0, TOP_N);

  async function runHunt() {
    setError(null);
    setTrends([]);
    setTrendMeta(null);
    setDomains([]);
    setDomainMeta(null);

    try {
      setPhase('trends');
      const tRes = await fetch('/api/trends', { method: 'POST' });
      const tData = (await tRes.json()) as {
        ok: boolean;
        trends?: Trend[];
        meta?: RunMeta;
        error?: string;
      };
      if (!tData.ok) throw new Error(tData.error || 'Trend hunt failed');
      const foundTrends = tData.trends || [];
      setTrends(foundTrends);
      setTrendMeta(tData.meta || null);

      if (foundTrends.length === 0) {
        throw new Error('No trends found — cannot generate domains.');
      }

      setPhase('domains');
      const dRes = await fetch('/api/domains', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trends: foundTrends }),
      });
      const dData = (await dRes.json()) as {
        ok: boolean;
        domains?: DomainResult[];
        meta?: DomainMeta;
        error?: string;
      };
      if (!dData.ok) throw new Error(dData.error || 'Domain hunt failed');
      setDomains(dData.domains || []);
      setDomainMeta(dData.meta || null);

      setPhase('done');
    } catch (err) {
      setError((err as Error).message);
      setPhase('error');
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e6edf3]">Domain Hunt</h1>
          <p className="text-sm text-[#8b949e] mt-0.5">
            Trends → generate names → confirm availability → value & rank by ROI
          </p>
        </div>
        <button
          onClick={runHunt}
          disabled={running}
          className={`px-5 py-2 rounded-md text-sm font-medium transition-all ${
            running
              ? 'bg-[#1c2128] text-[#6e7681] cursor-not-allowed'
              : 'bg-[#238636] hover:bg-[#2ea043] text-white cursor-pointer'
          }`}
        >
          {running ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin">⟳</span> Running…
            </span>
          ) : (
            '▶ Run Hunt'
          )}
        </button>
      </div>

      {/* Running state */}
      {running && (
        <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-6 text-center mb-6">
          <div className="text-3xl mb-3 animate-pulse">{phase === 'trends' ? '🔍' : '🌐'}</div>
          {phase === 'trends' ? (
            <>
              <p className="text-[#e6edf3] font-medium">Step 1/2 · Collecting trend signals…</p>
              <p className="text-sm text-[#8b949e] mt-1">
                Hacker News · Reddit · Product Hunt · Google Trends · GitHub · YC · Crunchbase
              </p>
            </>
          ) : (
            <>
              <p className="text-[#e6edf3] font-medium">Step 2/2 · Finding & valuing domains…</p>
              <p className="text-sm text-[#8b949e] mt-1">
                Generating names → registrar availability → appraisal & ROI
              </p>
              {trendMeta && (
                <p className="text-xs text-[#6e7681] mt-2">{trends.length} trends found</p>
              )}
            </>
          )}
        </div>
      )}

      {/* Error */}
      {phase === 'error' && error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4 mb-6">
          <p className="text-red-400 text-sm font-medium">Hunt failed</p>
          <p className="text-red-300 text-sm mt-1 font-mono">{error}</p>
        </div>
      )}

      {/* Buy/sell guide — shown whenever there are results */}
      {phase === 'done' && <BuySellGuide />}

      {/* Results */}
      {phase === 'done' && domainMeta && (
        <>
          {/* Meta bar */}
          <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-[#161b22] border border-[#30363d] rounded-lg text-sm">
            <span className="text-[#8b949e]">
              <span className="text-[#e6edf3] font-medium">{domainMeta.generated}</span>{' '}
              generated →{' '}
              <span className="text-[#e6edf3] font-medium">{domainMeta.available}</span>{' '}
              available →{' '}
              <span className="text-[#e6edf3] font-medium">{domainMeta.appraised}</span>{' '}
              valued →{' '}
              <span className="text-blue-400 font-semibold">top {Math.min(TOP_N, top10.length)} by ROI</span>
            </span>
            <span className="text-[#30363d]">|</span>
            <span className="text-[#8b949e]">
              availability:{' '}
              <span className="text-[#e6edf3]">{domainMeta.availabilitySource}</span>
            </span>
            <span className="text-[#30363d]">|</span>
            <span className="text-[#8b949e]">
              valuation: <span className="text-[#e6edf3]">{domainMeta.valuationSource}</span>
            </span>
            {trendMeta && (
              <>
                <span className="text-[#30363d]">|</span>
                <button
                  onClick={() => setShowTrends((s) => !s)}
                  className="text-[#58a6ff] hover:underline"
                >
                  {showTrends ? 'Hide' : 'Show'} {trends.length} source trends
                </button>
              </>
            )}
          </div>

          {/* Source trends */}
          {showTrends && (
            <div className="mb-4 p-3 bg-[#0d1117] border border-[#30363d] rounded-lg">
              <div className="flex flex-wrap gap-2">
                {trends.map((t) => (
                  <span
                    key={t.name}
                    className={`text-xs px-2 py-0.5 rounded border ${VELOCITY_COLORS[t.velocity]}`}
                  >
                    {VELOCITY_ICONS[t.velocity]} {t.name} ({t.commercialScore})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Top 10 domain cards */}
          {top10.length > 0 ? (
            <div className="flex flex-col gap-3">
              {top10.map((d, i) => (
                <DomainCard key={d.domain} d={d} rank={i + 1} />
              ))}
            </div>
          ) : (
            <p className="text-[#6e7681] text-center py-12">
              No available domains found this run — try again, generation varies each time.
            </p>
          )}
        </>
      )}

      {/* Idle state */}
      {phase === 'idle' && (
        <>
          <BuySellGuide />
          <div className="border border-dashed border-[#30363d] rounded-lg p-12 text-center">
            <p className="text-[#6e7681] text-sm">
              Press Run Hunt — finds trends, generates domain names, confirms availability, and
              ranks the top {TOP_N} by ROI.
            </p>
            <p className="text-xs text-[#484f58] mt-2">
              Requires ANTHROPIC_API_KEY. GODADDY_API_KEY/SECRET enables registrar-confirmed
              availability and GoValue appraisals.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
