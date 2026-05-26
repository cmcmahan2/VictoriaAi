'use client';

import { useState } from 'react';

type ServiceStatus = 'idle' | 'testing' | 'ok' | 'error';

type Integration = {
  id: string;
  name: string;
  description: string;
  envVars: string[];
  getKeyUrl: string;
  notes?: string;
};

const INTEGRATIONS: Integration[] = [
  {
    id: 'godaddy',
    name: 'GoDaddy GoValue',
    description: 'Real appraisals via GoDaddy GoValue API. Fallback: Claude estimates.',
    envVars: ['GODADDY_API_KEY', 'GODADDY_API_SECRET'],
    getKeyUrl: 'https://developer.godaddy.com/keys',
    notes: 'Requires a production API key. OTE (sandbox) keys will not work with the GoValue endpoint.',
  },
  {
    id: 'namecheap',
    name: 'Namecheap',
    description: 'One-click domain registration through Namecheap.',
    envVars: ['NAMECHEAP_API_USER', 'NAMECHEAP_API_KEY', 'NAMECHEAP_CLIENT_IP'],
    getKeyUrl: 'https://ap.www.namecheap.com/settings/tools/apiaccess',
    notes: 'Enable API access and whitelist your Vercel deployment IP in Namecheap settings.',
  },
  {
    id: 'resend',
    name: 'Resend',
    description: 'Sends outreach emails to prospective buyers.',
    envVars: ['RESEND_API_KEY'],
    getKeyUrl: 'https://resend.com/api-keys',
  },
  {
    id: 'namebio',
    name: 'NameBio',
    description: 'Real historical sale comps for more accurate valuations.',
    envVars: ['NAMEBIO_API_KEY'],
    getKeyUrl: 'https://namebio.com/api',
  },
];

function isConfigured(envVars: string[]): boolean {
  // We can't read env vars client-side — the test endpoint tells us.
  // This is only used to show "Configured" vs "Not set" based on test result.
  return false; // determined by test result
}

function StatusBadge({ status, tested }: { status: ServiceStatus; tested: boolean }) {
  if (!tested) {
    return (
      <span className="text-xs px-2 py-0.5 rounded border border-[#30363d] text-[#8b949e] bg-[#161b22]">
        Not tested
      </span>
    );
  }
  if (status === 'ok') {
    return (
      <span className="text-xs px-2 py-0.5 rounded border border-green-400/30 text-green-400 bg-green-400/10">
        Configured
      </span>
    );
  }
  return (
    <span className="text-xs px-2 py-0.5 rounded border border-[#30363d] text-[#8b949e] bg-[#161b22]">
      Not set
    </span>
  );
}

function IntegrationCard({ integration }: { integration: Integration }) {
  const [status, setStatus] = useState<ServiceStatus>('idle');
  const [tested, setTested] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function runTest() {
    setStatus('testing');
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/settings/test?service=${integration.id}`);
      const data = (await res.json()) as { ok: boolean; error?: string };
      setTested(true);
      if (data.ok) {
        setStatus('ok');
      } else {
        setStatus('error');
        setErrorMsg(data.error ?? 'Test failed.');
      }
    } catch {
      setTested(true);
      setStatus('error');
      setErrorMsg('Could not reach test endpoint.');
    }
  }

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-[#e6edf3] font-semibold">{integration.name}</h3>
            <StatusBadge status={status} tested={tested} />
          </div>
          <p className="text-sm text-[#8b949e] mt-1">{integration.description}</p>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {integration.envVars.map((v) => (
              <code
                key={v}
                className="text-xs px-1.5 py-0.5 rounded bg-[#0d1117] border border-[#30363d] text-[#79c0ff] font-mono"
              >
                {v}
              </code>
            ))}
          </div>
          {integration.notes && (
            <p className="text-xs text-[#6e7681] mt-2 italic">{integration.notes}</p>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <a
            href={integration.getKeyUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[#58a6ff] hover:underline whitespace-nowrap"
          >
            Get key ↗
          </a>
          <button
            onClick={runTest}
            disabled={status === 'testing'}
            className={`text-sm px-3 py-1.5 rounded border transition-colors ${
              status === 'testing'
                ? 'border-[#30363d] text-[#6e7681] cursor-not-allowed'
                : 'border-[#30363d] text-[#e6edf3] hover:border-[#58a6ff] hover:text-[#58a6ff] cursor-pointer'
            }`}
          >
            {status === 'testing' ? '…' : 'Test'}
          </button>
        </div>
      </div>

      {status === 'error' && errorMsg && (
        <div className="mt-3 px-3 py-2 bg-red-900/20 border border-red-500/30 rounded text-sm text-red-300">
          {errorMsg}
        </div>
      )}
      {status === 'ok' && (
        <div className="mt-3 px-3 py-2 bg-green-900/20 border border-green-500/30 rounded text-sm text-green-300">
          Connection verified successfully.
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold text-[#e6edf3] mb-2">Settings</h1>
      <p className="text-sm text-[#8b949e] mb-6">
        API keys are read from environment variables. Set them in your{' '}
        <a
          href="https://vercel.com/dashboard"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#58a6ff] hover:underline"
        >
          Vercel project settings
        </a>{' '}
        under <code className="text-xs bg-[#161b22] border border-[#30363d] px-1 py-0.5 rounded">Settings → Environment Variables</code>.
      </p>

      {/* How to add a key */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-lg p-5 mb-6">
        <h2 className="text-sm font-semibold text-[#e6edf3] mb-3">How to add a key</h2>
        <ol className="space-y-1.5 text-sm text-[#8b949e] list-decimal list-inside">
          <li>
            Open your{' '}
            <a
              href="https://vercel.com/dashboard"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#58a6ff] hover:underline"
            >
              Vercel dashboard
            </a>{' '}
            → select this project → <strong className="text-[#e6edf3]">Settings</strong> →{' '}
            <strong className="text-[#e6edf3]">Environment Variables</strong>.
          </li>
          <li>
            Click <strong className="text-[#e6edf3]">Add New</strong>, enter the variable name and value,
            tick all environments, click Save.
          </li>
          <li>
            <strong className="text-[#e6edf3]">Redeploy</strong> the project so the new variables are
            picked up (Deployments → ··· → Redeploy).
          </li>
          <li>
            Come back here and click <strong className="text-[#e6edf3]">Test</strong> to confirm the key
            works.
          </li>
        </ol>
      </div>

      {/* Integration cards */}
      <div className="flex flex-col gap-4">
        {INTEGRATIONS.map((integration) => (
          <IntegrationCard key={integration.id} integration={integration} />
        ))}
      </div>
    </div>
  );
}
