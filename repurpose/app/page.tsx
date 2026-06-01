'use client';

import { useState } from 'react';

type Metadata = {
  title: string;
  description: string;
  tags: string[];
  hashtags: string[];
  hook: string;
};

type Privacy = 'private' | 'unlisted' | 'public';

export default function Home() {
  const [url, setUrl] = useState('');
  const [caption, setCaption] = useState('');
  const [channelContext, setChannelContext] = useState('');

  const [busy, setBusy] = useState<null | 'ingest' | 'publish'>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [jobId, setJobId] = useState<number | null>(null);
  const [localPath, setLocalPath] = useState<string | null>(null);
  const [platform, setPlatform] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<Metadata | null>(null);

  const [privacy, setPrivacy] = useState<Privacy>('private');
  const [watchUrl, setWatchUrl] = useState<string | null>(null);

  async function handleFetchAndGenerate() {
    setBusy('ingest');
    setError(null);
    setStatus('Downloading clip…');
    setMetadata(null);
    setWatchUrl(null);
    try {
      const ingest = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const ingestData = await ingest.json();
      if (!ingest.ok) throw new Error(ingestData?.error?.message || 'Download failed');

      setJobId(ingestData.jobId ?? null);
      setLocalPath(ingestData.localPath ?? null);
      setPlatform(ingestData.platform ?? null);
      const fetchedCaption = caption || ingestData.caption || '';
      setCaption(fetchedCaption);

      setStatus('Generating metadata…');
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jobId: ingestData.jobId ?? undefined,
          sourcePlatform: ingestData.platform,
          sourceCaption: fetchedCaption || null,
          transcript: ingestData.transcript || null,
          channelContext: channelContext || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Generation failed');
      setMetadata(data.metadata);
      setStatus('Ready to review.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
      setStatus(null);
    } finally {
      setBusy(null);
    }
  }

  async function handlePublish() {
    if (!metadata) return;
    setBusy('publish');
    setError(null);
    setStatus('Uploading to YouTube…');
    try {
      const res = await fetch('/api/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jobId, localPath, metadata, privacyStatus: privacy }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Publish failed');
      setWatchUrl(data.result.watchUrl);
      setStatus('Published!');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Publish failed');
      setStatus(null);
    } finally {
      setBusy(null);
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
            Caption <span className="text-[#6e7681]">(auto-filled after download — editable)</span>
          </span>
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            rows={3}
            placeholder="Pulled from the original post; tweak to steer the metadata."
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
          onClick={handleFetchAndGenerate}
          disabled={busy !== null || !url}
          className="rounded-md bg-[#1f6feb] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy === 'ingest' ? 'Working…' : 'Fetch & generate'}
        </button>

        {platform && <p className="text-xs text-[#6e7681]">Detected platform: {platform}</p>}
        {status && <p className="text-sm text-[#3fb950]">{status}</p>}
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

          <div className="flex items-center gap-3 pt-2">
            <select
              value={privacy}
              onChange={(e) => setPrivacy(e.target.value as Privacy)}
              className="rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm"
            >
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>

            <button
              onClick={handlePublish}
              disabled={busy !== null}
              className="rounded-md bg-[#3fb950] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy === 'publish' ? 'Publishing…' : 'Publish to YouTube'}
            </button>
          </div>

          {watchUrl && (
            <p className="text-sm text-[#3fb950]">
              Published →{' '}
              <a href={watchUrl} target="_blank" rel="noreferrer" className="underline">
                {watchUrl}
              </a>
            </p>
          )}
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
