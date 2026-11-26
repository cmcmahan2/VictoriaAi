'use client';
import { useEffect, type ReactNode } from 'react';
import { barTone } from '@/lib/calc';
import { fmt } from '@/lib/format';

export function Card({ title, action, children, className = '', pad = true }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={`card ${pad ? '' : 'nopad'} ${className}`}>
      {(title || action) && (
        <header className="card-h">
          {title && <h2>{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Bar({ value, max, color, tone }: { value: number; max: number; color?: string; tone?: 'auto' | 'none' }) {
  const p = max > 0 ? Math.min(100, (value / max) * 100) : value > 0 ? 100 : 0;
  const t = tone === 'none' ? 'ok' : barTone(value, max);
  const bg = tone === 'none' ? color : t === 'over' ? 'var(--red)' : t === 'warn' ? 'var(--yellow)' : color ?? 'var(--accent)';
  return (
    <div className="bar" role="progressbar" aria-valuenow={Math.round(p)} aria-valuemin={0} aria-valuemax={100}>
      <div className="bar-fill" style={{ width: `${p}%`, background: bg }} />
    </div>
  );
}

export function BudgetRow({ emoji, name, spent, budget, color, sub }: { emoji: string; name: string; spent: number; budget: number; color: string; sub?: string }) {
  const tone = barTone(spent, budget);
  const left = budget - spent;
  return (
    <div className="brow">
      <div className="brow-top">
        <span className="brow-name"><span className="emoji">{emoji}</span>{name}</span>
        <span className={`brow-amt ${tone}`}>
          {fmt(spent)} <span className="muted">/ {fmt(budget)}</span>
        </span>
      </div>
      <Bar value={spent} max={budget} color={color} />
      <div className="brow-sub">
        <span className={tone === 'over' ? 'red' : tone === 'warn' ? 'yellow' : 'muted'}>
          {left >= 0 ? `${fmt(left)} left` : `${fmt(-left)} over`}
        </span>
        {sub && <span className="muted">{sub}</span>}
      </div>
    </div>
  );
}

export function Sheet({ open, onClose, title, children, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', k);
    document.body.classList.add('noscroll');
    return () => {
      window.removeEventListener('keydown', k);
      document.body.classList.remove('noscroll');
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="sheet-wrap" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grip" />
        <header className="sheet-h">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="sheet-body">{children}</div>
        {footer && <div className="sheet-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Seg<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="seg" role="tablist">
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={o.value === value} className={o.value === value ? 'on' : ''} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="field">
      <span className="field-l">{label}</span>
      {children}
      {hint && <span className="field-h">{hint}</span>}
    </label>
  );
}

/** Number input that keeps the raw text while typing. */
export function NumInput({ value, onChange, placeholder, prefix = '$', step, ...rest }: { value: number | null | undefined; onChange: (n: number) => void; placeholder?: string; prefix?: string; step?: string; autoFocus?: boolean; 'aria-label'?: string }) {
  return (
    <div className="num">
      {prefix && <span className="num-p">{prefix}</span>}
      <input
        type="number"
        inputMode="decimal"
        step={step ?? 'any'}
        value={value == null || Number.isNaN(value) ? '' : value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === '' ? NaN : parseFloat(e.target.value))}
        onFocus={(e) => e.target.select()}
        {...rest}
      />
    </div>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'green' | 'red' | 'yellow' }) {
  return (
    <div className="stat">
      <div className="stat-l">{label}</div>
      <div className={`stat-v ${tone ?? ''}`}>{value}</div>
      {sub && <div className="stat-s">{sub}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Check({ checked, onChange, label, sub }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; sub?: ReactNode }) {
  return (
    <button type="button" className={`check ${checked ? 'on' : ''}`} onClick={() => onChange(!checked)} aria-pressed={checked}>
      <span className="check-box">{checked ? '✓' : ''}</span>
      <span className="check-l">
        {label}
        {sub && <span className="check-s">{sub}</span>}
      </span>
    </button>
  );
}
