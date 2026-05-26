'use client';

import { useEffect, useState } from 'react';

type Status = {
  godaddy: boolean;
  namecheap: boolean;
  resend: boolean;
  namebio: boolean;
  reddit: boolean;
  productHunt: boolean;
};

type TestResult = { ok: boolean; message?: string; error?: string; sample?: unknown };

function Badge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
        active ? 'bg-[#1a7f37]/20 text-[#3fb950]' : 'bg-[#30363d] text-[#8b949e]'
      }`}
    >
      {active ? 'Configured' : 'Not set'}
    </span>
  );
}

type Integration = {
  label: string;
  key: keyof Status;
  envVars: string[];
  description: string;
  docsUrl: string;
  testEndpoint?: string;
};

const INTEGRATIONS: Integration[] = [
  {
    label: 'GoDaddy GoValue',
    key: 'godaddy',
    envVars: ['GODADDY_API_KEY', 'GODADDY_API_SECRET'],
    description: 'Real appraisals via GoDaddy GoValue API. Fallback: Claude estimates.',
    docsUrl: 'https://developer.godaddy.com/keys',
    testEndpoint: '/api/settings/test-godaddy',
  },
  {
    label: 'Namecheap',
    key: 'namecheap',
    envVars: ['NAMECHEAP_API_USER', 'NAMECHEAP_API_KEY', 'NAMECHEAP_CLIENT_IP'],
    description: 'One-click domain registration through Namecheap.',
    docsUrl: 'https://www.namecheap.com/support/api/intro/',
  },
  {
    label: 'Resend',
    key: 'resend',
    envVars: ['RESEND_API_KEY'],
    description: 'Sends outreach emails to prospective buyers.',
    docsUrl: 'https://resend.com/api-keys',
  },
  {
    label: 'NameBio',
    key: 'namebio',
    envVars: ['NAMEBIO_API_KEY'],
    description: 'Real historical sale comps for more accurate valuations.',
    docsUrl: 'https://namebio.com/api',
  },
  {
    label: 'Reddit',
    key: 'reddit',
    envVars: ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET'],
    description: 'Scrapes trending subreddits for domain ideas.',
    docsUrl: 'https://www.reddit.com/prefs/apps',
  },
  {
    label: 'Product Hunt',
    key: 'productHunt',
    envVars: ['PRODUCT_HUNT_TOKEN'],
    description: 'Pulls trending products to surface domain opportunities.',
    docsUrl: 'https://www.producthunt.com/v2/oauth/applications',
  },
];

export default function SettingsPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, TestResult>>({});

  useEffect(() => {
    fetch('/api/settings/status')
      .then((r) => r.json())
      .then((data) => setStatus(data as Status))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  async function runTest(integration: Integration) {
    if (!integration.testEndpoint) return;
    setTesting(integration.key);
    try {
      const res = await fetch(integration.testEndpoint);
      const data = (await res.json()) as TestResult;
      setTestResult((prev) => ({ ...prev, [integration.key]: data }));
    } catch {
      setTestResult((prev) => ({
        ...prev,
        [integration.key]: { ok: false, error: 'Request failed — check your network.' },
      }));
    } finally {
      setTesting(null);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-[#e6edf3]">Settings</h1>
        <p className="mt-1 text-sm text-[#8b949e]">
          API keys are read from environment variables. Set them in your{' '}
          <a
            href="https://vercel.com/dashboard"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#58a6ff] underline"
          >
            Vercel project settings
          </a>{' '}
          under <span className="font-mono text-[#e6edf3]">Settings → Environment Variables</span>.
        </p>
      </div>

      {/* How-to card */}
      <div className="rounded-lg border border-[#30363d] bg-[#161b22] p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[#e6edf3]">How to add a key</h2>
        <ol className="text-sm text-[#8b949e] space-y-1 list-decimal list-inside">
          <li>
            Open your{' '}
            <a
              href="https://vercel.com/dashboard"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#58a6ff] underline"
            >
              Vercel dashboard
            </a>{' '}
            → select this project → <strong className="text-[#e6edf3]">Settings</strong> →{' '}
            <strong className="text-[#e6edf3]">Environment Variables</strong>.
          </li>
          <li>Click <strong className="text-[#e6edf3]">Add New</strong>, enter the variable name and value, tick all environments, click Save.</li>
          <li>
            <strong className="text-[#e6edf3]">Redeploy</strong> the project so the new variables are picked up (Deployments → ⋯ → Redeploy).
          </li>
          <li>Come back here and click <strong className="text-[#e6edf3]">Test</strong> to confirm the key works.</li>
        </ol>
      </div>

      {/* Integration rows */}
      <div className="space-y-3">
        {loading ? (
          <p className="text-sm text-[#8b949e]">Checking configuration…</p>
        ) : (
          INTEGRATIONS.map((integration) => {
            const active = status ? status[integration.key] : false;
            const result = testResult[integration.key];
            const isTesting = testing === integration.key;

            return (
              <div
                key={integration.key}
                className="rounded-lg border border-[#30363d] bg-[#161b22] p-4 space-y-2"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-[#e6edf3]">{integration.label}</span>
                    <Badge active={active} />
                  </div>
                  <div className="flex items-center gap-2">
                    <a
                      href={integration.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-[#58a6ff] hover:underline"
                    >
                      Get key ↗
                    </a>
                    {integration.testEndpoint && active && (
                      <button
                        onClick={() => runTest(integration)}
                        disabled={isTesting}
                        className="px-3 py-1 rounded text-xs font-medium bg-[#21262d] hover:bg-[#30363d] text-[#e6edf3] disabled:opacity-50 transition-colors"
                      >
                        {isTesting ? 'Testing…' : 'Test'}
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-xs text-[#8b949e]">{integration.description}</p>

                <div className="flex flex-wrap gap-2">
                  {integration.envVars.map((v) => (
                    <code
                      key={v}
                      className="text-xs px-1.5 py-0.5 rounded bg-[#0d1117] text-[#79c0ff] font-mono"
                    >
                      {v}
                    </code>
                  ))}
                </div>

                {result && (
                  <div
                    className={`mt-1 text-xs px-3 py-2 rounded ${
                      result.ok
                        ? 'bg-[#1a7f37]/10 text-[#3fb950]'
                        : 'bg-[#da3633]/10 text-[#f85149]'
                    }`}
                  >
                    {result.ok ? result.message : result.error}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* GoDaddy quick-start callout */}
      <div className="rounded-lg border border-[#d29922]/40 bg-[#d29922]/5 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-[#d29922]">GoDaddy GoValue — quick setup</h3>
        <p className="text-xs text-[#8b949e]">
          GoDaddy's API uses a key + secret pair. Both come from the same developer portal page.
        </p>
        <ol className="text-xs text-[#8b949e] space-y-1 list-decimal list-inside">
          <li>
            Go to{' '}
            <a
              href="https://developer.godaddy.com/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#58a6ff] underline"
            >
              developer.godaddy.com/keys
            </a>{' '}
            and sign in with your GoDaddy account.
          </li>
          <li>Click <strong className="text-[#e6edf3]">Create New Key</strong> → choose <strong className="text-[#e6edf3]">Production</strong>.</li>
          <li>
            Copy the <strong className="text-[#e6edf3]">Key</strong> → paste it as{' '}
            <code className="font-mono text-[#79c0ff]">GODADDY_API_KEY</code> in Vercel.
          </li>
          <li>
            Copy the <strong className="text-[#e6edf3]">Secret</strong> → paste it as{' '}
            <code className="font-mono text-[#79c0ff]">GODADDY_API_SECRET</code> in Vercel.
          </li>
          <li>Redeploy → come back here → click <strong className="text-[#e6edf3]">Test</strong>.</li>
        </ol>
      </div>
    </div>
  );
}
