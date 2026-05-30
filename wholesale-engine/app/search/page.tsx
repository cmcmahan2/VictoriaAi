'use client';

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  Search, SlidersHorizontal, Building2, TrendingUp, DollarSign,
  AlertTriangle, ChevronDown, ChevronUp, X, Download, Bookmark,
  Map as MapIcon, List, Calculator, Bell, Users, CheckCircle, XCircle,
  BookmarkCheck, Trash2, ExternalLink, Sparkles, Wand2, Briefcase, Check,
} from 'lucide-react';
import Link from 'next/link';
import { cn, formatCurrency, scoreColor, scoreLabel, listingUrl } from '@/lib/utils';
import type { DealAnalysis } from '@/modules/deals/analysis';
import type { SearchQuery, PropertyType, SearchFilters } from '@/modules/properties/types';

type ParsedBuyBox = {
  market: string | null;
  zipCodes: string[] | null;
  minPrice: number | null;
  maxPrice: number | null;
  minBedrooms: number | null;
  propertyTypes: PropertyType[];
  maxDaysOnMarket: number | null;
  requireDistressSignals: boolean;
  minScore: number | null;
  minProfit: number | null;
  summary: string;
};

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
    agent?: AgentMeta;
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
  requireDistress: boolean;
  profitableOnly: boolean;
  minProfit: string;
};

type AgentMeta = {
  summary: string;
  usedAi: boolean;
  marketsScanned: number;
  totalScanned: number;
  profitableFound: number;
  minProfit: number | null;
  topMarkets: { market: string; count: number }[];
};

type SavedSearch = {
  id: number;
  name: string;
  market: string;
  zipCodes: string | null;
  filters: string;
};

const DEFAULT_FILTERS: LocalFilters = {
  minPrice: '', maxPrice: '', minBedrooms: '', maxDom: '',
  propertyTypes: [], onlyDeals: false, minScore: '', requireDistress: false,
  profitableOnly: false, minProfit: '',
};

const PROPERTY_TYPES: PropertyType[] = ['SFR', 'MFR', 'Condo', 'Townhouse', 'Land'];

const POPULAR_MARKETS = [
  'Memphis, TN', 'Detroit, MI', 'Houston, TX', 'Atlanta, GA',
  'Dallas, TX', 'Tampa, FL', 'Cleveland, OH', 'Indianapolis, IN',
  'Charlotte, NC', 'Columbus, OH', 'Jacksonville, FL', 'Birmingham, AL',
];

// ── Deal Calculator ──────────────────────────────────────────────────────────
function DealCalculator({ onClose }: { onClose: () => void }) {
  const [c, setC] = useState({
    purchasePrice: '', arv: '', repairCosts: '', closingCostPct: '3',
    holdingCostMonth: '', holdingMonths: '3', assignmentFee: '10000',
  });

  const n = (v: string) => Number(v) || 0;

  const arv = n(c.arv);
  const purchase = n(c.purchasePrice);
  const repair = n(c.repairCosts);
  const closing = arv * (n(c.closingCostPct) / 100);
  const holding = n(c.holdingCostMonth) * n(c.holdingMonths);
  const assignFee = n(c.assignmentFee);

  const flipProfit = arv - purchase - repair - closing - holding;
  const wholesaleProfit = assignFee;
  const mao70 = Math.max(0, arv * 0.70 - repair);
  const mao65 = Math.max(0, arv * 0.65 - repair);
  const mao75 = Math.max(0, arv * 0.75 - repair);
  const coc = purchase > 0 ? (flipProfit / purchase) * 100 : 0;

  const field = (label: string, key: keyof typeof c, placeholder: string, prefix = '$') => (
    <div>
      <label className="text-xs text-gray-500 mb-1 block">{label}</label>
      <div className="relative">
        <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-gray-600">{prefix}</span>
        <input
          type="number"
          value={c[key]}
          onChange={e => setC(prev => ({ ...prev, [key]: e.target.value }))}
          placeholder={placeholder}
          className="w-full bg-[#0d1117] border border-gray-700 rounded pl-5 pr-3 py-1.5 text-sm focus:outline-none focus:border-green-500"
        />
      </div>
    </div>
  );

  const resultRow = (label: string, value: number, highlight?: boolean) => (
    <div className="flex justify-between py-1.5 border-b border-gray-800/50 text-sm">
      <span className="text-gray-400">{label}</span>
      <span className={cn('font-semibold', highlight === true ? 'text-green-400' : highlight === false ? 'text-red-400' : 'text-gray-200')}>
        {formatCurrency(value)}
      </span>
    </div>
  );

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-[#161b22] border-l border-gray-800 z-50 flex flex-col shadow-2xl">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <span className="font-semibold text-gray-200 flex items-center gap-2">
          <Calculator className="w-4 h-4 text-green-400" /> Deal Calculator
        </span>
        <button onClick={onClose}><X className="w-4 h-4 text-gray-500" /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <p className="text-xs text-gray-500 mb-2">Inputs</p>
        {field('Purchase Price', 'purchasePrice', '150000')}
        {field('ARV (After Repair Value)', 'arv', '220000')}
        {field('Repair Costs', 'repairCosts', '30000')}
        {field('Closing Costs %', 'closingCostPct', '3', '%')}
        {field('Holding Costs / Month', 'holdingCostMonth', '1200')}
        {field('Holding Period (months)', 'holdingMonths', '3', '#')}
        {field('Assignment Fee (wholesale)', 'assignmentFee', '10000')}

        <div className="pt-3 border-t border-gray-800">
          <p className="text-xs text-gray-500 mb-2">Results</p>
          {resultRow('Flip Profit', flipProfit, flipProfit > 0)}
          {resultRow('Wholesale Profit', wholesaleProfit, wholesaleProfit > 0)}
          <div className="flex justify-between py-1.5 border-b border-gray-800/50 text-sm">
            <span className="text-gray-400">Cash-on-Cash Return</span>
            <span className={cn('font-semibold', coc > 0 ? 'text-green-400' : 'text-red-400')}>{coc.toFixed(1)}%</span>
          </div>
        </div>

        <div className="pt-3 border-t border-gray-800">
          <p className="text-xs text-gray-500 mb-2">Max Allowable Offer</p>
          <div className="space-y-1">
            {[['65% Rule', mao65], ['70% Rule (standard)', mao70], ['75% Rule', mao75]].map(([label, val]) => (
              <div key={String(label)} className="flex justify-between text-sm py-1">
                <span className="text-gray-500">{label}</span>
                <span className="text-gray-200 font-medium">{formatCurrency(Number(val))}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Simple Map View ──────────────────────────────────────────────────────────
function MapView({ analyses }: { analyses: DealAnalysis[] }) {
  const zipGroups = useMemo(() => {
    const m = new Map<string, DealAnalysis[]>();
    for (const a of analyses) {
      const k = a.property.zip;
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(a);
    }
    return m;
  }, [analyses]);

  type ZipEntry = [string, DealAnalysis[]];

  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-lg p-6">
      <p className="text-xs text-yellow-500/70 mb-4 flex items-center gap-1">
        <AlertTriangle className="w-3 h-3" />
        Map placeholder — set <code className="bg-gray-800 px-1 rounded">NEXT_PUBLIC_MAPBOX_TOKEN</code> in .env for an interactive map
      </p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {([...zipGroups.entries()] as ZipEntry[]).map(([zip, props]) => {
          const best = [...props].sort((a: DealAnalysis, b: DealAnalysis) => b.wholesaleScore - a.wholesaleScore)[0];
          const avgScore = Math.round(props.reduce((s: number, a: DealAnalysis) => s + a.wholesaleScore, 0) / props.length);
          return (
            <div key={zip} className={cn('rounded-lg border p-3', scoreColor(avgScore))}>
              <p className="font-bold text-sm mb-1">{zip}</p>
              <p className="text-xs opacity-75">{props.length} properties</p>
              <p className="text-xs opacity-75">Avg score: {avgScore}</p>
              {best && <p className="text-xs opacity-60 truncate mt-1">{best.property.address}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── API Status Panel ─────────────────────────────────────────────────────────
function ApiStatusPanel({ meta }: { meta: SearchResult['meta'] }) {
  const sources = [
    { name: 'Zillow', key: 'zillow' },
    { name: 'ATTOM', key: 'attom' },
    { name: 'RentCast', key: 'rentcast' },
    { name: 'Redfin', key: 'redfin' },
    { name: 'Mock', key: 'mock' },
  ];

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {sources.filter(s => meta.sources[s.key] !== undefined).map(s => (
        <span key={s.key} className={cn('flex items-center gap-1 text-xs px-2 py-0.5 rounded border',
          s.key === 'mock' ? 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10' : 'text-green-400 border-green-400/30 bg-green-400/10')}>
          {s.key === 'mock'
            ? <XCircle className="w-3 h-3" />
            : <CheckCircle className="w-3 h-3" />}
          {s.name} ({meta.sources[s.key]})
        </span>
      ))}
      <span className={cn('flex items-center gap-1 text-xs px-2 py-0.5 rounded border',
        meta.hasClaude ? 'text-green-400 border-green-400/30 bg-green-400/10' : 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10')}>
        {meta.hasClaude ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
        {meta.hasClaude ? 'AI Scored' : 'Demo Scores'}
      </span>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export default function SearchPage() {
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [filters, setFilters] = useState<LocalFilters>(DEFAULT_FILTERS);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'map'>('list');
  const [showCalc, setShowCalc] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [showSaved, setShowSaved] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [searchMode, setSearchMode] = useState<'quick' | 'buybox' | 'agent'>('quick');
  const [buyBoxText, setBuyBoxText] = useState('');
  const [agentText, setAgentText] = useState('');
  const [parsing, setParsing] = useState(false);
  const [interpreted, setInterpreted] = useState<{ summary: string; usedAi: boolean } | null>(null);
  const didAutoSearch = useRef(false);

  useEffect(() => { void loadSavedSearches(); }, []);

  async function loadSavedSearches() {
    try {
      const res = await fetch('/api/saved-searches');
      const data = (await res.json()) as { ok: boolean; searches: SavedSearch[] };
      if (data.ok) setSavedSearches(data.searches);
    } catch { /* DB not configured */ }
  }

  const runSearch = useCallback(async (market: string, serverFilters?: SearchFilters) => {
    if (!market.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setShowSaved(false);

    const isZips = /^\d{5}/.test(market.trim());
    const query: SearchQuery = isZips
      ? { zipCodes: market.split(',').map(z => z.trim()).filter(Boolean) }
      : { market: market.trim() };
    if (serverFilters) query.filters = serverFilters;

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

  // Buy box: parse a plain-English description into criteria, apply them as
  // filters, then run the search for the detected market.
  const runBuyBox = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setParsing(true);
    setError(null);
    setInterpreted(null);
    try {
      const res = await fetch('/api/parse-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = (await res.json()) as { ok: boolean; parsed?: ParsedBuyBox; usedAi?: boolean; error?: string };
      if (!data.ok || !data.parsed) throw new Error(data.error ?? 'Could not understand that — try rephrasing.');

      const p = data.parsed;
      const target = p.market ?? (p.zipCodes?.join(', ') ?? '');
      if (!target) {
        setError('I couldn\'t find a city or ZIP in that. Try including a market, e.g. "in Memphis, TN".');
        return;
      }

      // Reflect parsed criteria in the filter sidebar
      setFilters({
        minPrice: p.minPrice != null ? String(p.minPrice) : '',
        maxPrice: p.maxPrice != null ? String(p.maxPrice) : '',
        minBedrooms: p.minBedrooms != null ? String(p.minBedrooms) : '',
        maxDom: p.maxDaysOnMarket != null ? String(p.maxDaysOnMarket) : '',
        propertyTypes: p.propertyTypes ?? [],
        onlyDeals: false,
        minScore: p.minScore != null ? String(p.minScore) : '',
        requireDistress: p.requireDistressSignals,
        profitableOnly: false,
        minProfit: p.minProfit != null ? String(p.minProfit) : '',
      });
      setSearchInput(target);
      setInterpreted({ summary: p.summary, usedAi: data.usedAi ?? false });

      const serverFilters: SearchFilters = {
        minPrice: p.minPrice ?? undefined,
        maxPrice: p.maxPrice ?? undefined,
        minBedrooms: p.minBedrooms ?? undefined,
        propertyTypes: p.propertyTypes.length ? p.propertyTypes : undefined,
        maxDaysOnMarket: p.maxDaysOnMarket ?? undefined,
        requireDistressSignals: p.requireDistressSignals || undefined,
      };
      await runSearch(target, serverFilters);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not parse your description');
    } finally {
      setParsing(false);
    }
  }, [runSearch]);

  // Agent: scan every strong market in parallel and return only the best,
  // profitable deals ranked across all of them.
  const runAgent = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setShowSaved(false);
    setInterpreted(null);
    // The agent already returns only winners — don't double-filter client-side.
    setFilters(DEFAULT_FILTERS);
    try {
      const res = await fetch('/api/agent-hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = (await res.json()) as SearchResult & { ok: boolean; error?: string };
      if (!data.ok) throw new Error(data.error ?? 'Agent hunt failed');
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Agent hunt failed');
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-search when arriving from Buyers "Match Deals" link (?markets=...)
  useEffect(() => {
    if (didAutoSearch.current) return;
    const params = new URLSearchParams(window.location.search);
    const market = params.get('markets');
    if (market) {
      didAutoSearch.current = true;
      setSearchInput(market);
      void runSearch(market);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // run once on mount — window.location is stable, runSearch from useCallback([]) is stable

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void runSearch(searchInput);
  };

  async function saveSearch() {
    if (!saveName.trim() || !result) return;
    try {
      await fetch('/api/saved-searches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: saveName, market: result.meta.market, filters }),
      });
      setSaveName('');
      setShowSaveDialog(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
      void loadSavedSearches();
    } catch { /* best effort */ }
  }

  async function deleteSaved(id: number) {
    await fetch(`/api/saved-searches?id=${id}`, { method: 'DELETE' });
    void loadSavedSearches();
  }

  function exportCsv() {
    if (!filteredAnalyses.length) return;
    const headers = [
      'Address', 'City', 'State', 'Zip', 'List Price', 'ARV Estimate',
      'MAO', 'Equity Spread', 'Profit @ List', 'Wholesale Score',
      'Distress Signals', 'Days on Market', 'Bedrooms', 'Bathrooms',
      'Sqft', 'Year Built', 'Source',
    ];
    const rows = filteredAnalyses.map(a => {
      const p = a.property;
      return [
        `"${p.address}"`, `"${p.city}"`, p.state, p.zip,
        p.price, a.arvEstimate, a.mao, a.equitySpread, a.projectedProfit,
        a.wholesaleScore, `"${p.distressSignals.join('; ')}"`,
        p.daysOnMarket, p.bedrooms, p.bathrooms, p.sqft, p.yearBuilt, p.source,
      ].join(',');
    });
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'wholesale-deals.csv'; a.click();
    URL.revokeObjectURL(url);
  }

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
      if (filters.requireDistress && p.distressSignals.length === 0) return false;
      if (filters.profitableOnly && a.projectedProfit <= 0) return false;
      if (filters.minProfit && a.projectedProfit < Number(filters.minProfit)) return false;
      return true;
    }).sort((a, b) => b.wholesaleScore - a.wholesaleScore);
  }, [result, filters]);

  const hasActiveFilters = Object.entries(filters).some(([k, v]) => {
    if (k === 'propertyTypes') return (v as PropertyType[]).length > 0;
    if (k === 'onlyDeals' || k === 'requireDistress' || k === 'profitableOnly') return v === true;
    return v !== '';
  });

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      {/* Calculator slide-out */}
      {showCalc && <DealCalculator onClose={() => setShowCalc(false)} />}

      {/* Header */}
      <header className="border-b border-gray-800 bg-[#161b22]">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-green-400" />
              <span className="font-bold text-base tracking-tight">Wholesale Engine</span>
              <span className="text-xs text-gray-500 border border-gray-700 rounded px-1.5 py-0.5">beta</span>
            </div>
            <nav className="flex gap-4 text-sm">
              <Link href="/search" className="text-green-400 font-medium">Search</Link>
              <Link href="/deals" className="text-gray-500 hover:text-gray-300 flex items-center gap-1">
                <Briefcase className="w-3 h-3" />Pipeline
              </Link>
              <Link href="/buyers" className="text-gray-500 hover:text-gray-300 flex items-center gap-1">
                <Users className="w-3 h-3" />Buyers
              </Link>
              <Link href="/alerts" className="text-gray-500 hover:text-gray-300 flex items-center gap-1">
                <Bell className="w-3 h-3" />Alerts
              </Link>
            </nav>
          </div>
          <button onClick={() => setShowCalc(c => !c)}
            className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded border text-sm transition-colors',
              showCalc ? 'border-green-500 text-green-400 bg-green-500/10' : 'border-gray-700 text-gray-400 hover:border-gray-500')}>
            <Calculator className="w-4 h-4" /> Calculator
          </button>
        </div>
      </header>

      <main className={cn('max-w-7xl mx-auto px-4 py-8', showCalc && 'pr-84')}>
        {/* Search Bar */}
        <div className="mb-6">
          {/* Mode toggle */}
          <div className="flex items-center gap-1 mb-3">
            <button type="button" onClick={() => setSearchMode('quick')}
              className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors',
                searchMode === 'quick' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-gray-200 border border-gray-700')}>
              <Search className="w-3 h-3" />Quick search
            </button>
            <button type="button" onClick={() => setSearchMode('buybox')}
              className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors',
                searchMode === 'buybox' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-gray-200 border border-gray-700')}>
              <Wand2 className="w-3 h-3" />Describe your deal
            </button>
            <button type="button" onClick={() => setSearchMode('agent')}
              className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors',
                searchMode === 'agent' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-gray-200 border border-gray-700')}>
              <Sparkles className="w-3 h-3" />Deal Agent
            </button>
          </div>

          {searchMode === 'buybox' && (
            <div>
              <div className="relative">
                <Sparkles className="absolute left-3 top-3 w-4 h-4 text-green-400" />
                <textarea
                  value={buyBoxText}
                  onChange={e => setBuyBoxText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void runBuyBox(buyBoxText); } }}
                  rows={2}
                  placeholder="Describe what you're looking for — e.g. '3+ bed single family homes under $150k in Memphis with motivated sellers'"
                  className="w-full pl-10 pr-4 py-3 bg-[#161b22] border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500 resize-none"
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-gray-600">Tip: press ⌘/Ctrl + Enter to run</span>
                <button type="button" onClick={() => void runBuyBox(buyBoxText)} disabled={parsing || !buyBoxText.trim()}
                  className="flex items-center gap-1.5 px-5 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-semibold transition-colors">
                  <Wand2 className="w-4 h-4" />{parsing ? 'Reading…' : 'Match my buy box'}
                </button>
              </div>
              {interpreted && (
                <div className="mt-3 p-3 bg-green-900/10 border border-green-700/30 rounded text-sm text-gray-300 flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-green-400 shrink-0 mt-0.5" />
                  <span>
                    <span className="text-gray-500">{interpreted.usedAi ? 'AI understood' : 'Reading'}:</span> {interpreted.summary}
                  </span>
                </div>
              )}
            </div>
          )}

          {searchMode === 'agent' && (
            <div>
              <div className="relative">
                <Sparkles className="absolute left-3 top-3 w-4 h-4 text-green-400" />
                <textarea
                  value={agentText}
                  onChange={e => setAgentText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void runAgent(agentText); } }}
                  rows={2}
                  placeholder="Tell the agent what you want — e.g. '3+ bed houses, motivated sellers, at least $25k profit' — it scans every strong market and returns the best deals."
                  className="w-full pl-10 pr-4 py-3 bg-[#161b22] border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500 resize-none"
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-gray-600">Scans all {POPULAR_MARKETS.length}+ markets · ⌘/Ctrl + Enter to run</span>
                <button type="button" onClick={() => void runAgent(agentText)} disabled={loading || !agentText.trim()}
                  className="flex items-center gap-1.5 px-5 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-semibold transition-colors">
                  <Sparkles className="w-4 h-4" />{loading ? 'Hunting…' : 'Run deal agent'}
                </button>
              </div>
            </div>
          )}

          {searchMode === 'quick' && (
          <form onSubmit={handleSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input type="text" value={searchInput} onChange={e => setSearchInput(e.target.value)}
                placeholder="Memphis, TN — or — 38103, 38104, 38105"
                className="w-full pl-10 pr-4 py-3 bg-[#161b22] border border-gray-700 rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500" />
            </div>
            <button type="submit" disabled={loading || !searchInput.trim()}
              className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-semibold transition-colors">
              {loading ? 'Searching…' : 'Find Deals'}
            </button>
            {/* Saved searches */}
            <div className="relative">
              <button type="button" onClick={() => setShowSaved(s => !s)}
                className="h-full px-3 border border-gray-700 hover:border-gray-500 rounded-lg text-gray-400 hover:text-gray-200 transition-colors">
                <Bookmark className="w-4 h-4" />
              </button>
              {showSaved && (
                <div className="absolute right-0 top-full mt-1 w-64 bg-[#161b22] border border-gray-700 rounded-lg shadow-xl z-10">
                  <div className="p-2 border-b border-gray-800 text-xs text-gray-500">Saved Searches</div>
                  {savedSearches.length === 0 ? (
                    <div className="p-3 text-xs text-gray-600">No saved searches yet</div>
                  ) : (
                    savedSearches.map(s => (
                      <div key={s.id} className="flex items-center gap-2 p-2 hover:bg-gray-800/50 group">
                        <button className="flex-1 text-left text-sm text-gray-300"
                          onClick={() => { setSearchInput(s.market); void runSearch(s.market); setShowSaved(false); }}>
                          {s.name}
                          <span className="text-xs text-gray-600 ml-1">({s.market})</span>
                        </button>
                        <button onClick={() => void deleteSaved(s.id)} className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </form>
          )}

          {searchMode === 'quick' && !result && !loading && (
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="text-xs text-gray-500 py-1">Try:</span>
              <button
                onClick={() => { setSearchInput('All Markets'); void runSearch('any'); }}
                className="text-xs px-3 py-1 bg-green-600/20 border border-green-600/40 hover:border-green-500 rounded-full text-green-400 hover:text-green-300 transition-colors font-medium flex items-center gap-1">
                <Sparkles className="w-3 h-3" />Browse All Markets
              </button>
              {POPULAR_MARKETS.map(m => (
                <button key={m} onClick={() => { setSearchInput(m); void runSearch(m); }}
                  className="text-xs px-3 py-1 bg-[#161b22] border border-gray-700 hover:border-gray-500 rounded-full text-gray-400 hover:text-gray-200 transition-colors">
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-700/50 rounded-lg text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />{error}
          </div>
        )}

        {saveSuccess && (
          <div className="mb-4 p-3 bg-green-900/20 border border-green-700/50 rounded text-green-400 text-sm flex items-center gap-2">
            <BookmarkCheck className="w-4 h-4" /> Search saved!
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
            <aside className="w-56 shrink-0 hidden lg:block">
              <div className="bg-[#161b22] border border-gray-800 rounded-lg p-4 sticky top-4">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                    <SlidersHorizontal className="w-4 h-4" /> Filters
                  </span>
                  {hasActiveFilters && (
                    <button onClick={() => setFilters(DEFAULT_FILTERS)} className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1">
                      <X className="w-3 h-3" />Clear
                    </button>
                  )}
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Min Score</label>
                    <select value={filters.minScore} onChange={e => setFilters(f => ({ ...f, minScore: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-green-500">
                      <option value="">Any</option>
                      <option value="75">75+ (Hot)</option>
                      <option value="50">50+ (Potential)</option>
                      <option value="25">25+</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Price Range</label>
                    <div className="flex gap-1">
                      <input type="number" placeholder="Min" value={filters.minPrice}
                        onChange={e => setFilters(f => ({ ...f, minPrice: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-green-500" />
                      <input type="number" placeholder="Max" value={filters.maxPrice}
                        onChange={e => setFilters(f => ({ ...f, maxPrice: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-green-500" />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Min Beds</label>
                    <select value={filters.minBedrooms} onChange={e => setFilters(f => ({ ...f, minBedrooms: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-green-500">
                      <option value="">Any</option>
                      <option value="2">2+</option><option value="3">3+</option><option value="4">4+</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Max DOM</label>
                    <select value={filters.maxDom} onChange={e => setFilters(f => ({ ...f, maxDom: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-green-500">
                      <option value="">Any</option>
                      <option value="30">30d</option><option value="60">60d</option>
                      <option value="90">90d</option><option value="180">180d</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 mb-2 block">Type</label>
                    <div className="space-y-1">
                      {PROPERTY_TYPES.map(t => (
                        <label key={t} className="flex items-center gap-2 cursor-pointer">
                          <input type="checkbox" checked={filters.propertyTypes.includes(t)}
                            onChange={e => setFilters(f => ({ ...f, propertyTypes: e.target.checked ? [...f.propertyTypes, t] : f.propertyTypes.filter(x => x !== t) }))}
                            className="accent-green-500" />
                          <span className="text-sm text-gray-400">{t}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={filters.onlyDeals}
                      onChange={e => setFilters(f => ({ ...f, onlyDeals: e.target.checked }))}
                      className="accent-green-500" />
                    <span className="text-sm text-gray-400">Viable only</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={filters.requireDistress}
                      onChange={e => setFilters(f => ({ ...f, requireDistress: e.target.checked }))}
                      className="accent-green-500" />
                    <span className="text-sm text-gray-400">Distressed only</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={filters.profitableOnly}
                      onChange={e => setFilters(f => ({ ...f, profitableOnly: e.target.checked }))}
                      className="accent-green-500" />
                    <span className="text-sm text-gray-400">Profitable only</span>
                  </label>
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Min Profit @ List</label>
                    <input type="number" placeholder="e.g. 20000" value={filters.minProfit}
                      onChange={e => setFilters(f => ({ ...f, minProfit: e.target.value }))}
                      className="w-full bg-[#0d1117] border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-green-500" />
                  </div>
                </div>
              </div>
            </aside>

            {/* Main content */}
            <div className="flex-1 min-w-0">
              {/* Agent summary banner */}
              {result.meta.agent && (
                <div className="bg-green-900/10 border border-green-700/30 rounded-lg p-4 mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-green-400" />
                    <span className="text-sm font-semibold text-green-400">Deal Agent results</span>
                    <span className="text-xs text-gray-500">
                      {result.meta.agent.usedAi ? 'AI-parsed' : 'keyword-parsed'} buy box
                    </span>
                  </div>
                  <p className="text-sm text-gray-300 mb-2">{result.meta.agent.summary}</p>
                  <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-500">
                    <span>Scanned <b className="text-gray-300">{result.meta.agent.marketsScanned}</b> markets</span>
                    <span>Reviewed <b className="text-gray-300">{result.meta.agent.totalScanned}</b> properties</span>
                    <span>Found <b className="text-green-400">{result.meta.agent.profitableFound}</b> deals worth pursuing</span>
                    {result.meta.agent.minProfit != null && (
                      <span>Min profit: <b className="text-gray-300">{formatCurrency(result.meta.agent.minProfit)}</b></span>
                    )}
                  </div>
                  {result.meta.agent.topMarkets.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {result.meta.agent.topMarkets.map(tm => (
                        <span key={tm.market} className="text-xs px-2 py-0.5 bg-green-400/10 border border-green-400/20 text-green-400 rounded">
                          {tm.market} · {tm.count}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {/* No live data notice — usually a non-US market (RentCast is US-only) */}
              {result.meta.usedMock && (
                <div className="bg-yellow-900/10 border border-yellow-700/30 rounded-lg p-4 mb-4 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
                  <div className="text-sm text-yellow-500/90">
                    <span className="font-semibold">No live listings found — showing demo data.</span>{' '}
                    Real listings come from RentCast, which covers the <b>US only</b>. If you searched a
                    non-US market (e.g. Vancouver, BC), try a US city instead — like Houston, TX,
                    Memphis, TN, or Phoenix, AZ.
                  </div>
                </div>
              )}
              {/* Market Summary */}
              <div className="bg-[#161b22] border border-gray-800 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-green-400" />
                    {result.meta.market === 'any' ? 'All Markets' : result.meta.market}
                  </h2>
                  <span className="text-xs text-gray-600">{result.meta.durationMs}ms</span>
                </div>
                <div className="grid grid-cols-4 gap-4 mb-3">
                  <Stat label="Hot Deals" value={String(result.marketSummary.hotDeals)} sub="Score 75+" highlight={result.marketSummary.hotDeals > 0} />
                  <Stat label="Potential" value={String(result.marketSummary.potentialDeals)} sub="Score 50-74" />
                  <Stat label="Avg Score" value={String(result.marketSummary.avgWholesaleScore)} sub="Wholesale index" />
                  <Stat label="Avg Equity" value={formatCurrency(result.marketSummary.avgEquitySpread)} sub="ARV − list" highlight={result.marketSummary.avgEquitySpread > 0} />
                </div>
                <ApiStatusPanel meta={result.meta} />
                {result.marketSummary.topDistressSignals.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {result.marketSummary.topDistressSignals.map(sig => (
                      <span key={sig} className="text-xs px-2 py-0.5 bg-orange-400/10 border border-orange-400/20 text-orange-400 rounded">{sig}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* Toolbar */}
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-gray-500">
                  {filteredAnalyses.length} properties
                  {filteredAnalyses.length !== result.analyses.length && ` (filtered from ${result.analyses.length})`}
                </p>
                <div className="flex items-center gap-2">
                  {/* View toggle */}
                  <div className="flex border border-gray-700 rounded overflow-hidden">
                    <button onClick={() => setViewMode('list')}
                      className={cn('px-3 py-1.5 text-xs flex items-center gap-1', viewMode === 'list' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-gray-200')}>
                      <List className="w-3 h-3" />List
                    </button>
                    <button onClick={() => setViewMode('map')}
                      className={cn('px-3 py-1.5 text-xs flex items-center gap-1', viewMode === 'map' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-gray-200')}>
                      <MapIcon className="w-3 h-3" />Map
                    </button>
                  </div>
                  {/* Export */}
                  <button onClick={exportCsv} disabled={filteredAnalyses.length === 0}
                    className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-700 hover:border-gray-500 rounded text-xs text-gray-400 hover:text-gray-200 transition-colors disabled:opacity-40">
                    <Download className="w-3 h-3" />Export CSV
                  </button>
                  {/* Save search */}
                  {!showSaveDialog ? (
                    <button onClick={() => setShowSaveDialog(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-700 hover:border-gray-500 rounded text-xs text-gray-400 hover:text-gray-200 transition-colors">
                      <Bookmark className="w-3 h-3" />Save
                    </button>
                  ) : (
                    <div className="flex items-center gap-1">
                      <input value={saveName} onChange={e => setSaveName(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && void saveSearch()}
                        placeholder="Search name…" autoFocus
                        className="px-2 py-1.5 bg-[#0d1117] border border-gray-700 rounded text-xs focus:outline-none focus:border-green-500 w-32" />
                      <button onClick={() => void saveSearch()}
                        className="px-2 py-1.5 bg-green-600 hover:bg-green-500 rounded text-xs">Save</button>
                      <button onClick={() => setShowSaveDialog(false)} className="p-1.5 text-gray-600 hover:text-gray-400">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Results */}
              {viewMode === 'map' ? (
                <MapView analyses={filteredAnalyses} />
              ) : filteredAnalyses.length === 0 ? (
                <div className="py-16 text-center text-gray-500">
                  <Building2 className="w-8 h-8 mx-auto mb-3 opacity-30" />
                  <p>No properties match your filters.</p>
                  <button onClick={() => setFilters(DEFAULT_FILTERS)} className="mt-2 text-green-400 hover:text-green-300 text-sm">Clear filters</button>
                </div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {filteredAnalyses.map(analysis => (
                    <PropertyCard key={analysis.property.id} analysis={analysis}
                      expanded={expandedId === analysis.property.id}
                      onToggle={() => setExpandedId(id => id === analysis.property.id ? null : analysis.property.id)} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {!result && !loading && !error && (
          <div className="text-center py-24">
            <Building2 className="w-12 h-12 mx-auto mb-4 text-gray-700" />
            <h2 className="text-xl font-semibold text-gray-400 mb-2">Find Wholesale Deals</h2>
            <p className="text-gray-600 max-w-md mx-auto text-sm">
              Enter a US city/state or zip codes. Our AI scores every property for wholesale potential
              using ARV analysis, distress signals, and market momentum.
            </p>
          </div>
        )}
      </main>
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

function TrackDealButton({ analysis }: { analysis: DealAnalysis }) {
  const [state, setState] = useState<'idle' | 'saving' | 'tracked'>('idle');
  const p = analysis.property;

  async function track(e: React.MouseEvent) {
    e.stopPropagation();
    if (state !== 'idle') return;
    setState('saving');
    try {
      const res = await fetch('/api/deals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          externalId: p.id,
          address: p.address,
          city: p.city,
          state: p.state,
          zip: p.zip,
          price: p.price,
          propertyType: p.propertyType,
          wholesaleScore: analysis.wholesaleScore,
          arvEstimate: analysis.arvEstimate,
          mao: analysis.mao,
          projectedProfit: analysis.projectedProfit,
          source: p.source,
          listingUrl: listingUrl(p),
        }),
      });
      const data = (await res.json()) as { ok: boolean };
      setState(data.ok ? 'tracked' : 'idle');
    } catch {
      setState('idle');
    }
  }

  return (
    <button
      onClick={track}
      disabled={state !== 'idle'}
      className={cn('inline-flex items-center gap-1.5 px-3 py-1.5 border rounded text-xs font-semibold transition-colors',
        state === 'tracked'
          ? 'bg-gray-700/40 border-gray-600 text-gray-400 cursor-default'
          : 'border-gray-700 text-gray-300 hover:border-green-500 hover:text-green-400')}
      title="Save this property to your deal pipeline"
    >
      {state === 'tracked'
        ? <><Check className="w-3 h-3" />Tracked</>
        : <><Briefcase className="w-3 h-3" />{state === 'saving' ? 'Saving…' : 'Track Deal'}</>}
    </button>
  );
}

type AvmResponse = {
  ok: boolean;
  error?: string;
  arv: number;
  rangeLow: number;
  rangeHigh: number;
  compCount: number;
  mao: number;
  equitySpread: number;
  projectedProfit: number;
  comparables: { address: string; price: number; bedrooms: number; bathrooms: number; sqft: number; distance: number; daysOld: number }[];
};

// On-demand real ARV from RentCast comps. Each click costs 1 RentCast request,
// so this is opt-in per property rather than run across the whole search.
function RealArvPanel({ analysis }: { analysis: DealAnalysis }) {
  const p = analysis.property;
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [data, setData] = useState<AvmResponse | null>(null);
  const [error, setError] = useState('');

  // Mock/demo properties have fake addresses RentCast can't comp.
  if (p.source === 'mock') return null;

  async function fetchArv(e: React.MouseEvent) {
    e.stopPropagation();
    setState('loading'); setError('');
    try {
      const res = await fetch('/api/avm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          address: p.address, city: p.city, state: p.state, zip: p.zip,
          propertyType: p.propertyType, bedrooms: p.bedrooms, bathrooms: p.bathrooms, sqft: p.sqft,
          price: p.price, repairEstimate: analysis.repairEstimate, maoPercentage: 0.70,
        }),
      });
      const d = (await res.json()) as AvmResponse;
      if (!d.ok) { setError(d.error ?? 'Failed to fetch comps'); setState('error'); return; }
      setData(d); setState('done');
    } catch {
      setError('Request failed'); setState('error');
    }
  }

  return (
    <div className="mt-3 border-t border-gray-800 pt-3">
      {state !== 'done' && (
        <button onClick={fetchArv} disabled={state === 'loading'}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-700 hover:border-green-500 hover:text-green-400 rounded text-xs font-semibold text-gray-300 transition-colors disabled:opacity-50">
          <TrendingUp className="w-3 h-3" />
          {state === 'loading' ? 'Pulling comps…' : 'Get real ARV from comps'}
          <span className="text-gray-600 font-normal">· uses 1 RentCast credit</span>
        </button>
      )}
      {state === 'error' && <p className="text-xs text-red-400 mt-1.5">{error}</p>}
      {state === 'done' && data && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-3.5 h-3.5 text-green-400" />
            <span className="text-xs font-semibold text-green-400">Comp-based value ({data.compCount} comps · RentCast)</span>
          </div>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <MetricBox label="ARV (comps)" value={formatCurrency(data.arv)} highlight />
            <MetricBox label="MAO (real)" value={formatCurrency(data.mao)} highlight={data.mao > p.price} dim={data.mao <= 0} />
            <MetricBox label="Profit @ List" value={formatCurrency(data.projectedProfit)}
              highlight={data.projectedProfit > 0} dim={data.projectedProfit < 0}
              prefix={data.projectedProfit > 0 ? '+' : ''} />
          </div>
          <p className="text-xs text-gray-500 mb-2">
            Value range {formatCurrency(data.rangeLow)} – {formatCurrency(data.rangeHigh)}
          </p>
          {data.comparables.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-gray-500 font-semibold">Comparable sales</p>
              {data.comparables.map((c, i) => (
                <div key={i} className="flex items-center justify-between text-xs text-gray-400 border-b border-gray-800/50 py-1">
                  <span className="truncate max-w-[55%]">{c.address}</span>
                  <span className="flex gap-2 shrink-0">
                    <span className="text-gray-300 font-medium">{formatCurrency(c.price)}</span>
                    <span className="text-gray-600">{c.distance.toFixed(1)}mi</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PropertyCard({ analysis, expanded, onToggle }: { analysis: DealAnalysis; expanded: boolean; onToggle: () => void }) {
  const { property: p } = analysis;
  const scoreClass = scoreColor(analysis.wholesaleScore);

  return (
    <div onClick={onToggle}
      className={cn('bg-[#161b22] border rounded-lg p-4 cursor-pointer transition-all',
        expanded ? 'border-green-600/50' : 'border-gray-800 hover:border-gray-600')}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <a
            href={listingUrl(p)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="group inline-flex items-center gap-1 text-sm font-semibold text-gray-200 hover:text-green-400 transition-colors max-w-full"
            title={p.source === 'mock' ? 'Demo property — opens real listings for this market on Zillow' : 'View the listing'}
          >
            <span className="truncate">{p.address}</span>
            <ExternalLink className="w-3 h-3 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
          </a>
          <p className="text-xs text-gray-500">{p.city}, {p.state} {p.zip}</p>
        </div>
        <div className={cn('shrink-0 px-2.5 py-1 rounded border text-xs font-bold', scoreClass)}>
          {analysis.wholesaleScore} · {scoreLabel(analysis.wholesaleScore)}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <MetricBox label="List Price" value={formatCurrency(p.price)} />
        <MetricBox label="MAO" value={formatCurrency(analysis.mao)} highlight={analysis.mao > p.price} dim={analysis.mao <= 0} />
        <MetricBox label="Profit @ List" value={formatCurrency(analysis.projectedProfit)}
          highlight={analysis.projectedProfit > 0} dim={analysis.projectedProfit < 0}
          prefix={analysis.projectedProfit > 0 ? '+' : ''} />
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mb-2">
        <span>{p.bedrooms}bd/{p.bathrooms}ba</span>
        <span>{p.sqft.toLocaleString()} sqft</span>
        <span>Built {p.yearBuilt}</span>
        <span>{p.daysOnMarket}d DOM</span>
        <span className="capitalize">{p.propertyType}</span>
      </div>

      {p.distressSignals.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {p.distressSignals.map(sig => (
            <span key={sig} className="text-xs px-1.5 py-0.5 bg-orange-400/10 border border-orange-400/20 text-orange-400 rounded">{sig}</span>
          ))}
        </div>
      )}

      {analysis.arvConfidence === 'low' && (
        <p className="text-xs text-yellow-500/60 flex items-center gap-1 mb-1">
          <AlertTriangle className="w-3 h-3 shrink-0" />ARV estimated — verify with comps
        </p>
      )}

      {analysis.scoreSummary && (
        <p className="text-xs text-gray-500 italic border-t border-gray-800 pt-2 mb-1">{analysis.scoreSummary}</p>
      )}

      {expanded && (
        <div className="border-t border-gray-800 pt-3 mt-1" onClick={e => e.stopPropagation()}>
          <p className="text-xs font-semibold text-gray-400 mb-2 flex items-center gap-1">
            <DollarSign className="w-3 h-3" />Deal Analysis
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs mb-3">
            <DetailRow label="ARV Estimate" value={formatCurrency(analysis.arvEstimate)} />
            <DetailRow label="ARV Confidence" value={analysis.arvConfidence} />
            <DetailRow label="Repair Estimate" value={formatCurrency(analysis.repairEstimate)} />
            <DetailRow label="MAO (70% Rule)" value={formatCurrency(analysis.mao)} />
            <DetailRow label="Equity Spread" value={formatCurrency(analysis.equitySpread)} positive={analysis.equitySpread > 0} />
            <DetailRow label="Profit @ List" value={formatCurrency(analysis.projectedProfit)} positive={analysis.projectedProfit > 0} />
          </div>
          <div className="grid grid-cols-4 gap-2">
            <ScoreBar label="Wholesale" value={analysis.wholesaleScore} />
            <ScoreBar label="Distress" value={analysis.distressScore} />
            <ScoreBar label="Momentum" value={analysis.momentumScore} />
            <ScoreBar label="Motivation" value={analysis.sellerMotivation} />
          </div>
          {analysis.arvConfidence === 'low' && (
            <p className="mt-2 text-xs text-yellow-500/70 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />Verify ARV with local comps before making an offer.
            </p>
          )}
          <RealArvPanel analysis={analysis} />
          <div className="mt-3 flex items-center gap-2">
            <a
              href={listingUrl(p)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-600/20 border border-green-600/40 text-green-400 hover:bg-green-600/30 rounded text-xs font-semibold transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              {p.source === 'mock' ? `Browse ${p.city} on Zillow` : `View Listing on ${p.source}`}
            </a>
            <TrackDealButton analysis={analysis} />
          </div>
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
      <span className={cn('font-medium', positive === true ? 'text-green-400' : positive === false ? 'text-red-400' : 'text-gray-300')}>{value}</span>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 75 ? 'bg-green-400' : value >= 50 ? 'bg-yellow-400' : 'bg-red-400';
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${value}%` }} />
      </div>
      <p className="text-xs font-semibold text-gray-400 mt-0.5">{value}</p>
    </div>
  );
}
