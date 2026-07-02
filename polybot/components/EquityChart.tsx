"use client";

import type { EquityPoint } from "@/lib/analytics";
import { usd } from "@/lib/utils";

/**
 * Cumulative realized-P&L curve. Pure SVG so it has no chart-lib quirks
 * (e.g. strict ascending-unique time) and scales cleanly. Green when the
 * record is in profit, red when underwater.
 */
export function EquityChart({ points }: { points: EquityPoint[] }) {
  const W = 800;
  const H = 300;
  const padL = 52;
  const padR = 16;
  const padT = 16;
  const padB = 28;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const n = points.length;
  const values = points.map((p) => p.cum);
  let min = Math.min(0, ...values);
  let max = Math.max(0, ...values);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const pad = (max - min) * 0.08;
  min -= pad;
  max += pad;

  const xFor = (i: number) => padL + (innerW * i) / Math.max(1, n - 1);
  const yFor = (v: number) => padT + innerH * (1 - (v - min) / (max - min));

  const last = points[n - 1];
  const positive = (last?.cum ?? 0) >= 0;
  const stroke = positive ? "#34d399" : "#f87171";
  const fill = positive ? "rgba(52,211,153,0.14)" : "rgba(248,113,113,0.14)";

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yFor(p.cum)}`).join(" ");
  const areaPath =
    n > 0
      ? `${linePath} L ${xFor(n - 1)} ${yFor(0)} L ${xFor(0)} ${yFor(0)} Z`
      : "";

  const gridVals = ticks(min, max, 4);

  return (
    <div className="rounded-xl border border-edge bg-panel p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <div className="text-sm font-medium text-slate-200">Equity curve · realized P&amp;L</div>
        <div className={`text-lg font-bold ${positive ? "text-pos" : "text-neg"}`}>
          {usd(last?.cum ?? 0)}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Equity curve">
        {/* gridlines */}
        {gridVals.map((v) => (
          <g key={v}>
            <line x1={padL} x2={W - padR} y1={yFor(v)} y2={yFor(v)} stroke="#1c2735" strokeWidth={1} />
            <text x={padL - 8} y={yFor(v) + 4} textAnchor="end" fontSize={11} fill="#7d8ba0">
              {usd(v, 0)}
            </text>
          </g>
        ))}
        {/* zero baseline */}
        <line x1={padL} x2={W - padR} y1={yFor(0)} y2={yFor(0)} stroke="#2a3a4d" strokeWidth={1.5} strokeDasharray="4 3" />

        {n > 0 && (
          <>
            <path d={areaPath} fill={fill} />
            <path d={linePath} fill="none" stroke={stroke} strokeWidth={2} />
            {points.map((p, i) => (
              <circle key={i} cx={xFor(i)} cy={yFor(p.cum)} r={n > 40 ? 0 : 2.5} fill={stroke}>
                <title>{`${p.label}\n${usd(p.cum)} · ${new Date(p.t).toLocaleString()}`}</title>
              </circle>
            ))}
          </>
        )}

        {/* x-axis endpoints */}
        {n > 0 && (
          <>
            <text x={padL} y={H - 8} fontSize={11} fill="#7d8ba0">
              {new Date(points[0].t).toLocaleDateString()}
            </text>
            <text x={W - padR} y={H - 8} textAnchor="end" fontSize={11} fill="#7d8ba0">
              {new Date(last.t).toLocaleDateString()}
            </text>
          </>
        )}
      </svg>
    </div>
  );
}

/** Evenly spaced tick values across [min, max]. */
function ticks(min: number, max: number, count: number): number[] {
  const out: number[] = [];
  for (let i = 0; i <= count; i++) out.push(min + ((max - min) * i) / count);
  return out;
}
