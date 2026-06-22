"use client";

import type { ArbOpportunity } from "@/lib/types";
import { buildStakePlan } from "@/lib/arbitrage";
import { cents, pct, usd } from "@/lib/utils";
import { CheckCircle2 } from "lucide-react";

export function ArbDetail({
  arb,
  stake,
  onLogBet,
}: {
  arb: ArbOpportunity;
  stake: number;
  onLogBet: (plan: ReturnType<typeof buildStakePlan>) => void;
}) {
  const plan = buildStakePlan(arb, stake);

  return (
    <div className="rounded-xl border border-edge bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="text-3xl font-bold text-pos">{pct(arb.roiPct)}</div>
        <div className="rounded bg-posDim px-2 py-1 text-sm font-semibold text-pos">
          guaranteed {usd(plan.profit)}
        </div>
      </div>
      <div className="mt-2 text-sm text-slate-100">{arb.question}</div>

      {/* Stake plan: how many shares of each leg to buy */}
      <div className="mt-5 text-xs font-semibold uppercase tracking-wide text-muted">
        Stake plan @ {usd(stake, 0)}
      </div>
      <div className="mt-2 overflow-hidden rounded-lg border border-edge">
        <table className="w-full text-sm">
          <thead className="bg-panel text-xs text-muted">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Outcome</th>
              <th className="px-3 py-2 text-right font-medium">Price</th>
              <th className="px-3 py-2 text-right font-medium">Shares</th>
              <th className="px-3 py-2 text-right font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {plan.legs.map((l) => (
              <tr key={l.label} className="border-t border-edge">
                <td className="px-3 py-2 text-slate-200">{l.label}</td>
                <td className="px-3 py-2 text-right font-mono text-slate-300">{cents(l.price)}</td>
                <td className="px-3 py-2 text-right text-slate-300">{l.shares}</td>
                <td className="px-3 py-2 text-right text-slate-300">{usd(l.cost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Payout breakdown */}
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <Stat label="Total staked" value={usd(plan.stake)} />
        <Stat label="Guaranteed return" value={usd(plan.guaranteedReturn)} accent />
        <Stat label="Net profit" value={usd(plan.profit)} accent />
        <Stat label="Fee on winnings" value={pct(arb.feePct * 100)} />
      </div>

      <p className="mt-4 text-xs leading-relaxed text-muted">
        One share of every outcome above forms a complete set that pays exactly $1.00 at
        resolution. Buying {plan.sets} set{plan.sets === 1 ? "" : "s"} for {usd(plan.stake)} locks{" "}
        {usd(plan.profit)} regardless of how the market resolves — assuming both legs fill at these
        prices. (Execution/leg risk is what Phase 3 auto-execution removes.)
      </p>

      <button
        onClick={() => onLogBet(plan)}
        disabled={plan.sets <= 0}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-pos px-4 py-2.5 font-semibold text-ink transition hover:brightness-110 disabled:opacity-40"
      >
        <CheckCircle2 size={18} />
        Log this bet (paper)
      </button>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg bg-panel px-3 py-2">
      <div className="text-xs text-muted">{label}</div>
      <div className={accent ? "font-semibold text-pos" : "font-medium text-slate-200"}>{value}</div>
    </div>
  );
}
