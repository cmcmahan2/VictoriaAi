import type { TrackedBet } from "./types";

export interface EquityPoint {
  t: number; // epoch ms (resolution time)
  cum: number; // cumulative realized P&L
  label: string; // market question, for tooltips
}

export interface Analytics {
  total: number;
  open: number;
  resolved: number;
  wins: number;
  losses: number;
  winRate: number | null; // % of resolved that won
  staked: number; // total staked across all bets
  realized: number; // realized P&L on resolved bets
  roi: number | null; // realized / staked-on-resolved, %
  openExposure: number; // stake tied up in open bets
  openExpectedProfit: number; // expected profit still to be realized
  autoShare: number | null; // % of bets placed by the bot
  equity: EquityPoint[]; // cumulative realized P&L curve
}

/** Compute the full dashboard analytics from the track record. */
export function computeAnalytics(bets: TrackedBet[]): Analytics {
  const resolved = bets.filter((b) => b.status !== "open");
  const open = bets.filter((b) => b.status === "open");
  const wins = resolved.filter((b) => b.status === "won");
  const losses = resolved.filter((b) => b.status === "lost");

  const stakedResolved = resolved.reduce((s, b) => s + b.stake, 0);
  const realized = resolved.reduce((s, b) => s + (b.actualProfit ?? 0), 0);

  // Equity curve: order resolved bets by resolution time, accumulate P&L.
  const ordered = [...resolved].sort(
    (a, b) => resolveTime(a) - resolveTime(b),
  );
  let cum = 0;
  const equity: EquityPoint[] = ordered.map((b) => {
    cum += b.actualProfit ?? 0;
    return { t: resolveTime(b), cum: round(cum, 2), label: b.question };
  });

  const autoCount = bets.filter((b) => b.auto).length;

  return {
    total: bets.length,
    open: open.length,
    resolved: resolved.length,
    wins: wins.length,
    losses: losses.length,
    winRate: resolved.length ? round((wins.length / resolved.length) * 100, 1) : null,
    staked: round(bets.reduce((s, b) => s + b.stake, 0), 2),
    realized: round(realized, 2),
    roi: stakedResolved > 0 ? round((realized / stakedResolved) * 100, 2) : null,
    openExposure: round(open.reduce((s, b) => s + b.stake, 0), 2),
    openExpectedProfit: round(open.reduce((s, b) => s + b.expectedProfit, 0), 2),
    autoShare: bets.length ? round((autoCount / bets.length) * 100, 0) : null,
    equity,
  };
}

function resolveTime(b: TrackedBet): number {
  return new Date(b.resolvedAt ?? b.placedAt).getTime();
}

function round(n: number, dp: number) {
  const f = 10 ** dp;
  return Math.round(n * f) / f;
}
