'use client';

import { useState } from 'react';

type Idea = { matchup: string; sport: string; angle: string; viralReason: string };
type PlayerProfile = { name: string; oneLiner: string; accolades: string[]; wikiTitle: string };
type StatRow = { label: string; a: string; b: string; edge: 'A' | 'B' | 'EVEN' };
type Plan = {
  matchup: string;
  sport: string;
  playerA: PlayerProfile;
  playerB: PlayerProfile;
  statRows: StatRow[];
  hook: string;
  narration: string[];
  verdict: string;
  youtube: { title: string; description: string; tags: string[]; hashtags: string[] };
  statsDisclaimer: string;
};

export default function Home() {
  const [matchup, setMatchup] = useState('');
  const [sportFilter, setSportFilter] = useState('');
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState<null | 'ideas' | 'plan'>(null);
  const [error, setError] = useState<string | null>(null);

  // Video production + upload
  const [producing, setProducing] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoPath, setVideoPath] = useState<string | null>(null);
  const [uploadMeta, setUploadMeta] = useState<Record<string, unknown> | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [privacy, setPrivacy] = useState<'private' | 'unlisted' | 'public'>('private');
  const [uploading, setUploading] = useState(false);
  const [watchUrl, setWatchUrl] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Editor settings
  const [speed, setSpeed] = useState(1.75);

  function resetVideo() {
    setVideoUrl(null);
    setVideoPath(null);
    setUploadMeta(null);
    setJobId(null);
    setWatchUrl(null);
    setNotice(null);
  }

  async function generateVideo() {
    if (!plan) return;
    setProducing(true);
    setError(null);
    resetVideo();
    setNotice('Producing video — photos, voice, and assembly. This can take a minute…');
    try {
      const res = await fetch('/api/produce', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan, speed }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Video production failed');
      setVideoUrl(data.videoUrl);
      setVideoPath(data.videoPath ?? null);
      setUploadMeta(data.metadata ?? null);
      setJobId(data.jobId);
      setNotice('Video ready — review it below.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
      setNotice(null);
    } finally {
      setProducing(false);
    }
  }

  async function uploadVideo() {
    if (!videoPath && jobId === null) return;
    setUploading(true);
    setError(null);
    setNotice('Uploading to YouTube…');
    try {
      const res = await fetch('/api/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Send localPath + metadata so upload works with or without a DB.
        body: JSON.stringify({ jobId, localPath: videoPath, metadata: uploadMeta, privacyStatus: privacy }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Upload failed');
      setWatchUrl(data.result.watchUrl);
      setNotice('Published!');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
      setNotice(null);
    } finally {
      setUploading(false);
    }
  }

  async function suggestIdeas() {
    setBusy('ideas');
    setError(null);
    try {
      const res = await fetch('/api/ideas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: 8, sportFilter: sportFilter || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Could not generate ideas');
      setIdeas(data.ideas);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setBusy(null);
    }
  }

  async function makeVideo(target?: string) {
    const m = (target ?? matchup).trim();
    if (!m) return;
    setMatchup(m);
    setBusy('plan');
    setError(null);
    setPlan(null);
    resetVideo();
    try {
      const res = await fetch('/api/matchup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ matchup: m }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Could not build the matchup');
      setPlan(data.plan);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-semibold">🏀 Matchup Maker</h1>
      <p className="mt-1 text-sm text-[#8b949e]">
        What are we making today? Type a debate, or get ideas — then generate the full plan.
      </p>

      {/* Prompt box */}
      <div className="mt-8 space-y-4 rounded-lg border border-[#30363d] bg-[#161b22] p-5">
        <label className="block">
          <span className="text-sm text-[#8b949e]">Make a video:</span>
          <div className="mt-1 flex gap-2">
            <input
              value={matchup}
              onChange={(e) => setMatchup(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && makeVideo()}
              placeholder="Jordan vs LeBron"
              className="flex-1 rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm outline-none focus:border-[#1f6feb]"
            />
            <button
              onClick={() => makeVideo()}
              disabled={busy !== null || !matchup.trim()}
              className="rounded-md bg-[#1f6feb] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy === 'plan' ? 'Building…' : 'Generate'}
            </button>
          </div>
        </label>

        <div className="flex items-center gap-2 pt-1">
          <input
            value={sportFilter}
            onChange={(e) => setSportFilter(e.target.value)}
            placeholder="any sport"
            className="w-40 rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm outline-none focus:border-[#1f6feb]"
          />
          <button
            onClick={suggestIdeas}
            disabled={busy !== null}
            className="rounded-md border border-[#30363d] px-4 py-2 text-sm text-[#e6edf3] disabled:opacity-50"
          >
            {busy === 'ideas' ? 'Thinking…' : '💡 Suggest ideas'}
          </button>
        </div>

        {error && <p className="text-sm text-[#f85149]">{error}</p>}
      </div>

      {/* Idea list */}
      {ideas.length > 0 && !plan && (
        <div className="mt-6 grid gap-2 sm:grid-cols-2">
          {ideas.map((idea, i) => (
            <button
              key={i}
              onClick={() => makeVideo(idea.matchup)}
              disabled={busy !== null}
              className="rounded-lg border border-[#30363d] bg-[#161b22] p-4 text-left hover:border-[#1f6feb] disabled:opacity-50"
            >
              <div className="font-medium text-[#e6edf3]">{idea.matchup}</div>
              <div className="mt-1 text-xs uppercase tracking-wide text-[#6e7681]">{idea.sport}</div>
              <div className="mt-2 text-sm text-[#8b949e]">{idea.angle}</div>
            </button>
          ))}
        </div>
      )}

      {/* Plan review */}
      {plan && (
        <div className="mt-6 space-y-6 rounded-lg border border-[#30363d] bg-[#161b22] p-5">
          {/* VS header */}
          <div className="flex items-center justify-between gap-4 text-center">
            <PlayerHead p={plan.playerA} />
            <div className="text-xl font-bold text-[#ffa657]">VS</div>
            <PlayerHead p={plan.playerB} />
          </div>

          {/* Stat table */}
          <div className="overflow-hidden rounded-md border border-[#30363d]">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#1c2128] text-[#8b949e]">
                  <th className="px-3 py-2 text-right">{plan.playerA.name}</th>
                  <th className="px-3 py-2 text-center text-[#6e7681]">Stat</th>
                  <th className="px-3 py-2 text-left">{plan.playerB.name}</th>
                </tr>
              </thead>
              <tbody>
                {plan.statRows.map((row, i) => (
                  <tr key={i} className="border-t border-[#30363d]">
                    <td className={`px-3 py-2 text-right ${row.edge === 'A' ? 'font-bold text-[#3fb950]' : ''}`}>{row.a}</td>
                    <td className="px-3 py-2 text-center text-[#6e7681]">{row.label}</td>
                    <td className={`px-3 py-2 text-left ${row.edge === 'B' ? 'font-bold text-[#3fb950]' : ''}`}>{row.b}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-[#d29922]">⚠️ {plan.statsDisclaimer}</p>

          {/* Script */}
          <Section title="Hook">
            <p className="text-[#e6edf3]">{plan.hook}</p>
          </Section>
          <Section title="Narration (voiceover beats)">
            <ol className="list-decimal space-y-1 pl-5 text-[#e6edf3]">
              {plan.narration.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ol>
          </Section>
          <Section title="Verdict / vote">
            <p className="text-[#58a6ff]">{plan.verdict}</p>
          </Section>

          {/* YouTube metadata */}
          <Section title="YouTube title">
            <p className="text-[#e6edf3]">{plan.youtube.title}</p>
          </Section>
          <Section title="Tags">
            <p className="text-[#8b949e]">{plan.youtube.tags.join(', ')}</p>
          </Section>
          <Section title="Hashtags">
            <p className="text-[#58a6ff]">{plan.youtube.hashtags.join(' ')}</p>
          </Section>

          {/* Produce + upload */}
          <div className="space-y-4 rounded-md border border-[#30363d] bg-[#0d1117] p-4">
            {/* Editor settings */}
            <div className="flex flex-wrap items-center gap-3 border-b border-[#30363d] pb-3">
              <span className="text-xs uppercase tracking-wide text-[#6e7681]">🎚️ Editor</span>
              <label className="flex items-center gap-2 text-sm text-[#8b949e]">
                Narration speed
                <select
                  value={speed}
                  onChange={(e) => setSpeed(Number(e.target.value))}
                  className="rounded-md border border-[#30363d] bg-[#0d1117] px-2 py-1 text-sm text-[#e6edf3]"
                >
                  <option value={1}>1x</option>
                  <option value={1.25}>1.25x</option>
                  <option value={1.5}>1.5x</option>
                  <option value={1.75}>1.75x</option>
                  <option value={2}>2x</option>
                </select>
              </label>
            </div>

            {!videoUrl && (
              <button
                onClick={generateVideo}
                disabled={producing}
                className="rounded-md bg-[#ffa657] px-4 py-2 text-sm font-semibold text-black disabled:opacity-50"
              >
                {producing ? '🎬 Producing…' : '🎬 Generate video'}
              </button>
            )}

            {notice && <p className="text-sm text-[#3fb950]">{notice}</p>}

            {videoUrl && (
              <>
                <video
                  src={videoUrl}
                  controls
                  playsInline
                  className="mx-auto max-h-[70vh] rounded-md border border-[#30363d]"
                />

                <div className="flex flex-wrap items-center gap-3">
                  <select
                    value={privacy}
                    onChange={(e) => setPrivacy(e.target.value as typeof privacy)}
                    className="rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm"
                  >
                    <option value="private">Private</option>
                    <option value="unlisted">Unlisted</option>
                    <option value="public">Public</option>
                  </select>

                  <button
                    onClick={uploadVideo}
                    disabled={uploading}
                    className="rounded-md bg-[#3fb950] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {uploading ? 'Uploading…' : '⬆️ Upload to YouTube'}
                  </button>

                  <button
                    onClick={generateVideo}
                    disabled={producing}
                    className="rounded-md border border-[#30363d] px-4 py-2 text-sm text-[#8b949e] disabled:opacity-50"
                  >
                    Re-generate
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
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PlayerHead({ p }: { p: PlayerProfile }) {
  return (
    <div className="flex-1">
      <div className="text-base font-semibold text-[#e6edf3]">{p.name}</div>
      <div className="mt-1 text-xs text-[#8b949e]">{p.oneLiner}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-xs uppercase tracking-wide text-[#6e7681]">{title}</div>
      {children}
    </div>
  );
}
