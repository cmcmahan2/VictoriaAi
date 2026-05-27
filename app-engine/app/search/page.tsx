'use client';

import { useState, useRef } from 'react';

type SearchResult = {
  domain: string;
  sld: string;
  tld: string;
  available: boolean;
  price: number;
  tier: 'budget' | 'standard' | 'premium';
  registerUrl: string;
};

const TIER_COLORS = {
  budget:   'text-green-400 border-green-400/30 bg-green-400/10',
  standard: 'text-[#8b949e] border-[#30363d] bg-transparent',
  premium:  'text-yellow-400 border-yellow-400/30 bg-yellow-400/10',
} as const;

function usd(n: number) {
  return `$${n}/yr`;
}

function DomainRow({ r }: { r: SearchResult }) {
  const avail = r.available;
  return (
    <div className={`flex items-center justify-between px-4 py-3 border-b border-[#21262d] last:border-0 ${avail ? '' : 'opacity-40'}`}>
      <div className="flex items-center gap-3 min-w-0">
        <span className={`shrink-0 text-xs w-2 h-2 rounded-full ${avail ? 'bg-green-400' : 'bg-[#484f58]'}`} />
        <span className="font-mono text-sm text-[#e6edf3] truncate">{r.domain}</span>
        <span className={`shrink-0 text-xs px-1.5 py-0.5 rounded border ${TIER_COLORS[r.tier]}`}>
          {r.tier}
        </span>
      </div>
      <div className="flex items-center gap-4 shrink-0 ml-4">
        <span className="text-sm text-[#8b949e] tabular-nums">{usd(r.price)}</span>
        {avail ? (
          <a
            href={r.registerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm px-3 py-1 rounded bg-[#238636] hover:bg-[#2ea043] text-white transition-colors"
          >
            Register ↗
          </a>
        ) : (
          <span className="text-sm px-3 py-1 rounded border border-[#30363d] text-[#484f58]">Taken</span>
        )}
      </div>
    </div>
  );
}

function FilterBar({
  filter,
  onChange,
  availCount,
  total,
}: {
  filter: 'all' | 'available';
  onChange: (f: 'all' | 'available') => void;
  availCount: number;
  total: number;
}) {
  return (
    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#30363d] bg-[#0d1117]">
      <button
        onClick={() => onChange('available')}
        className={`text-xs px-2.5 py-1 rounded border transition-colors ${
          filter === 'available'
            ? 'border-green-400/40 bg-green-400/10 text-green-400'
            : 'border-[#30363d] text-[#8b949e] hover:border-[#484f58]'
        }`}
      >
        Available ({availCount})
      </button>
      <button
        onClick={() => onChange('all')}
        className={`text-xs px-2.5 py-1 rounded border transition-colors ${
          filter === 'all'
            ? 'border-[#58a6ff]/40 bg-[#58a6ff]/10 text-[#58a6ff]'
            : 'border-[#30363d] text-[#8b949e] hover:border-[#484f58]'
        }`}
      >
        All ({total})
      </button>
    </div>
  );
}

export default function SearchPage() {
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searchedFor, setSearchedFor] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'available'>('available');
  const inputRef = useRef<HTMLInputElement>(null);

  async function runSearch(kw?: string) {
    const q = (kw ?? keyword).trim();
    if (!q || loading) return;

    setLoading(true);
    setError(null);
    setResults(null);
    setFilter('available');

    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: q }),
      });
      const data = (await res.json()) as { ok: boolean; results?: SearchResult[]; keyword?: string; error?: string };
      if (!data.ok) {
        setError(data.error ?? 'Search failed.');
      } else {
        setResults(data.results ?? []);
        setSearchedFor(data.keyword ?? q);
      }
    } catch {
      setError('Could not reach the search endpoint.');
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') runSearch();
  }

  const visible = results
    ? filter === 'available'
      ? results.filter((r) => r.available)
      : results
    : [];
  const availCount = results?.filter((r) => r.available).length ?? 0;

  // Quick-search chips
  const suggestions = ['mystore', 'aitools', 'portfolio', 'launchpad', 'devhub'];

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold text-[#e6edf3] mb-1">Domain Search</h1>
      <p className="text-sm text-[#8b949e] mb-6">
        Enter a keyword — we check availability across budget and premium TLDs and link you straight to registration.
      </p>

      {/* Search box */}
      <div className="flex gap-2 mb-4">
        <input
          ref={inputRef}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="e.g. aitools, mystore, launchpad…"
          className="flex-1 px-4 py-2.5 rounded-md bg-[#0d1117] border border-[#30363d] text-[#e6edf3] text-sm placeholder-[#484f58] focus:outline-none focus:border-[#58a6ff] transition-colors"
        />
        <button
          onClick={() => runSearch()}
          disabled={loading || !keyword.trim()}
          className={`px-5 py-2 rounded-md text-sm font-medium transition-all shrink-0 ${
            loading || !keyword.trim()
              ? 'bg-[#1c2128] text-[#6e7681] cursor-not-allowed'
              : 'bg-[#238636] hover:bg-[#2ea043] text-white cursor-pointer'
          }`}
        >
          {loading ? <span className="animate-spin inline-block">⟳</span> : 'Search'}
        </button>
      </div>

      {/* Quick suggestions */}
      {!results && !loading && (
        <div className="flex flex-wrap gap-2 mb-6">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => { setKeyword(s); runSearch(s); }}
              className="text-xs px-2.5 py-1 rounded border border-[#30363d] text-[#8b949e] hover:border-[#484f58] hover:text-[#e6edf3] transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-8 text-center">
          <p className="text-[#e6edf3] font-medium animate-pulse">Checking availability…</p>
          <p className="text-sm text-[#8b949e] mt-1">Querying RDAP for each domain — takes ~5s</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Results */}
      {results && !loading && (
        <>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-[#8b949e]">
              Results for <span className="text-[#e6edf3] font-medium font-mono">{searchedFor}</span>
              {' '}— <span className="text-green-400">{availCount} available</span> of {results.length} checked
            </p>
            <button
              onClick={() => { setResults(null); setKeyword(''); setTimeout(() => inputRef.current?.focus(), 50); }}
              className="text-xs text-[#6e7681] hover:text-[#8b949e]"
            >
              ✕ Clear
            </button>
          </div>

          <div className="bg-[#161b22] border border-[#30363d] rounded-lg overflow-hidden">
            <FilterBar filter={filter} onChange={setFilter} availCount={availCount} total={results.length} />

            {visible.length === 0 ? (
              <p className="text-center text-[#6e7681] text-sm py-10">
                {filter === 'available'
                  ? 'No available domains found. Try the "All" view or a different keyword.'
                  : 'No results.'}
              </p>
            ) : (
              <div>
                {visible.map((r) => (
                  <DomainRow key={r.domain} r={r} />
                ))}
              </div>
            )}
          </div>

          {/* Price legend */}
          <div className="flex gap-4 mt-3 text-xs text-[#6e7681]">
            <span className="flex items-center gap-1"><span className="text-green-400">■</span> Budget (≤$5/yr)</span>
            <span className="flex items-center gap-1"><span className="text-[#8b949e]">■</span> Standard ($10–$20/yr)</span>
            <span className="flex items-center gap-1"><span className="text-yellow-400">■</span> Premium ($30+/yr)</span>
          </div>
        </>
      )}
    </div>
  );
}
