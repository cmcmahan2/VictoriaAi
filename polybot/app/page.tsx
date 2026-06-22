"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArbCard } from "@/components/ArbCard";
import { ArbDetail } from "@/components/ArbDetail";
import { buildStakePlan } from "@/lib/arbitrage";
import type { ArbOpportunity, TrackedBet } from "@/lib/types";
import { pct, usd } from "@/lib/utils";
import { Activity, RefreshCw, Trash2, Wifi, WifiOff } from "lucide-react";

const LS_KEY = "polybot.bets.v1";

type ScanResponse = {
  source: "live" | "demo";
  scanned: number;
  found: number;
  feePct: number;
  asOf: string;
  arbs: ArbOpportunity[];
};

export default function Home() {
  const [tab, setTab] = useState<"finder" | "tracker">("finder");
  const [data, setData] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [bankroll, setBankroll] = useState(100);
  const [stake, setStake] = useState(50);
  const [minRoi, setMinRoi] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bets, setBets] = useState<TrackedBet[]>([]);

  // Load tracked bets from localStorage.
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

  const scan = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/arbs?bankroll=${bankroll}&minRoi=${minRoi}`, {
        cache: "no-store",
      });
      const json: ScanResponse = await res.json();
      setData(json);
      if (!json.arbs.find((a) => a.id === selectedId)) {
        setSelectedId(json.arbs[0]?.id ?? null);
      }
    } finally {
      setLoading(false);
    }
  }, [bankroll, minRoi, selectedId]);

  useEffect(() => {
    scan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bankroll, minRoi]);

  const selected = useMemo(
    () => data?.arbs.find((a) => a.id === selectedId) ?? null,
    [data, selectedId],
  );

  function logBet(arb: ArbOpportunity, plan: ReturnType<typeof buildStakePlan>) {
    const bet: TrackedBet = {
      id: `${arb.id}-${Date.now()}`,
      question: arb.question,
      type: arb.type,
      legs: plan.legs,
      stake: plan.stake,
      expectedReturn: plan.guaranteedReturn,
      expectedProfit: plan.profit,
      status: "open",
      placedAt: new Date().toISOString(),
    };
    persist([bet, ...bets]);
    setTab("tracker");
  }

  function resolveBet(id: string, status: "won" | "lost") {
    persist(
      bets.map((b) =>
        b.id === id
          ? {
              ...b,
              status,
              // A true arb wins regardless; "lost" is for recording a busted
              // leg (one side didn't fill), which costs the unmatched stake.
              actualProfit: status === "won" ? b.expectedProfit : -b.stake,
            }
          : b,
      ),
    );
  }

  function removeBet(id: string) {
    persist(bets.filter((b) => b.id !== id));
  }

  const stats = useMemo(() => summarize(bets), [bets]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      {/* Header */}
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-pos/10 p-2 text-pos">
            <Activity size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold">Polybot</h1>
            <p className="text-xs text-muted">Polymarket-internal arbitrage finder · Phase 1 (read-only)</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {data && (
            <span
              className="flex items-center gap-1.5 rounded-full border border-edge px-2.5 py-1 text-xs text-muted"
              title={data.source === "live" ? "Live Polymarket data" : "Demo data (set POLYMARKET_LIVE=true for live)"}
            >
              {data.source === "live" ? (
                <Wifi size={13} className="text-pos" />
              ) : (
                <WifiOff size={13} className="text-warn" />
              )}
              {data.source}
            </span>
          )}
          <button
            onClick={scan}
            className="flex items-center gap-2 rounded-lg border border-edge bg-card px-3 py-1.5 text-sm hover:border-pos/50"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Scan
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-5 flex gap-1 rounded-lg border border-edge bg-panel p-1 text-sm">
        <TabBtn active={tab === "finder"} onClick={() => setTab("finder")}>
          Arbitrage finder
        </TabBtn>
        <TabBtn active={tab === "tracker"} onClick={() => setTab("tracker")}>
          Bet tracker {bets.length > 0 && <span className="text-muted">({bets.length})</span>}
        </TabBtn>
      </div>

      {tab === "finder" ? (
        <FinderView
          data={data}
          loading={loading}
          bankroll={bankroll}
          setBankroll={setBankroll}
          stake={stake}
          setStake={setStake}
          minRoi={minRoi}
          setMinRoi={setMinRoi}
          selected={selected}
          selectedId={selectedId}
          setSelectedId={setSelectedId}
          onLogBet={logBet}
        />
      ) : (
        <TrackerView bets={bets} stats={stats} onResolve={resolveBet} onRemove={removeBet} />
      )}
    </main>
  );
}

function FinderView(props: {
  data: ScanResponse | null;
  loading: boolean;
  bankroll: number;
  setBankroll: (n: number) => void;
  stake: number;
  setStake: (n: number) => void;
  minRoi: number;
  setMinRoi: (n: number) => void;
  selected: ArbOpportunity | null;
  selectedId: string | null;
  setSelectedId: (id: string) => void;
  onLogBet: (arb: ArbOpportunity, plan: ReturnType<typeof buildStakePlan>) => void;
}) {
  const { data, loading } = props;
  return (
    <>
      {/* Controls */}
      <div className="mb-4 flex flex-wrap items-end gap-4 rounded-xl border border-edge bg-card p-4">
        <NumField label="Bankroll ($)" value={props.bankroll} onChange={props.setBankroll} step={25} />
        <NumField label="Stake / bet ($)" value={props.stake} onChange={props.setStake} step={10} />
        <NumField label="Min ROI (%)" value={props.minRoi} onChange={props.setMinRoi} step={0.5} />
        <div className="ml-auto text-xs text-muted">
          {data && (
            <span>
              scanned {data.scanned} markets · {data.found} arb{data.found === 1 ? "" : "s"} · fee{" "}
              {pct(data.feePct * 100)} · {new Date(data.asOf).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_minmax(340px,420px)]">
        {/* Opportunity list */}
        <div className="space-y-3">
          {loading && !data && <Empty>Scanning Polymarket…</Empty>}
          {data && data.arbs.length === 0 && (
            <Empty>No arbitrage above your filters right now. Lower Min ROI or scan again.</Empty>
          )}
          {data?.arbs.map((arb) => (
            <ArbCard
              key={arb.id}
              arb={arb}
              stake={props.stake}
              selected={arb.id === props.selectedId}
              onSelect={() => props.setSelectedId(arb.id)}
            />
          ))}
        </div>

        {/* Detail panel */}
        <div className="lg:sticky lg:top-6 lg:self-start">
          {props.selected ? (
            <ArbDetail
              arb={props.selected}
              stake={props.stake}
              onLogBet={(plan) => props.onLogBet(props.selected!, plan)}
            />
          ) : (
            <Empty>Select an opportunity to see the stake plan.</Empty>
          )}
        </div>
      </div>
    </>
  );
}

function TrackerView({
  bets,
  stats,
  onResolve,
  onRemove,
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
        <Kpi
          label="Realized P&L"
          value={usd(stats.realized)}
          tone={stats.realized > 0 ? "pos" : stats.realized < 0 ? "neg" : "flat"}
        />
        <Kpi label="Win rate" value={stats.resolved ? pct((stats.wins / stats.resolved) * 100, 0) : "—"} />
      </div>

      {bets.length === 0 ? (
        <Empty>No bets logged yet. Find an arb and click “Log this bet”.</Empty>
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
                    <div className="text-slate-200">{b.question}</div>
                    <div className="text-xs text-muted">
                      {b.type} · {new Date(b.placedAt).toLocaleString()}
                    </div>
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
                          <button
                            onClick={() => onResolve(b.id, "won")}
                            className="rounded bg-posDim px-2 py-1 text-xs text-pos hover:brightness-125"
                          >
                            Won
                          </button>
                          <button
                            onClick={() => onResolve(b.id, "lost")}
                            className="rounded bg-neg/15 px-2 py-1 text-xs text-neg hover:brightness-125"
                          >
                            Lost
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => onRemove(b.id)}
                        className="rounded p-1 text-muted hover:text-neg"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
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

// ---- small presentational helpers ----

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded-md px-3 py-1.5 transition ${
        active ? "bg-card text-slate-100" : "text-muted hover:text-slate-300"
      }`}
    >
      {children}
    </button>
  );
}

function NumField({
  label,
  value,
  onChange,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  step?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      <input
        type="number"
        value={value}
        step={step}
        min={0}
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
  return (
    <div className="rounded-xl border border-dashed border-edge bg-card/50 p-8 text-center text-sm text-muted">
      {children}
    </div>
  );
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
