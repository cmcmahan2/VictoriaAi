"use client";

import type { ArbOpportunity } from "@/lib/types";
import { cents, pct, usd } from "@/lib/utils";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<ArbOpportunity["type"], string> = {
  binary: "YES / NO",
  multi: "MULTI-OUTCOME",
  logical: "CORRELATED",
};

export function ArbCard({
  arb,
  stake,
  selected,
  onSelect,
}: {
  arb: ArbOpportunity;
  stake: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const sets = Math.min(Math.floor(stake / arb.costPerSet), arb.maxSets);
  const profit = (sets - sets * arb.costPerSet) * (1 - arb.feePct);

  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full text-left rounded-xl border bg-card p-4 transition",
        selected ? "border-pos/70 ring-1 ring-pos/40" : "border-edge hover:border-edge/80",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-2xl font-bold text-pos leading-none">{pct(arb.roiPct)}</div>
          <div className="mt-1 inline-flex rounded bg-posDim px-1.5 py-0.5 text-[11px] font-medium text-pos">
            ~{usd(profit, 0)} on {usd(sets * arb.costPerSet, 0)}
          </div>
        </div>
        <div className="text-right text-xs text-muted">
          <div className="font-medium text-slate-300">{TYPE_LABEL[arb.type]}</div>
          {arb.endDate && <div>{new Date(arb.endDate).toLocaleDateString()}</div>}
          {arb.category && <div className="text-muted">{arb.category}</div>}
        </div>
      </div>

      <div className="mt-3 font-medium text-slate-100">{arb.question}</div>

      <div className="mt-3 space-y-1.5">
        {arb.legs.map((l) => (
          <div
            key={l.tokenId}
            className="flex items-center justify-between rounded-lg bg-panel px-3 py-2 text-sm"
          >
            <span className="text-slate-200">{l.label}</span>
            <div className="flex items-center gap-3">
              <span className="font-mono text-slate-300">{cents(l.askPrice)}</span>
              <span className="text-xs text-muted">depth {l.askSize}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-muted">
        <span>
          set cost <span className="font-mono text-slate-300">{cents(arb.costPerSet)}</span> / $1.00
        </span>
        <span>
          max capture <span className="text-slate-300">{usd(arb.maxStake, 0)}</span>
        </span>
      </div>
    </button>
  );
}
