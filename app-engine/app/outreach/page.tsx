'use client';

import { useState } from 'react';

type OutreachTarget = {
  type: string;
  description: string;
  findThem: string;
  subjects: string[];
  email: string;
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <button
      onClick={copy}
      className="text-xs px-2.5 py-1 rounded border border-[#30363d] hover:border-[#484f58] text-[#8b949e] hover:text-[#e6edf3] transition-colors shrink-0"
    >
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  );
}

function TargetCard({ t, index }: { t: OutreachTarget; index: number }) {
  const [open, setOpen] = useState(index === 0);

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#1c2128] transition-colors"
      >
        <div>
          <span className="text-sm font-semibold text-[#e6edf3]">{t.type}</span>
          <p className="text-xs text-[#6e7681] mt-0.5">{t.description}</p>
        </div>
        <span className="text-[#6e7681] ml-3 shrink-0">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-[#30363d]">
          {/* Find them */}
          <div className="mt-3 flex gap-2 items-start bg-[#0d1117] rounded-lg p-3">
            <span className="text-base shrink-0">📍</span>
            <p className="text-xs text-[#8b949e] leading-relaxed">{t.findThem}</p>
          </div>

          {/* Subject lines */}
          <div>
            <p className="text-xs text-[#6e7681] font-medium uppercase tracking-wider mb-2">
              Subject lines
            </p>
            <div className="flex flex-col gap-1.5">
              {t.subjects.map((s) => (
                <div key={s} className="flex items-center justify-between gap-2 bg-[#0d1117] rounded px-3 py-2">
                  <span className="text-sm text-[#e6edf3] font-mono">{s}</span>
                  <CopyButton text={s} />
                </div>
              ))}
            </div>
          </div>

          {/* Email body */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-[#6e7681] font-medium uppercase tracking-wider">Email</p>
              <CopyButton text={t.email} />
            </div>
            <pre className="text-sm text-[#e6edf3] bg-[#0d1117] rounded-lg p-3 whitespace-pre-wrap leading-relaxed font-sans">
              {t.email}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function OutreachPage() {
  const [domain, setDomain] = useState('');
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [targets, setTargets] = useState<OutreachTarget[]>([]);
  const [resultDomain, setResultDomain] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    if (!domain.trim() || loading) return;
    setLoading(true);
    setTargets([]);
    setError(null);

    try {
      const res = await fetch('/api/outreach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: domain.trim(), context: context.trim() }),
      });
      const data = (await res.json()) as {
        ok: boolean;
        domain?: string;
        targets?: OutreachTarget[];
        error?: string;
      };
      if (!data.ok) throw new Error(data.error || 'Failed to generate outreach');
      setTargets(data.targets || []);
      setResultDomain(data.domain || domain.trim());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-3 md:p-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#e6edf3]">Outreach</h1>
        <p className="text-sm text-[#8b949e] mt-1">
          Enter a domain you own — get 4 buyer profiles and ready-to-send cold emails.
        </p>
      </div>

      {/* Form */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 mb-6 space-y-3">
        <div>
          <label className="text-xs text-[#8b949e] font-medium">Domain</label>
          <input
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && generate()}
            placeholder="hbmhub.com"
            className="w-full mt-1 px-3 py-2.5 bg-[#0d1117] border border-[#30363d] rounded-lg text-[#e6edf3] placeholder-[#6e7681] text-sm font-mono outline-none focus:border-[#484f58] transition-colors"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
        </div>
        <div>
          <label className="text-xs text-[#8b949e] font-medium">
            Context <span className="text-[#6e7681] font-normal">(optional)</span>
          </label>
          <input
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="e.g. HBM = High Bandwidth Memory chip tech, used in AI GPUs"
            className="w-full mt-1 px-3 py-2.5 bg-[#0d1117] border border-[#30363d] rounded-lg text-[#e6edf3] placeholder-[#6e7681] text-sm outline-none focus:border-[#484f58] transition-colors"
          />
          <p className="text-xs text-[#6e7681] mt-1">
            Help Claude understand the domain if it&apos;s an acronym or niche term.
          </p>
        </div>
        <button
          onClick={generate}
          disabled={!domain.trim() || loading}
          className="w-full py-2.5 bg-[#238636] hover:bg-[#2ea043] disabled:bg-[#1c2128] disabled:text-[#484f58] text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin">⟳</span> Writing emails…
            </span>
          ) : (
            'Generate Outreach →'
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 px-4 py-3 bg-red-900/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {targets.length > 0 && (
        <div>
          <p className="text-xs text-[#6e7681] font-medium uppercase tracking-wider mb-3">
            {targets.length} buyer profiles for {resultDomain}
          </p>
          <div className="space-y-3">
            {targets.map((t, i) => (
              <TargetCard key={i} t={t} index={i} />
            ))}
          </div>
          <p className="text-xs text-[#6e7681] mt-4 text-center">
            Tip: replace [Name] and [Your name] before sending. Keep it short — 3 sentences works better than 10.
          </p>
        </div>
      )}
    </div>
  );
}
