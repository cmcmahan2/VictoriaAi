'use client';

import { useState } from 'react';

type Metadata = {
  title: string;
  description: string;
  tags: string[];
  hashtags: string[];
  hook: string;
};

export default function Home() {
  const [url, setUrl] = useState('');
  const [caption, setCaption] = useState('');
  const [channelContext, setChannelContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [platform, setPlatform] = useState<string | null>(null);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setMetadata(null);
    try {
      // Probe ingest so we can show detected platform (downloader lands step 2).
      const ingest = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const ingestData = await ingest.json();
      if (ingestData.platform) setPlatform(ingestData.platform);

      // Generate metadata from whatever context we have today.
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sourcePlatform: ingestData.platform,
          sourceCaption: caption || null,
          channelContext: channelContext || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Generation failed');
      setMetadata(data.metadata);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-semibold">Repurpose Engine</h1>
      <p className="mt-1 text-sm text-[#8b949e]">
        Paste a TikTok / Reel / Short link, generate YouTube Shorts metadata with Claude, then publish.
      </p>

      <div className="mt-8 space-y-4 rounded-lg border border-[#30363d] bg-[#161b22] p-5">
        <label className="block">
          <span className="text-sm text-[#8b949e]">Source link</span>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.tiktok.com/@you/video/..."
            className="mt-1 w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm outline-none focus:border-[#1f6feb]"
          />
        </label>

        <label className="block">
          <span className="text-sm text-[#8b949e]">
            Original caption <span className="text-[#6e7681]">(optional — until auto-fetch lands in step 2)</span>
          </span>
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            rows={3}
            placeholder="Paste the caption from the original post for better metadata."
            className="mt-1 w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm outline-none focus:border-[#1f6feb]"
          />
        </label>

        <label className="block">
          <span className="text-sm text-[#8b949e]">
            Channel context <span className="text-[#6e7681]">(optional — your niche/tone)</span>
          </span>
          <input
            value={channelContext}
            onChange={(e) => setChannelContext(e.target.value)}
            placeholder="e.g. street food reviews, casual and funny"
            className="mt-1 w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm outline-none focus:border-[#1f6feb]"
          />
        </label>

        <button
          onClick={handleGenerate}
          disabled={loading || !url}
          className="rounded-md bg-[#1f6feb] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? 'Generating…' : 'Generate metadata'}
        </button>

        {platform && (
          <p className="text-xs text-[#6e7681]">Detected platform: {platform}</p>
        )}
        {error && <p className="text-sm text-[#f85149]">{error}</p>}
      </div>

      {metadata && (
        <div className="mt-6 space-y-4 rounded-lg border border-[#30363d] bg-[#161b22] p-5">
          <h2 className="text-lg font-medium">Review</h2>

          <Field label="Title">
            <input
              value={metadata.title}
              onChange={(e) => setMetadata({ ...metadata, title: e.target.value })}
              className="w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Hook">
            <input
              value={metadata.hook}
              onChange={(e) => setMetadata({ ...metadata, hook: e.target.value })}
              className="w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Description">
            <textarea
              value={metadata.description}
              onChange={(e) => setMetadata({ ...metadata, description: e.target.value })}
              rows={4}
              className="w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm"
            />
          </Field>

          <Field label="Tags">
            <p className="text-sm text-[#e6edf3]">{metadata.tags.join(', ')}</p>
          </Field>

          <Field label="Hashtags">
            <p className="text-sm text-[#58a6ff]">{metadata.hashtags.join(' ')}</p>
          </Field>

          <button
            disabled
            title="Publishing lands with the YouTube upload step"
            className="rounded-md border border-[#30363d] px-4 py-2 text-sm text-[#6e7681]"
          >
            Publish to YouTube (coming soon)
          </button>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-xs uppercase tracking-wide text-[#6e7681]">{label}</div>
      {children}
    </div>
  );
}
