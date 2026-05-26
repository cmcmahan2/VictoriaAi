'use client';

import { useState, useEffect } from 'react';

// Sonnet pricing (per million tokens)
const INPUT_PRICE_PER_M = 3.0;
const OUTPUT_PRICE_PER_M = 15.0;

function calcCost(inputTokens: number, outputTokens: number): number {
  return (inputTokens / 1_000_000) * INPUT_PRICE_PER_M + (outputTokens / 1_000_000) * OUTPUT_PRICE_PER_M;
}

const USAGE_KEY = 'victoria_token_usage';
type CumulativeUsage = { inputTokens: number; outputTokens: number; runs: number };

function loadUsage(): CumulativeUsage {
  if (typeof window === 'undefined') return { inputTokens: 0, outputTokens: 0, runs: 0 };
  try { return JSON.parse(localStorage.getItem(USAGE_KEY) || 'null') ?? { inputTokens: 0, outputTokens: 0, runs: 0 }; }
  catch { return { inputTokens: 0, outputTokens: 0, runs: 0 }; }
}

function saveUsage(u: CumulativeUsage) { localStorage.setItem(USAGE_KEY, JSON.stringify(u)); }

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
  usage?: { inputTokens: number; outputTokens: number };
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

type DomainMeta = {
  generated: number;
  checked: number;
  available: number;
  appraised: number;
  durationMs: number;
  valuationSource: 'godaddy' | 'claude' | 'mixed';
};

type Phase = 'idle' | 'trends' | 'domains' | 'done' | 'error';

const VELOCITY_COLORS = {
  rising: 'text-green-400 bg-green-400/10 border-green-400/30',
  peak: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  declining: 'text-red-400 bg-red-400/10 border-red-400/30',
} as const;

const VELOCITY_ICONS = { rising: '↑', peak: '→', declining: '↓' } as const;

function usd(n: number): string {
  return '$' + Math.round(n).toLocaleString();
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? 'text-green-400' : score >= 40 ? 'text-yellow-400' : 'text-red-400';
  return <span className={`text-lg font-bold tabular-nums ${color}`}>{score}</span>;
}

const GODADDY_URL = (domain: string) =>
  `https://www.godaddy.com/domainsearch/find?domainToCheck=${encodeURIComponent(domain)}`;
const AFTERNIC_URL = (domain: string) =>
  `https://www.afternic.com/forsale/${encodeURIComponent(domain)}`;

function DomainCard({ d, rank }: { d: DomainResult; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const sellColor =
    d.sellability >= 70 ? 'text-green-400' : d.sellability >= 40 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div
      className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 hover:border-[#484f58] transition-colors cursor-pointer"
      onClick={() => setExpanded((e) => !e)}
    >
      <div className="flex items-start gap-4">
        <span className="text-[#6e7681] text-sm w-6 text-right shrink-0 pt-0.5">#{rank}</span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-[#e6edf3] font-semibold font-mono">{d.domain}</h3>
            <span className="text-xs px-2 py-0.5 rounded border border-[#30363d] text-[#8b949e]">
              {d.strategy}
            </span>
            <span className="text-xs px-2 py-0.5 rounded border border-green-400/30 text-green-400 bg-green-400/10">
              available
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm">
            <span className="text-[#8b949e]">
              Value <span className="text-[#e6edf3] font-medium">{usd(d.valueMedian)}</span>
              <span className="text-[#6e7681]"> ({usd(d.valueLow)}–{usd(d.valueHigh)})</span>
            </span>
            <span className="text-[#8b949e]">
              Buy <span className="text-[#e6edf3] font-medium">{usd(d.estPrice)}/yr</span>
            </span>
            <span className="text-[#8b949e]">
              ROI <span className="text-[#e6edf3] font-medium">{d.roi}x</span>
            </span>
            <span className="text-[#8b949e]">
              Sell <span className={`font-medium ${sellColor}`}>{d.sellability}</span>
            </span>
          </div>

          {expanded && (
            <div className="mt-3 pt-3 border-t border-[#30363d] space-y-2">
              <p className="text-sm text-[#8b949e]">{d.reasoning}</p>
              <p className="text-xs text-[#6e7681]">
                Likely buyers: <span className="text-[#58a6ff]">{d.buyers}</span>
              </p>
              <p className="text-xs text-[#6e7681]">
                From trend: <span className="text-[#e6edf3]">{d.basis || '—'}</span> · valuation by{' '}
                <span className="text-[#e6edf3]">{d.valueSource}</span>
              </p>
              {/* Quick-action links — open in new tab, stop card toggle */}
              <div className="flex gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
                <a
                  href={GODADDY_URL(d.domain)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs px-3 py-1 rounded bg-[#238636] hover:bg-[#2ea043] text-white font-medium transition-colors"
                >
                  Buy on GoDaddy ↗
                </a>
                <a
                  href={AFTERNIC_URL(d.domain)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs px-3 py-1 rounded border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors"
                >
                  List on Afternic ↗
                </a>
              </div>
            </div>
          )}
        </div>

        <div className="shrink-0 text-right">
          <ScoreBadge score={d.score} />
          <p className="text-xs text-[#6e7681] mt-0.5">score</p>
        </div>
      </div>
    </div>
  );
}

function SourceChip({ label, count }: { label: string; count: number }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-[#1c2128] border border-[#30363d] rounded text-xs text-[#8b949e]">
      <span className="text-[#e6edf3]">{count}</span> {label}
    </span>
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
  const [cumulative, setCumulative] = useState<CumulativeUsage>({ inputTokens: 0, outputTokens: 0, runs: 0 });
  const [lastRunTokens, setLastRunTokens] = useState<{ inputTokens: number; outputTokens: number } | null>(null);

  useEffect(() => { setCumulative(loadUsage()); }, []);

  const running = phase === 'trends' || phase === 'domains';

  async function runHunt() {
    setError(null);
    setTrends([]);
    setTrendMeta(null);
    setDomains([]);
    setDomainMeta(null);
    setLastRunTokens(null);

    try {
      // Phase 1 — trends
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

      // Phase 2 — domains
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
        usage?: { inputTokens: number; outputTokens: number };
        error?: string;
      };
      if (!dData.ok) throw new Error(dData.error || 'Domain hunt failed');
      setDomains(dData.domains || []);
      setDomainMeta(dData.meta || null);

      // Aggregate token usage across both phases and persist
      const tIn = tData.meta?.usage?.inputTokens ?? 0;
      const tOut = tData.meta?.usage?.outputTokens ?? 0;
      const dIn = dData.usage?.inputTokens ?? 0;
      const dOut = dData.usage?.outputTokens ?? 0;
      const runTokens = { inputTokens: tIn + dIn, outputTokens: tOut + dOut };
      setLastRunTokens(runTokens);
      const prev = loadUsage();
      const next: CumulativeUsage = {
        inputTokens: prev.inputTokens + runTokens.inputTokens,
        outputTokens: prev.outputTokens + runTokens.outputTokens,
        runs: prev.runs + 1,
      };
      saveUsage(next);
      setCumulative(next);

      setPhase('done');
    } catch (err) {
      setError((err as Error).message);
      setPhase('error');
    }
  }

  return (
    <div className="p-3 md:p-6 max-w-4xl mx-auto">
      {/* Token usage tracker */}
      {(cumulative.runs > 0 || lastRunTokens) && (
        <div className="flex flex-wrap gap-3 mb-4 text-xs text-[#6e7681]">
          {lastRunTokens && (
            <span className="px-2 py-1 bg-[#161b22] border border-[#30363d] rounded">
              Last run:{' '}
              <span className="text-[#e6edf3]">
                {(lastRunTokens.inputTokens + lastRunTokens.outputTokens).toLocaleString()} tokens
              </span>
              {' '}≈{' '}
              <span className="text-yellow-400">
                ${calcCost(lastRunTokens.inputTokens, lastRunTokens.outputTokens).toFixed(3)}
              </span>
            </span>
          )}
          <span className="px-2 py-1 bg-[#161b22] border border-[#30363d] rounded">
            All-time ({cumulative.runs} run{cumulative.runs !== 1 ? 's' : ''}):{' '}
            <span className="text-[#e6edf3]">
              {(cumulative.inputTokens + cumulative.outputTokens).toLocaleString()} tokens
            </span>
            {' '}≈{' '}
            <span className="text-yellow-400">
              ${calcCost(cumulative.inputTokens, cumulative.outputTokens).toFixed(2)} spent
            </span>
          </span>
          <button
            onClick={() => { saveUsage({ inputTokens: 0, outputTokens: 0, runs: 0 }); setCumulative({ inputTokens: 0, outputTokens: 0, runs: 0 }); }}
            className="px-2 py-1 text-[#484f58] hover:text-[#6e7681] transition-colors"
          >
            reset
          </button>
        </div>
      )}

      <div className="flex items-start justify-between mb-6 gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-[#e6edf3]">Domain Hunt</h1>
          <p className="text-xs md:text-sm text-[#8b949e] mt-0.5 leading-snug">
            7 sources → trends → generate names → check availability → value & score
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
                Generating names → RDAP availability → appraisal & sellability
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

      {/* Results */}
      {phase === 'done' && domainMeta && (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-[#161b22] border border-[#30363d] rounded-lg">
            <span className="text-sm text-[#8b949e]">
              <span className="text-[#e6edf3] font-medium">{domainMeta.generated}</span> generated →{' '}
              <span className="text-[#e6edf3] font-medium">{domainMeta.available}</span> available →{' '}
              <span className="text-[#e6edf3] font-medium">{domainMeta.appraised}</span> valued
            </span>
            <span className="text-[#30363d]">|</span>
            <span className="text-sm text-[#8b949e]">
              valuation: <span className="text-[#e6edf3]">{domainMeta.valuationSource}</span>
            </span>
            {trendMeta && (
              <>
                <span className="text-[#30363d]">|</span>
                <button
                  onClick={() => setShowTrends((s) => !s)}
                  className="text-sm text-[#58a6ff] hover:underline"
                >
                  {showTrends ? 'Hide' : 'Show'} {trends.length} source trends
                </button>
              </>
            )}
          </div>

          {/* Source trends (collapsible) */}
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

          {/* Domain list — the deliverable */}
          <div className="flex flex-col gap-2">
            {domains.map((d, i) => (
              <DomainCard key={d.domain} d={d} rank={i + 1} />
            ))}
          </div>

          {domains.length === 0 && (
            <p className="text-[#6e7681] text-center py-12">
              No available domains found this run. Try again — generation varies each time.
            </p>
          )}
        </>
      )}

      {/* Idle */}
      {phase === 'idle' && (
        <div className="border border-dashed border-[#30363d] rounded-lg p-12 text-center">
          <p className="text-[#6e7681] text-sm">
            Press Run Hunt — it finds trends, generates domain names, checks availability, and values them.
          </p>
          <p className="text-xs text-[#484f58] mt-2">
            Requires ANTHROPIC_API_KEY. GODADDY_API_KEY/SECRET enables GoValue appraisals (optional).
          </p>
        </div>
      )}
    </div>
  );
}
