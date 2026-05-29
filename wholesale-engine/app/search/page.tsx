'use client';

import { useState, useMemo, useCallback } from 'react';
import { Search, SlidersHorizontal, Building2, TrendingUp, DollarSign, AlertTriangle, ChevronDown, ChevronUp, X } from 'lucide-react';
import { cn, formatCurrency, scoreColor, scoreLabel } from '@/lib/utils';
import type { DealAnalysis } from '@/modules/deals/analysis';
import type { SearchQuery, PropertyType } from '@/modules/properties/types';

type SearchResult = {
  analyses: DealAnalysis[];
  marketSummary: {
    totalProperties: number;
    hotDeals: number;
    potentialDeals: number;
    avgWholesaleScore: number;
    avgEquitySpread: number;
    medianListPrice: number;
    topDistressSignals: string[];
  };
  meta: {
    market: string;
    propertyCount: number;
    sources: Record<string, number>;
    usedMock: boolean;
    hasClaude: boolean;
    durationMs: number;
  };
};

type LocalFilters = {
  minPrice: string;
  maxPrice: string;
  minBedrooms: string;
  maxDom: string;
  propertyTypes: PropertyType[];
  onlyDeals: boolean;
  minScore: string;
};

const DEFAULT_FILTERS: LocalFilters = {
  minPrice: '',
  maxPrice: '',
  minBedrooms: '',
  maxDom: '',
  propertyTypes: [],
  onlyDeals: false,
  minScore: '',
};

const PROPERTY_TYPES: PropertyType[] = ['SFR', 'MFR', 'Condo', 'Townhouse', 'Land'];

const POPULAR_MARKETS = [
  'Memphis, TN', 'Detroit, MI', 'Cleveland, OH', 'Baltimore, MD',
  'Kansas City, MO', 'Indianapolis, IN', 'Birmingham, AL', 'St. Louis, MO',
];

export default function SearchPage() {
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [filters, setFilters] = useState<LocalFilters>(DEFAULT_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const runSearch = useCallback(async (market: string) => {
    if (!market.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const isZips = /^\d{5}/.test(market.trim());
    const query: SearchQuery = isZips
      ? { zipCodes: market.split(',').map(z => z.trim()).filter(Boolean) }
      : { market: market.trim() };

    try {
      const res = await fetch('/api/properties', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(query),
      });
      const data = (await res.json()) as SearchResult & { ok: boolean; error?: string };
      if (!data.ok) throw new Error(data.error ?? 'Search failed');
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void runSearch(searchInput);
  };

  // Client-side filtering — no new API call needed
  const filteredAnalyses = useMemo(() => {
    if (!result) return [];
    return result.analyses.filter(a => {
      const p = a.property;
      if (filters.minPrice && p.price < Number(filters.minPrice)) return false;
      if (filters.maxPrice && p.price > Number(filters.maxPrice)) return false;
      if (filters.minBedrooms && p.bedrooms < Number(filters.minBedrooms)) return false;
      if (filters.maxDom && p.daysOnMarket > Number(filters.maxDom)) return false;
      if (filters.propertyTypes.length > 0 && !filters.propertyTypes.includes(p.propertyType)) return false;
      if (filters.onlyDeals && !a.isViableDeal) return false;
      if (filters.minScore && a.wholesaleScore < Number(filters.minScore)) return false;
      return true;
    }).sort((a, b) => b.wholesaleScore - a.wholesaleScore);
  }, [result, filters]);

  const hasActiveFilters = Object.entries(filters).some(([k, v]) => {
    if (k === 'propertyTypes') return (v as PropertyType[]).length > 0;
    if (k === 'onlyDeals') return v === true;
    return v !== '';
  });

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-[#161b22]">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Building2 className="w-6 h-6 text-green-400" />
            <span className="font-bold text-lg tracking-tight">Wholesale Engine</span>
            <span className="text-xs text-gray-500 border border-gray-700 rounded px-2 py-0.5">beta</span>
          </div>
          <span className="text-xs text-gray-500">AI-powered wholesale deal finder</span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Search Bar */}
        <div className="mb-8">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                placeholder="Memphis, TN — or — 38103, 38104, 38105"
                className="w-full pl-10 pr-4 py-3 bg-[#161b22] border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !searchInput.trim()}
              className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-semibold transition-colors"
            >
              {loading ? 'Searching…' : 'Find Deals'}
            </button>
          </form>

          {/* Popular markets */}
          {!result && !loading && (
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="text-xs text-gray-500 py-1">Try:</span>
              {POPULAR_MARKETS.map(m => (
                <button
                  key={m}
                  onClick={() => { setSearchInput(m); void runSearch(m); }}
                  className="text-xs px-3 py-1 bg-[#161b22] border border-gray-700 hover:border-gray-500 rounded-full text-gray-400 hover:text-gray-200 transition-colors"
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-700/50 rounded-lg text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-500 text-sm">Searching properties and scoring deals…</p>
          </div>
        )}

        {result && (
          <div className="flex gap-6">
            {/* Filter Sidebar */}
            <aside className="w-64 shrink-0 hidden lg:block">
              <div className="bg-[#161b22] border border-gray-800 rounded-lg p-4 sticky top-4">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                    <SlidersHorizontal className="w-4 h-4" /> Filters
                  </span>
                  {hasActiveFilters && (
                    <button onClick={() => setFilters(DEFAULT_FILTERS)} className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1">
                      <X className="w-3 h-3" /> Clear
                    </button>
                  )}
                </div>

                <div className="space-y-4">
                  {/* Min wholesale score */}
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Min Deal Score</label>
                    <select
                      value={filters.minScore}
                      onChange={e => setFilters(f => ({ ...f, minScore: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-green-500"
                    >
                      <option value="">Any</option>
                      <option value="75">75+ (Hot Deals)</option>
                      <option value="50">50+ (Potential)</option>
                      <option value="25">25+</option>
                    </select>
                  </div>

                  {/* Price range */}
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Price Range</label>
                    <div className="flex gap-2">
                      <input
                        type="number"
                        placeholder="Min"
                        value={filters.minPrice}
                        onChange={e => setFilters(f => ({ ...f, minPrice: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 placeholder-gray-600 focus:outline-none focus:border-green-500"
                      />
                      <input
                        type="number"
                        placeholder="Max"
                        value={filters.maxPrice}
                        onChange={e => setFilters(f => ({ ...f, maxPrice: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 placeholder-gray-600 focus:outline-none focus:border-green-500"
                      />
                    </div>
                  </div>

                  {/* Bedrooms */}
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Min Bedrooms</label>
                    <select
                      value={filters.minBedrooms}
                      onChange={e => setFilters(f => ({ ...f, minBedrooms: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-green-500"
                    >
                      <option value="">Any</option>
                      <option value="2">2+</option>
                      <option value="3">3+</option>
                      <option value="4">4+</option>
                    </select>
                  </div>

                  {/* Days on market */}
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Max Days on Market</label>
                    <select
                      value={filters.maxDom}
                      onChange={e => setFilters(f => ({ ...f, maxDom: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-green-500"
                    >
                      <option value="">Any</option>
                      <option value="30">30 days</option>
                      <option value="60">60 days</option>
                      <option value="90">90 days</option>
                      <option value="180">180 days</option>
                    </select>
                  </div>

                  {/* Property types */}
                  <div>
                    <label className="text-xs text-gray-500 mb-2 block">Property Type</label>
                    <div className="space-y-1.5">
                      {PROPERTY_TYPES.map(type => (
                        <label key={type} className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={filters.propertyTypes.includes(type)}
                            onChange={e => setFilters(f => ({
                              ...f,
                              propertyTypes: e.target.checked
                                ? [...f.propertyTypes, type]
                                : f.propertyTypes.filter(t => t !== type),
                            }))}
                            className="accent-green-500"
                          />
                          <span className="text-sm text-gray-400">{type}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Only viable deals */}
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={filters.onlyDeals}
                      onChange={e => setFilters(f => ({ ...f, onlyDeals: e.target.checked }))}
                      className="accent-green-500"
                    />
                    <span className="text-sm text-gray-400">Viable deals only</span>
                  </label>
                </div>
              </div>
            </aside>

            {/* Main content */}
            <div className="flex-1 min-w-0">
              {/* Mobile filter toggle */}
              <button
                onClick={() => setFiltersOpen(f => !f)}
                className="lg:hidden mb-4 flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200"
              >
                <SlidersHorizontal className="w-4 h-4" />
                Filters {hasActiveFilters && <span className="text-green-400">(active)</span>}
                {filtersOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>

              {/* Market Summary */}
              <MarketSummaryPanel summary={result.marketSummary} meta={result.meta} />

              {/* Results count */}
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-gray-500">
                  {filteredAnalyses.length} properties
                  {filteredAnalyses.length !== result.analyses.length && ` (filtered from ${result.analyses.length})`}
                  {' '}· sorted by deal score
                </p>
                {result.meta.usedMock && (
                  <span className="text-xs px-2 py-0.5 bg-yellow-400/10 border border-yellow-400/30 text-yellow-400 rounded">
                    Demo data — add API keys for live results
                  </span>
                )}
              </div>

              {/* Property Cards */}
              {filteredAnalyses.length === 0 ? (
                <div className="py-16 text-center text-gray-500">
                  <Building2 className="w-8 h-8 mx-auto mb-3 opacity-30" />
                  <p>No properties match your filters.</p>
                  <button onClick={() => setFilters(DEFAULT_FILTERS)} className="mt-2 text-green-400 hover:text-green-300 text-sm">
                    Clear filters
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {filteredAnalyses.map(analysis => (
                    <PropertyCard
                      key={analysis.property.id}
                      analysis={analysis}
                      expanded={expandedId === analysis.property.id}
                      onToggle={() => setExpandedId(id => id === analysis.property.id ? null : analysis.property.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!result && !loading && !error && (
          <div className="text-center py-24">
            <Building2 className="w-12 h-12 mx-auto mb-4 text-gray-700" />
            <h2 className="text-xl font-semibold text-gray-400 mb-2">Find Wholesale Deals</h2>
            <p className="text-gray-600 max-w-md mx-auto text-sm">
              Enter a US city/state or zip codes. Our AI scores every property for wholesale potential using ARV analysis, distress signals, and market momentum.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

function MarketSummaryPanel({
  summary,
  meta,
}: {
  summary: SearchResult['marketSummary'];
  meta: SearchResult['meta'];
}) {
  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-lg p-4 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-green-400" />
          {meta.market}
        </h2>
        <span className="text-xs text-gray-600">{meta.durationMs}ms</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Hot Deals" value={String(summary.hotDeals)} sub="Score 75+" highlight={summary.hotDeals > 0} />
        <Stat label="Potential" value={String(summary.potentialDeals)} sub="Score 50-74" />
        <Stat label="Avg Score" value={String(summary.avgWholesaleScore)} sub="Wholesale index" />
        <Stat label="Avg Equity" value={formatCurrency(summary.avgEquitySpread)} sub="ARV − list price" highlight={summary.avgEquitySpread > 0} />
      </div>
      {summary.topDistressSignals.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {summary.topDistressSignals.map(sig => (
            <span key={sig} className="text-xs px-2 py-0.5 bg-orange-400/10 border border-orange-400/20 text-orange-400 rounded">
              {sig}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, sub, highlight }: { label: string; value: string; sub: string; highlight?: boolean }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={cn('text-lg font-bold', highlight ? 'text-green-400' : 'text-gray-200')}>{value}</p>
      <p className="text-xs text-gray-600">{sub}</p>
    </div>
  );
}

function PropertyCard({
  analysis,
  expanded,
  onToggle,
}: {
  analysis: DealAnalysis;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { property: p } = analysis;
  const scoreClass = scoreColor(analysis.wholesaleScore);

  return (
    <div
      className={cn(
        'bg-[#161b22] border rounded-lg p-4 cursor-pointer transition-all',
        expanded ? 'border-green-600/50' : 'border-gray-800 hover:border-gray-600',
      )}
      onClick={onToggle}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-200 truncate">{p.address}</p>
          <p className="text-xs text-gray-500">{p.city}, {p.state} {p.zip}</p>
        </div>
        <div className={cn('shrink-0 px-2.5 py-1 rounded border text-xs font-bold', scoreClass)}>
          {analysis.wholesaleScore} · {scoreLabel(analysis.wholesaleScore)}
        </div>
      </div>

      {/* Key metrics row */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <MetricBox label="List Price" value={formatCurrency(p.price)} />
        <MetricBox
          label="MAO"
          value={formatCurrency(analysis.mao)}
          highlight={analysis.mao > p.price}
          dim={analysis.mao <= 0}
        />
        <MetricBox
          label="Profit @ List"
          value={formatCurrency(analysis.projectedProfit)}
          highlight={analysis.projectedProfit > 0}
          dim={analysis.projectedProfit < 0}
          prefix={analysis.projectedProfit > 0 ? '+' : ''}
        />
      </div>

      {/* Property details */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mb-3">
        <span>{p.bedrooms}bd / {p.bathrooms}ba</span>
        <span>{p.sqft.toLocaleString()} sqft</span>
        <span>Built {p.yearBuilt}</span>
        <span>{p.daysOnMarket}d on market</span>
        <span className="capitalize">{p.propertyType}</span>
        {p.source !== 'mock' && <span className="text-blue-400">{p.source}</span>}
      </div>

      {/* Distress signals */}
      {p.distressSignals.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {p.distressSignals.map(sig => (
            <span key={sig} className="text-xs px-1.5 py-0.5 bg-orange-400/10 border border-orange-400/20 text-orange-400 rounded">
              {sig}
            </span>
          ))}
        </div>
      )}

      {/* ARV confidence warning — shown on card face, not just expanded */}
      {analysis.arvConfidence === 'low' && (
        <p className="text-xs text-yellow-500/60 flex items-center gap-1 mb-2">
          <AlertTriangle className="w-3 h-3 shrink-0" /> ARV estimated — verify with comps
        </p>
      )}

      {/* Score summary */}
      {analysis.scoreSummary && (
        <p className="text-xs text-gray-500 italic border-t border-gray-800 pt-2 mb-2">
          {analysis.scoreSummary}
        </p>
      )}

      {/* Expanded deal breakdown */}
      {expanded && (
        <div className="border-t border-gray-800 pt-3 mt-1" onClick={e => e.stopPropagation()}>
          <p className="text-xs font-semibold text-gray-400 mb-2 flex items-center gap-1">
            <DollarSign className="w-3 h-3" /> Deal Analysis
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <DetailRow label="ARV Estimate" value={formatCurrency(analysis.arvEstimate)} />
            <DetailRow label="ARV Confidence" value={analysis.arvConfidence} />
            <DetailRow label="Repair Estimate" value={formatCurrency(analysis.repairEstimate)} />
            <DetailRow label="MAO (70% Rule)" value={formatCurrency(analysis.mao)} />
            <DetailRow label="Equity Spread" value={formatCurrency(analysis.equitySpread)} positive={analysis.equitySpread > 0} />
            <DetailRow label="Profit @ List" value={formatCurrency(analysis.projectedProfit)} positive={analysis.projectedProfit > 0} />
          </div>
          <div className="grid grid-cols-4 gap-2 mt-3">
            <ScoreBar label="Wholesale" value={analysis.wholesaleScore} />
            <ScoreBar label="Distress" value={analysis.distressScore} />
            <ScoreBar label="Momentum" value={analysis.momentumScore} />
            <ScoreBar label="Motivation" value={analysis.sellerMotivation} />
          </div>
          {analysis.arvConfidence === 'low' && (
            <p className="mt-2 text-xs text-yellow-500/70 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              ARV estimate is approximate — verify with local comps before making an offer.
            </p>
          )}
        </div>
      )}

      <div className="flex items-center justify-end mt-2">
        {expanded ? <ChevronUp className="w-3 h-3 text-gray-600" /> : <ChevronDown className="w-3 h-3 text-gray-600" />}
      </div>
    </div>
  );
}

function MetricBox({ label, value, highlight, dim, prefix }: { label: string; value: string; highlight?: boolean; dim?: boolean; prefix?: string }) {
  return (
    <div className="bg-[#0d1117] rounded p-2">
      <p className="text-xs text-gray-600 mb-0.5">{label}</p>
      <p className={cn('text-sm font-bold', highlight ? 'text-green-400' : dim ? 'text-red-400/70' : 'text-gray-300')}>
        {prefix}{value}
      </p>
    </div>
  );
}

function DetailRow({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="flex justify-between items-center py-1 border-b border-gray-800/50">
      <span className="text-gray-500">{label}</span>
      <span className={cn('font-medium', positive === true ? 'text-green-400' : positive === false ? 'text-red-400' : 'text-gray-300')}>
        {value}
      </span>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 75 ? 'bg-green-400' : value >= 50 ? 'bg-yellow-400' : 'bg-red-400';
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${value}%` }} />
      </div>
      <p className="text-xs font-semibold text-gray-400 mt-0.5">{value}</p>
    </div>
  );
}
