"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArbCard } from "@/components/ArbCard";
import { ArbDetail } from "@/components/ArbDetail";
import { ChartPanel, type TradeMarker } from "@/components/ChartPanel";
import type { Candle } from "@/lib/priceHistory";
import { buildStakePlan } from "@/lib/arbitrage";
import type { ArbOpportunity, TrackedBet } from "@/lib/types";
import { pct, usd } from "@/lib/utils";
import { Activity, Pause, Play, RefreshCw, Trash2, Wifi, WifiOff, Zap } from "lucide-react";

const LS_KEY = "polybot.bets.v1";

type ScanResponse = {
  source: "live" | "demo";
  scanned: number;
  found: number;
  feePct: number;
  asOf: string;
  arbs: ArbOpportunity[];
};

type FeedEntry = { id: string; ts: number; kind: "scan" | "trade" | "info"; text: string };

export default function Home() {
  const [tab, setTab] = useState<"finder" | "live" | "tracker">("finder");
  const [data, setData] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [bankroll, setBankroll] = useState(100);
  const [stake, setStake] = useState(50);
  const [minRoi, setMinRoi] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bets, setBets] = useState<TrackedBet[]>([]);

  // Live / bot state
  const [botRunning, setBotRunning] = useState(false);
  const [feed, setFeed] = useState<FeedEntry[]>([]);
  const betsRef = useRef<TrackedBet[]>([]);
  betsRef.current = bets;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (raw) setBets(JSON.parse(raw));
    } catch {}
  }, []);

  const persist = useCallback((next: TrackedBet[]) => {
    setBets(next);
    localStorage.setItem(LS_KEY, JSON.stringify(next));
  }, []);

  const pushFeed = useCallback((kind: FeedEntry["kind"], text: string) => {
    setFeed((f) => [{ id: `${Date.now()}-${Math.random()}`, ts: Date.now(), kind, text }, ...f].slice(0, 60));
  }, []);

  const scan = useCallback(async (): Promise<ScanResponse | null> => {
    setLoading(true);
    try {
      const res = await fetch(`/api/arbs?bankroll=${bankroll}&minRoi=${minRoi}`, { cache: "no-store" });
      const json: ScanResponse = await res.json();
      setData(json);
      setSelectedId((cur) => (json.arbs.find((a) => a.id === cur) ? cur : json.arbs[0]?.id ?? null));
      return json;
    } finally {
      setLoading(false);
    }
  }, [bankroll, minRoi]);

  useEffect(() => {
    scan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bankroll, minRoi]);

  const placeBet = useCallback(
    (arb: ArbOpportunity, plan: ReturnType<typeof buildStakePlan>, auto: boolean) => {
      if (plan.sets <= 0) return;
      const bet: TrackedBet = {
        id: `${arb.id}-${Date.now()}`,
        marketId: arb.id,
        question: arb.question,
        type: arb.type,
        auto,
        legs: plan.legs,
        stake: plan.stake,
        expectedReturn: plan.guaranteedReturn,
        expectedProfit: plan.profit,
        status: "open",
        placedAt: new Date().toISOString(),
      };
      persist([bet, ...betsRef.current]);
      pushFeed("trade", `${auto ? "🤖 Auto" : "Manual"} buy · ${arb.question} · ${usd(plan.stake)} → +${usd(plan.profit)} locked (${pct(arb.roiPct)})`);
    },
    [persist, pushFeed],
  );

  // ---- Paper auto-trader: while running, scan on an interval and execute the
  // best qualifying arb we don't already hold an open position in. ----
  useEffect(() => {
    if (!botRunning) return;
    let cancelled = false;

    const tick = async () => {
      const json = await scan();
      if (cancelled || !json) return;
      pushFeed("scan", `Scanned ${json.scanned} markets · ${json.found} arb${json.found === 1 ? "" : "s"} ≥ ${pct(minRoi)}`);
      const held = new Set(betsRef.current.filter((b) => b.status === "open").map((b) => b.marketId));
      const target = json.arbs.find((a) => !held.has(a.id));
      if (target) {
        placeBet(target, buildStakePlan(target, stake), true);
      } else if (json.arbs.length > 0) {
        pushFeed("info", "All current arbs already held — holding.");
      }
    };

    pushFeed("info", "Bot started (paper mode).");
    tick();
    const interval = setInterval(tick, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botRunning, stake]);

  const selected = useMemo(() => data?.arbs.find((a) => a.id === selectedId) ?? null, [data, selectedId]);

  function resolveBet(id: string, status: "won" | "lost") {
    persist(
      bets.map((b) =>
        b.id === id ? { ...b, status, actualProfit: status === "won" ? b.expectedProfit : -b.stake } : b,
      ),
    );
  }
  function removeBet(id: string) {
    persist(bets.filter((b) => b.id !== id));
  }

  const stats = useMemo(() => summarize(bets), [bets]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-pos/10 p-2 text-pos">
            <Activity size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold">Polybot</h1>
            <p className="text-xs text-muted">Polymarket-internal arbitrage · Phase 1–2 (read-only + paper)</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data && (
            <span className="flex items-center gap-1.5 rounded-full border border-edge px-2.5 py-1 text-xs text-muted">
              {data.source === "live" ? <Wifi size={13} className="text-pos" /> : <WifiOff size={13} className="text-warn" />}
              {data.source}
            </span>
          )}
          <button onClick={scan} className="flex items-center gap-2 rounded-lg border border-edge bg-card px-3 py-1.5 text-sm hover:border-pos/50">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Scan
          </button>
        </div>
      </div>

      <div className="mb-5 flex gap-1 rounded-lg border border-edge bg-panel p-1 text-sm">
        <TabBtn active={tab === "finder"} onClick={() => setTab("finder")}>Arbitrage finder</TabBtn>
        <TabBtn active={tab === "live"} onClick={() => setTab("live")}>
          Live chart {botRunning && <span className="ml-1 inline-block h-2 w-2 animate-pulse rounded-full bg-pos align-middle" />}
        </TabBtn>
        <TabBtn active={tab === "tracker"} onClick={() => setTab("tracker")}>
          Bet tracker {bets.length > 0 && <span className="text-muted">({bets.length})</span>}
        </TabBtn>
      </div>

      {tab === "finder" && (
        <FinderView
          data={data} loading={loading}
          bankroll={bankroll} setBankroll={setBankroll}
          stake={stake} setStake={setStake}
          minRoi={minRoi} setMinRoi={setMinRoi}
          selected={selected} selectedId={selectedId} setSelectedId={setSelectedId}
          onLogBet={(arb, plan) => placeBet(arb, plan, false)}
        />
      )}
      {tab === "live" && (
        <LiveView
          arbs={data?.arbs ?? []}
          selected={selected}
          selectedId={selectedId}
          setSelectedId={setSelectedId}
          bets={bets}
          stake={stake}
          botRunning={botRunning}
          setBotRunning={setBotRunning}
          feed={feed}
        />
      )}
      {tab === "tracker" && <TrackerView bets={bets} stats={stats} onResolve={resolveBet} onRemove={removeBet} />}
    </main>
  );
}

function LiveView({
  arbs, selected, selectedId, setSelectedId, bets, stake, botRunning, setBotRunning, feed,
}: {
  arbs: ArbOpportunity[];
  selected: ArbOpportunity | null;
  selectedId: string | null;
  setSelectedId: (id: string) => void;
  bets: TrackedBet[];
  stake: number;
  botRunning: boolean;
  setBotRunning: (b: boolean) => void;
  feed: FeedEntry[];
}) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  // Default the chart to the top opportunity.
  useEffect(() => {
    if (!selectedId && arbs[0]) setSelectedId(arbs[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [arbs]);

  useEffect(() => {
    if (!selected) {
      setCandles([]);
      return;
    }
    const leg = selected.legs[0];
    setChartLoading(true);
    fetch(`/api/history?token=${encodeURIComponent(leg.tokenId)}&price=${leg.askPrice}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => setCandles(j.candles ?? []))
      .catch(() => setCandles([]))
      .finally(() => setChartLoading(false));
  }, [selected]);

  const markers: TradeMarker[] = useMemo(() => {
    if (!selected) return [];
    return bets
      .filter((b) => b.marketId === selected.id)
      .map((b) => ({
        time: Math.floor(new Date(b.placedAt).getTime() / 1000),
        text: `BUY ${usd(b.stake, 0)}`,
        side: "buy" as const,
      }));
  }, [bets, selected]);

  return (
    <div className="space-y-4">
      {/* Bot control bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-edge bg-card p-4">
        <button
          onClick={() => setBotRunning(!botRunning)}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 font-semibold transition ${
            botRunning ? "bg-neg/20 text-neg hover:brightness-125" : "bg-pos text-ink hover:brightness-110"
          }`}
        >
          {botRunning ? <Pause size={16} /> : <Play size={16} />}
          {botRunning ? "Pause bot" : "Run bot (paper)"}
        </button>
        <div className="flex items-center gap-2 text-sm text-muted">
          <Zap size={14} className={botRunning ? "text-pos" : ""} />
          {botRunning ? "Scanning every 15s · auto-placing paper trades" : "Paper mode — no real funds, no orders sent"}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {arbs.map((a) => (
            <button
              key={a.id}
              onClick={() => setSelectedId(a.id)}
              className={`rounded-lg border px-2.5 py-1 text-xs ${
                a.id === selectedId ? "border-pos/70 text-pos" : "border-edge text-muted hover:text-slate-300"
              }`}
            >
              {a.question.length > 28 ? a.question.slice(0, 28) + "…" : a.question}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_minmax(320px,380px)]">
        {/* Chart (left) */}
        <ChartPanel
          candles={candles}
          markers={markers}
          loading={chartLoading}
          label={selected ? `${selected.legs[0].label} · ${selected.question}` : "Select a market"}
        />

        {/* Bot activity feed (right) */}
        <div className="rounded-xl border border-edge bg-panel">
          <div className="border-b border-edge px-4 py-2.5 text-sm font-medium text-slate-200">Bot activity</div>
          <div className="max-h-[360px] overflow-y-auto p-3">
            {feed.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted">Press “Run bot” to start the paper trader.</div>
            ) : (
              <ul className="space-y-2">
                {feed.map((e) => (
                  <li key={e.id} className="flex gap-2 text-xs">
                    <span className="shrink-0 font-mono text-muted">{new Date(e.ts).toLocaleTimeString()}</span>
                    <span className={e.kind === "trade" ? "text-pos" : e.kind === "scan" ? "text-slate-300" : "text-muted"}>
                      {e.text}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FinderView(props: {
  data: ScanResponse | null;
  loading: boolean;
  bankroll: number; setBankroll: (n: number) => void;
  stake: number; setStake: (n: number) => void;
  minRoi: number; setMinRoi: (n: number) => void;
  selected: ArbOpportunity | null;
  selectedId: string | null;
  setSelectedId: (id: string) => void;
  onLogBet: (arb: ArbOpportunity, plan: ReturnType<typeof buildStakePlan>) => void;
}) {
  const { data, loading } = props;
  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-4 rounded-xl border border-edge bg-card p-4">
        <NumField label="Bankroll ($)" value={props.bankroll} onChange={props.setBankroll} step={25} />
        <NumField label="Stake / bet ($)" value={props.stake} onChange={props.setStake} step={10} />
        <NumField label="Min ROI (%)" value={props.minRoi} onChange={props.setMinRoi} step={0.5} />
        <div className="ml-auto text-xs text-muted">
          {data && (
            <span>
              scanned {data.scanned} markets · {data.found} arb{data.found === 1 ? "" : "s"} · fee {pct(data.feePct * 100)} ·{" "}
              {new Date(data.asOf).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_minmax(340px,420px)]">
        <div className="space-y-3">
          {loading && !data && <Empty>Scanning Polymarket…</Empty>}
          {data && data.arbs.length === 0 && <Empty>No arbitrage above your filters right now. Lower Min ROI or scan again.</Empty>}
          {data?.arbs.map((arb) => (
            <ArbCard key={arb.id} arb={arb} stake={props.stake} selected={arb.id === props.selectedId} onSelect={() => props.setSelectedId(arb.id)} />
          ))}
        </div>
        <div className="lg:sticky lg:top-6 lg:self-start">
          {props.selected ? (
            <ArbDetail arb={props.selected} stake={props.stake} onLogBet={(plan) => props.onLogBet(props.selected!, plan)} />
          ) : (
            <Empty>Select an opportunity to see the stake plan.</Empty>
          )}
        </div>
      </div>
    </>
  );
}

function TrackerView({
  bets, stats, onResolve, onRemove,
}: {
  bets: TrackedBet[];
  stats: ReturnType<typeof summarize>;
  onResolve: (id: string, s: "won" | "lost") => void;
  onRemove: (id: string) => void;
}) {
  return (
    <>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label="Bets logged" value={String(stats.count)} />
        <Kpi label="Total staked" value={usd(stats.staked)} />
        <Kpi label="Realized P&L" value={usd(stats.realized)} tone={stats.realized > 0 ? "pos" : stats.realized < 0 ? "neg" : "flat"} />
        <Kpi label="Win rate" value={stats.resolved ? pct((stats.wins / stats.resolved) * 100, 0) : "—"} />
      </div>

      {bets.length === 0 ? (
        <Empty>No bets logged yet. Find an arb and click “Log this bet”, or run the bot in paper mode.</Empty>
      ) : (
        <div className="overflow-hidden rounded-xl border border-edge">
          <table className="w-full text-sm">
            <thead className="bg-panel text-xs text-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Market</th>
                <th className="px-3 py-2 text-right font-medium">Staked</th>
                <th className="px-3 py-2 text-right font-medium">Exp. profit</th>
                <th className="px-3 py-2 text-right font-medium">Result</th>
                <th className="px-3 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bets.map((b) => (
                <tr key={b.id} className="border-t border-edge">
                  <td className="px-3 py-2">
                    <div className="text-slate-200">
                      {b.auto && <span className="mr-1 rounded bg-pos/15 px-1 text-[10px] text-pos">AUTO</span>}
                      {b.question}
                    </div>
                    <div className="text-xs text-muted">{b.type} · {new Date(b.placedAt).toLocaleString()}</div>
                  </td>
                  <td className="px-3 py-2 text-right text-slate-300">{usd(b.stake)}</td>
                  <td className="px-3 py-2 text-right text-pos">{usd(b.expectedProfit)}</td>
                  <td className="px-3 py-2 text-right">
                    {b.status === "open" ? (
                      <span className="text-muted">open</span>
                    ) : (
                      <span className={b.status === "won" ? "text-pos" : "text-neg"}>
                        {b.status} {b.actualProfit != null && `(${usd(b.actualProfit)})`}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-end gap-1.5">
                      {b.status === "open" && (
                        <>
                          <button onClick={() => onResolve(b.id, "won")} className="rounded bg-posDim px-2 py-1 text-xs text-pos hover:brightness-125">Won</button>
                          <button onClick={() => onResolve(b.id, "lost")} className="rounded bg-neg/15 px-2 py-1 text-xs text-neg hover:brightness-125">Lost</button>
                        </>
                      )}
                      <button onClick={() => onRemove(b.id)} className="rounded p-1 text-muted hover:text-neg" title="Delete"><Trash2 size={14} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`flex-1 rounded-md px-3 py-1.5 transition ${active ? "bg-card text-slate-100" : "text-muted hover:text-slate-300"}`}>
      {children}
    </button>
  );
}

function NumField({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (n: number) => void; step?: number }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      <input
        type="number" value={value} step={step} min={0}
        onChange={(e) => onChange(Math.max(0, parseFloat(e.target.value) || 0))}
        className="w-32 rounded-lg border border-edge bg-panel px-3 py-1.5 text-sm outline-none focus:border-pos/60"
      />
    </label>
  );
}

function Kpi({ label, value, tone = "flat" }: { label: string; value: string; tone?: "pos" | "neg" | "flat" }) {
  const color = tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-slate-100";
  return (
    <div className="rounded-xl border border-edge bg-card p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-1 text-lg font-bold ${color}`}>{value}</div>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-xl border border-dashed border-edge bg-card/50 p-8 text-center text-sm text-muted">{children}</div>;
}

function summarize(bets: TrackedBet[]) {
  const resolved = bets.filter((b) => b.status !== "open");
  const wins = bets.filter((b) => b.status === "won").length;
  return {
    count: bets.length,
    staked: bets.reduce((s, b) => s + b.stake, 0),
    realized: resolved.reduce((s, b) => s + (b.actualProfit ?? 0), 0),
    resolved: resolved.length,
    wins,
  };
}
