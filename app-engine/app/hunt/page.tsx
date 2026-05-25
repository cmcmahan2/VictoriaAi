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

const VELOCITY_COLORS = {
  rising: 'text-green-400 bg-green-400/10 border-green-400/30',
  peak: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  declining: 'text-red-400 bg-red-400/10 border-red-400/30',
} as const;

const VELOCITY_ICONS = {
  rising: '↑',
  peak: '→',
  declining: '↓',
} as const;

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? 'text-green-400' : score >= 40 ? 'text-yellow-400' : 'text-red-400';
  return (
    <span className={`text-lg font-bold tabular-nums ${color}`}>{score}</span>
  );
}

function TrendCard({ trend, rank }: { trend: Trend; rank: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 hover:border-[#484f58] transition-colors cursor-pointer"
      onClick={() => setExpanded((e) => !e)}
    >
      <div className="flex items-start gap-4">
        <span className="text-[#6e7681] text-sm w-6 text-right shrink-0 pt-0.5">#{rank}</span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-[#e6edf3] font-semibold">{trend.name}</h3>
            <span
              className={`text-xs px-2 py-0.5 rounded border ${VELOCITY_COLORS[trend.velocity]}`}
            >
              {VELOCITY_ICONS[trend.velocity]} {trend.velocity}
            </span>
          </div>

          {trend.summary && (
            <p className="text-[#8b949e] text-sm mt-1 leading-snug">{trend.summary}</p>
          )}

          <div className="flex flex-wrap gap-1.5 mt-2">
            {trend.keywords.slice(0, 5).map((kw) => (
              <span
                key={kw}
                className="text-xs px-2 py-0.5 bg-[#1c2128] border border-[#30363d] rounded text-[#58a6ff]"
              >
                {kw}
              </span>
            ))}
          </div>

          {expanded && (
            <div className="mt-3 pt-3 border-t border-[#30363d]">
              <p className="text-xs text-[#6e7681] mb-1">Sources</p>
              <div className="flex flex-wrap gap-1">
                {trend.sources.map((s) => (
                  <span key={s} className="text-xs px-1.5 py-0.5 bg-[#0d1117] rounded text-[#6e7681]">
                    {s}
                  </span>
                ))}
              </div>
              {trend.keywords.length > 5 && (
                <>
                  <p className="text-xs text-[#6e7681] mt-2 mb-1">All keywords</p>
                  <div className="flex flex-wrap gap-1">
                    {trend.keywords.map((kw) => (
                      <span key={kw} className="text-xs px-1.5 py-0.5 bg-[#1c2128] rounded text-[#58a6ff]">
                        {kw}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="shrink-0 text-right">
          <ScoreBadge score={trend.commercialScore} />
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
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [trends, setTrends] = useState<Trend[]>([]);
  const [meta, setMeta] = useState<RunMeta | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runHunt() {
    setStatus('running');
    setError(null);
    setTrends([]);
    setMeta(null);

    try {
      const res = await fetch('/api/trends', { method: 'POST' });
      const data = await res.json() as { ok: boolean; trends?: Trend[]; meta?: RunMeta; error?: string };

      if (!data.ok) throw new Error(data.error || 'Hunt failed');

      setTrends(data.trends || []);
      setMeta(data.meta || null);
      setStatus('done');
    } catch (err) {
      setError((err as Error).message);
      setStatus('error');
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#e6edf3]">Trend Hunt</h1>
          <p className="text-sm text-[#8b949e] mt-0.5">
            Aggregate signals from 7 sources → Claude scores commercial domain potential
          </p>
        </div>

        <button
          onClick={runHunt}
          disabled={status === 'running'}
          className={`
            px-5 py-2 rounded-md text-sm font-medium transition-all
            ${status === 'running'
              ? 'bg-[#1c2128] text-[#6e7681] cursor-not-allowed'
              : 'bg-[#238636] hover:bg-[#2ea043] text-white cursor-pointer'
            }
          `}
        >
          {status === 'running' ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin">⟳</span> Running…
            </span>
          ) : (
            '▶ Run Hunt'
          )}
        </button>
      </div>

      {/* Running state */}
      {status === 'running' && (
        <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-6 text-center mb-6">
          <div className="text-3xl mb-3 animate-pulse-soft">🔍</div>
          <p className="text-[#e6edf3] font-medium">Collecting signals…</p>
          <p className="text-sm text-[#8b949e] mt-1">
            Hacker News · Reddit · Product Hunt · Google Trends · GitHub · YC · Crunchbase
          </p>
          <p className="text-sm text-[#6e7681] mt-2">Then Claude scores commercial potential. ~30–90s</p>
        </div>
      )}

      {/* Error state */}
      {status === 'error' && error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4 mb-6">
          <p className="text-red-400 text-sm font-medium">Hunt failed</p>
          <p className="text-red-300 text-sm mt-1 font-mono">{error}</p>
        </div>
      )}

      {/* Results */}
      {status === 'done' && meta && (
        <>
          {/* Meta strip */}
          <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-[#161b22] border border-[#30363d] rounded-lg">
            <span className="text-sm text-[#8b949e]">
              <span className="text-[#e6edf3] font-medium">{meta.signalCount}</span> signals →{' '}
              <span className="text-[#e6edf3] font-medium">{trends.length}</span> trends in{' '}
              <span className="text-[#e6edf3] font-medium">{(meta.durationMs / 1000).toFixed(1)}s</span>
            </span>
            <span className="text-[#30363d]">|</span>
            {Object.entries(meta.sourceBreakdown).map(([src, count]) => (
              <SourceChip key={src} label={src} count={count} />
            ))}
          </div>

          {/* Trend cards */}
          <div className="flex flex-col gap-2">
            {trends.map((trend, i) => (
              <TrendCard key={trend.name} trend={trend} rank={i + 1} />
            ))}
          </div>

          {trends.length === 0 && (
            <p className="text-[#6e7681] text-center py-12">No trends returned. Check your ANTHROPIC_API_KEY.</p>
          )}
        </>
      )}

      {/* Idle state hint */}
      {status === 'idle' && (
        <div className="border border-dashed border-[#30363d] rounded-lg p-12 text-center">
          <p className="text-[#6e7681] text-sm">Press Run Hunt to start collecting trend signals</p>
          <p className="text-xs text-[#484f58] mt-2">
            Requires ANTHROPIC_API_KEY. Reddit, Product Hunt, and YC batch sources are optional.
          </p>
        </div>
      )}
    </div>
  );
}
