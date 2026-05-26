'use client';

import { useState } from 'react';

type SendState = 'idle' | 'sending' | 'sent' | 'error';

function Field({
  label,
  id,
  type = 'text',
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  id: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm text-[#e6edf3] mb-1.5">
        {label}
        {required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-md bg-[#0d1117] border border-[#30363d] text-[#e6edf3] text-sm placeholder-[#484f58] focus:outline-none focus:border-[#58a6ff] transition-colors"
      />
    </div>
  );
}

export default function OutreachPage() {
  const [to, setTo] = useState('');
  const [domain, setDomain] = useState('');
  const [askPrice, setAskPrice] = useState('');
  const [senderName, setSenderName] = useState('');
  const [senderEmail, setSenderEmail] = useState('');
  const [buyerProfile, setBuyerProfile] = useState('');

  const [state, setState] = useState<SendState>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [sentId, setSentId] = useState<string | null>(null);

  const sending = state === 'sending';

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (sending) return;

    setState('sending');
    setErrorMsg(null);
    setSentId(null);

    try {
      const res = await fetch('/api/outreach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to,
          domain,
          askPrice: Number(askPrice),
          senderName,
          senderEmail,
          buyerProfile: buyerProfile || undefined,
        }),
      });
      const data = (await res.json()) as { ok: boolean; id?: string; error?: string };
      if (data.ok) {
        setState('sent');
        setSentId(data.id ?? null);
      } else {
        setState('error');
        setErrorMsg(data.error ?? 'Failed to send.');
      }
    } catch {
      setState('error');
      setErrorMsg('Could not reach the outreach endpoint.');
    }
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-semibold text-[#e6edf3] mb-1">Outreach</h1>
      <p className="text-sm text-[#8b949e] mb-6">
        Send a personalised acquisition offer to a prospective buyer. Requires{' '}
        <code className="text-xs bg-[#161b22] border border-[#30363d] px-1 py-0.5 rounded text-[#79c0ff]">
          RESEND_API_KEY
        </code>{' '}
        — add it in{' '}
        <a href="/settings" className="text-[#58a6ff] hover:underline">
          Settings
        </a>
        .
      </p>

      {state === 'sent' ? (
        <div className="bg-green-900/20 border border-green-500/30 rounded-lg p-5 text-center">
          <p className="text-green-300 font-medium">Email sent successfully.</p>
          {sentId && <p className="text-xs text-[#6e7681] mt-1">Resend ID: {sentId}</p>}
          <button
            onClick={() => {
              setState('idle');
              setTo('');
              setDomain('');
              setAskPrice('');
            }}
            className="mt-4 text-sm text-[#58a6ff] hover:underline"
          >
            Send another
          </button>
        </div>
      ) : (
        <form onSubmit={send} className="flex flex-col gap-4">
          <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-5 flex flex-col gap-4">
            <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Domain</h2>
            <Field
              label="Domain name"
              id="domain"
              value={domain}
              onChange={setDomain}
              placeholder="cursorflow.com"
              required
            />
            <Field
              label="Ask price (USD)"
              id="askPrice"
              type="number"
              value={askPrice}
              onChange={setAskPrice}
              placeholder="2500"
              required
            />
            <Field
              label="Likely buyer profile (optional)"
              id="buyerProfile"
              value={buyerProfile}
              onChange={setBuyerProfile}
              placeholder="AI dev-tool startups"
            />
          </div>

          <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-5 flex flex-col gap-4">
            <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Recipient</h2>
            <Field
              label="Buyer email"
              id="to"
              type="email"
              value={to}
              onChange={setTo}
              placeholder="founder@startup.com"
              required
            />
          </div>

          <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-5 flex flex-col gap-4">
            <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">From</h2>
            <Field
              label="Your name"
              id="senderName"
              value={senderName}
              onChange={setSenderName}
              placeholder="Chris McMahan"
              required
            />
            <Field
              label="Your email (must be verified in Resend)"
              id="senderEmail"
              type="email"
              value={senderEmail}
              onChange={setSenderEmail}
              placeholder="chris@yourdomain.com"
              required
            />
          </div>

          {state === 'error' && errorMsg && (
            <div className="bg-red-900/20 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-300">
              {errorMsg}
            </div>
          )}

          <button
            type="submit"
            disabled={sending}
            className={`px-5 py-2.5 rounded-md text-sm font-medium transition-all ${
              sending
                ? 'bg-[#1c2128] text-[#6e7681] cursor-not-allowed'
                : 'bg-[#238636] hover:bg-[#2ea043] text-white cursor-pointer'
            }`}
          >
            {sending ? 'Sending…' : 'Send Outreach Email'}
          </button>
        </form>
      )}
    </div>
  );
}
