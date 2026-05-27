"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

const GENRES = [
  { label: "Hip-Hop", emoji: "🎤" },
  { label: "R&B", emoji: "🎵" },
  { label: "Pop", emoji: "✨" },
  { label: "Rock", emoji: "🎸" },
  { label: "Alternative", emoji: "🌀" },
  { label: "Indie", emoji: "🌿" },
  { label: "Electronic", emoji: "⚡" },
  { label: "Jazz", emoji: "🎷" },
  { label: "Soul", emoji: "💿" },
  { label: "Funk", emoji: "🕺" },
  { label: "Folk", emoji: "🪕" },
  { label: "Country", emoji: "🤠" },
  { label: "Metal", emoji: "🤘" },
  { label: "Classical", emoji: "🎻" },
  { label: "Reggae", emoji: "🌴" },
  { label: "Latin", emoji: "💃" },
  { label: "Afrobeats", emoji: "🥁" },
  { label: "K-Pop", emoji: "🌸" },
];

export default function OnboardingPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [selected, setSelected] = useState<string[]>([]);
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  const user = session?.user as { name?: string | null } | undefined;

  function toggle(genre: string) {
    setSelected((prev) =>
      prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]
    );
  }

  async function finish() {
    setSaving(true);
    await fetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ favoriteGenres: selected, onboarded: true }),
    });
    router.push("/search");
  }

  if (step === 1) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-lg w-full text-center">
          <div className="flex justify-center gap-1 mb-6">
            <span className="w-3 h-3 rounded-full bg-[#E8B84B]" />
            <span className="w-3 h-3 rounded-full bg-[#888]" />
            <span className="w-3 h-3 rounded-full bg-[#444]" />
          </div>
          <h1 className="text-4xl font-bold text-[#F5F2EB] mb-3" style={{ fontFamily: "Playfair Display, serif" }}>
            Welcome{user?.name ? `, ${user.name}` : ""}!
          </h1>
          <p className="text-[#888] text-lg mb-8">
            Tracklist is your music diary. Rate albums, write reviews, discover what your friends are listening to.
          </p>
          <div className="grid grid-cols-3 gap-3 mb-8 text-left">
            {[
              { icon: "★", title: "Rate Albums", desc: "Give every album a score out of 5" },
              { icon: "♥", title: "Like Reviews", desc: "Save the reviews that speak to you" },
              { icon: "✦", title: "Follow Friends", desc: "See what they're listening to" },
            ].map((f) => (
              <div key={f.title} className="bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-4">
                <span className="text-[#E8B84B] text-xl">{f.icon}</span>
                <p className="text-[#F5F2EB] text-sm font-semibold mt-2 mb-1">{f.title}</p>
                <p className="text-[#555] text-xs">{f.desc}</p>
              </div>
            ))}
          </div>
          <button
            onClick={() => setStep(2)}
            className="bg-[#E8B84B] text-black font-semibold px-10 py-3 rounded-full hover:bg-[#d4a43a] transition-colors text-lg"
          >
            Let&apos;s go →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="max-w-lg w-full">
        <h2 className="text-2xl font-bold text-[#F5F2EB] mb-2 text-center" style={{ fontFamily: "Playfair Display, serif" }}>
          What do you listen to?
        </h2>
        <p className="text-[#888] text-center mb-8">Pick your genres — we&apos;ll use this to personalize your recommendations.</p>

        <div className="flex flex-wrap gap-2 justify-center mb-8">
          {GENRES.map((g) => (
            <button
              key={g.label}
              onClick={() => toggle(g.label)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-sm transition-all border ${
                selected.includes(g.label)
                  ? "bg-[#E8B84B] border-[#E8B84B] text-black font-semibold"
                  : "bg-[#111] border-[rgba(255,255,255,0.1)] text-[#888] hover:border-[#E8B84B] hover:text-[#E8B84B]"
              }`}
            >
              <span>{g.emoji}</span>
              <span>{g.label}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between">
          <button onClick={() => setStep(1)} className="text-[#555] text-sm hover:text-[#888] transition-colors">
            ← Back
          </button>
          <button
            onClick={finish}
            disabled={saving}
            className="bg-[#E8B84B] text-black font-semibold px-8 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors disabled:opacity-50"
          >
            {saving ? "Saving…" : selected.length > 0 ? `Continue with ${selected.length} genre${selected.length !== 1 ? "s" : ""}` : "Skip for now"}
          </button>
        </div>
      </div>
    </div>
  );
}
