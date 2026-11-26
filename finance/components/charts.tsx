'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fmt, fmtMonthShort, parseISO } from '@/lib/format';

export interface Slice { label: string; value: number; color: string }

/** Ring made of stroked circle segments (animates smoothly via dasharray). */
function Ring({ slices, r, width, total }: { slices: Slice[]; r: number; width: number; total?: number }) {
  const C = 2 * Math.PI * r;
  const sum = total ?? slices.reduce((a, s) => a + Math.max(0, s.value), 0);
  const [ready, setReady] = useState(false);
  useEffect(() => { const t = requestAnimationFrame(() => setReady(true)); return () => cancelAnimationFrame(t); }, []);
  let acc = 0;
  const gap = slices.filter((s) => s.value > 0).length > 1 ? 1.5 : 0;
  return (
    <g transform="rotate(-90 60 60)">
      <circle cx={60} cy={60} r={r} fill="none" stroke="var(--track)" strokeWidth={width} />
      {sum > 0 && slices.map((s, i) => {
        if (s.value <= 0) return null;
        const len = (s.value / sum) * C;
        const off = acc;
        acc += len;
        return (
          <circle
            key={i}
            cx={60} cy={60} r={r} fill="none"
            stroke={s.color}
            strokeWidth={width}
            strokeDasharray={`${ready ? Math.max(0, len - gap) : 0} ${C}`}
            strokeDashoffset={-off}
            style={{ transition: 'stroke-dasharray .8s cubic-bezier(.2,.8,.2,1)' }}
          >
            <title>{`${s.label}: ${fmt(s.value)}`}</title>
          </circle>
        );
      })}
    </g>
  );
}

export function Donut({ slices, center, sub }: { slices: Slice[]; center: string; sub?: string }) {
  return (
    <svg viewBox="0 0 120 120" className="donut" role="img" aria-label={slices.map((s) => `${s.label} ${fmt(s.value)}`).join(', ')}>
      <Ring slices={slices} r={46} width={16} />
      <text x={60} y={58} textAnchor="middle" className="donut-c">{center}</text>
      {sub && <text x={60} y={74} textAnchor="middle" className="donut-s">{sub}</text>}
    </svg>
  );
}

/** Outer ring = actual % of income, inner ring = planned % of income. */
export function DualDonut({ planned, actual, total }: { planned: Slice[]; actual: Slice[]; total: number }) {
  return (
    <svg viewBox="0 0 120 120" className="donut" role="img" aria-label="Planned versus actual share of income">
      <Ring slices={actual} r={50} width={11} total={total} />
      <Ring slices={planned} r={35} width={11} total={total} />
      <text x={60} y={57} textAnchor="middle" className="donut-s">outer: actual</text>
      <text x={60} y={69} textAnchor="middle" className="donut-s">inner: plan</text>
    </svg>
  );
}

export function Legend({ items }: { items: { label: string; color: string; value?: string }[] }) {
  return (
    <ul className="legend">
      {items.map((i) => (
        <li key={i.label}>
          <span className="dot" style={{ background: i.color }} />
          <span className="legend-l">{i.label}</span>
          {i.value && <span className="legend-v">{i.value}</span>}
        </li>
      ))}
    </ul>
  );
}

export interface Series { label: string; color: string; points: { x: string; y: number }[] }

/** Smooth multi-line chart with a time x-axis (ISO dates). */
export function LineChart({ series, markers = [], height = 200 }: { series: Series[]; markers?: { x: string; label: string; color: string }[]; height?: number }) {
  const W = 340, H = height, pl = 44, pr = 10, pt = 12, pb = 26;
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const xs = useMemo(() => Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.x)))).sort(), [series]);
  if (!xs.length) return null;
  const t0 = parseISO(xs[0]).getTime();
  const t1 = Math.max(t0 + 1, parseISO(xs[xs.length - 1]).getTime(), ...markers.map((m) => parseISO(m.x).getTime()));
  const ymax = Math.max(1, ...series.flatMap((s) => s.points.map((p) => p.y)));
  const niceMax = niceCeil(ymax);
  const X = (x: string) => pl + ((parseISO(x).getTime() - t0) / (t1 - t0)) * (W - pl - pr);
  const Y = (y: number) => pt + (1 - y / niceMax) * (H - pt - pb);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * niceMax);
  const months = Math.max(1, (t1 - t0) / (86400000 * 30));
  const every = months > 30 ? 6 : months > 14 ? 3 : months > 6 ? 2 : 1;
  const xTicks = xs.filter((_, i) => i % every === 0);

  const onMove = (e: React.PointerEvent) => {
    const svg = ref.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0, bd = Infinity;
    xs.forEach((x, i) => { const d = Math.abs(X(x) - px); if (d < bd) { bd = d; best = i; } });
    setHover(best);
  };

  return (
    <div className="linechart">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} onPointerMove={onMove} onPointerLeave={() => setHover(null)} role="img" aria-label="Debt payoff timeline">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pl} x2={W - pr} y1={Y(t)} y2={Y(t)} className="grid" />
            <text x={pl - 6} y={Y(t) + 3} textAnchor="end" className="axis">{t >= 1000 ? `$${(t / 1000).toFixed(t % 1000 ? 1 : 0)}k` : `$${t.toFixed(0)}`}</text>
          </g>
        ))}
        {xTicks.map((x) => (
          <text key={x} x={X(x)} y={H - 8} textAnchor="middle" className="axis">{fmtMonthShort(x).replace(' 20', " '")}</text>
        ))}
        {markers.map((m) => (
          <g key={m.label}>
            <line x1={X(m.x)} x2={X(m.x)} y1={pt} y2={H - pb} stroke={m.color} strokeDasharray="3 3" strokeWidth={1} />
            <text x={Math.min(X(m.x), W - pr - 2)} y={pt + 8} textAnchor="end" className="axis" fill={m.color}>{m.label}</text>
          </g>
        ))}
        {series.map((s) => (
          <path key={s.label} d={smooth(s.points.map((p) => [X(p.x), Y(p.y)]))} fill="none" stroke={s.color} strokeWidth={2.5} strokeLinecap="round" className="draw" pathLength={1} />
        ))}
        {hover != null && (
          <g>
            <line x1={X(xs[hover])} x2={X(xs[hover])} y1={pt} y2={H - pb} className="hoverline" />
            {series.map((s) => {
              const p = s.points.find((q) => q.x === xs[hover]);
              return p ? <circle key={s.label} cx={X(p.x)} cy={Y(p.y)} r={4} fill={s.color} stroke="var(--card)" strokeWidth={2} /> : null;
            })}
          </g>
        )}
      </svg>
      <div className="lc-tip">
        {hover != null ? (
          <>
            <b>{fmtMonthShort(xs[hover])}</b>
            {series.map((s) => {
              const p = s.points.find((q) => q.x === xs[hover]);
              return p ? <span key={s.label}><i className="dot" style={{ background: s.color }} />{fmt(p.y, { whole: true })}</span> : null;
            })}
          </>
        ) : (
          <span className="muted">Drag across the chart to see balances</span>
        )}
      </div>
    </div>
  );
}

function niceCeil(v: number) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return m * p;
}

/** Monotone-ish smoothing: cubic bezier with clamped control points (never overshoots below 0). */
function smooth(pts: number[][]): string {
  if (!pts.length) return '';
  if (pts.length < 3) return 'M' + pts.map((p) => p.join(',')).join(' L');
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const dx = (x1 - x0) / 3;
    d += ` C${x0 + dx},${y0} ${x1 - dx},${y1} ${x1},${y1}`;
  }
  return d;
}
