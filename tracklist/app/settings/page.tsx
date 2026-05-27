"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Image from "next/image";

const GENRE_OPTIONS = [
  "Hip-Hop", "R&B", "Pop", "Rock", "Alternative Rock", "Indie Pop",
  "Electronic", "Jazz", "Soul", "Funk", "Folk", "Country", "Metal",
  "Synth-Pop", "Grunge", "Classical", "Reggae", "Latin", "Afrobeats",
];

interface ProfileData {
  username: string;
  email: string;
  displayName: string | null;
  bio: string | null;
  avatarUrl: string | null;
  website: string | null;
  location: string | null;
  favoriteGenres: string[];
}

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [form, setForm] = useState({
    displayName: "",
    bio: "",
    avatarUrl: "",
    website: "",
    location: "",
    favoriteGenres: [] as string[],
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
      return;
    }
    if (status !== "authenticated") return;

    fetch("/api/settings")
      .then((r) => r.json())
      .then((data: ProfileData) => {
        setProfile(data);
        setForm({
          displayName: data.displayName ?? "",
          bio: data.bio ?? "",
          avatarUrl: data.avatarUrl ?? "",
          website: data.website ?? "",
          location: data.location ?? "",
          favoriteGenres: data.favoriteGenres ?? [],
        });
      });
  }, [status, router]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    await fetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  function toggleGenre(genre: string) {
    setForm((prev) => ({
      ...prev,
      favoriteGenres: prev.favoriteGenres.includes(genre)
        ? prev.favoriteGenres.filter((g) => g !== genre)
        : [...prev.favoriteGenres, genre],
    }));
  }

  if (status === "loading" || !profile) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10 animate-pulse space-y-4">
        {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 bg-[#1a1a1a] rounded-xl" />)}
      </div>
    );
  }

  const user = session?.user as { name?: string | null };

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-[#F5F2EB] mb-8" style={{ fontFamily: "Playfair Display, serif" }}>
        Edit Profile
      </h1>

      <form onSubmit={save} className="space-y-6">
        {/* Avatar preview */}
        <div className="flex items-center gap-5">
          <div className="w-20 h-20 rounded-full overflow-hidden bg-[#1a1a1a] border-2 border-[rgba(255,255,255,0.1)] shrink-0">
            {form.avatarUrl ? (
              <Image src={form.avatarUrl} alt="Avatar" width={80} height={80} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-[#E8B84B] text-2xl font-bold">
                {(user?.name ?? "U")[0].toUpperCase()}
              </div>
            )}
          </div>
          <div className="flex-1">
            <label className="block text-[#888] text-xs uppercase tracking-widest mb-1.5">Avatar URL</label>
            <input
              type="url"
              value={form.avatarUrl}
              onChange={(e) => setForm((p) => ({ ...p, avatarUrl: e.target.value }))}
              placeholder="https://..."
              className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-xl px-4 py-2.5 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
            />
            <p className="text-[#444] text-xs mt-1">Paste a link to your image. Try Gravatar or Imgur.</p>
          </div>
        </div>

        {/* Username (read-only) */}
        <div>
          <label className="block text-[#888] text-xs uppercase tracking-widest mb-1.5">Username</label>
          <input
            type="text"
            value={profile.username}
            disabled
            className="w-full bg-[#0D0D0D] border border-[rgba(255,255,255,0.06)] rounded-xl px-4 py-2.5 text-sm text-[#555] cursor-not-allowed"
          />
          <p className="text-[#444] text-xs mt-1">Usernames cannot be changed.</p>
        </div>

        {/* Display name */}
        <div>
          <label className="block text-[#888] text-xs uppercase tracking-widest mb-1.5">Display Name</label>
          <input
            type="text"
            value={form.displayName}
            onChange={(e) => setForm((p) => ({ ...p, displayName: e.target.value }))}
            placeholder="Your name"
            maxLength={50}
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-xl px-4 py-2.5 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
          />
        </div>

        {/* Bio */}
        <div>
          <label className="block text-[#888] text-xs uppercase tracking-widest mb-1.5">Bio</label>
          <textarea
            value={form.bio}
            onChange={(e) => setForm((p) => ({ ...p, bio: e.target.value }))}
            placeholder="Tell people about your taste in music…"
            maxLength={300}
            rows={3}
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-xl px-4 py-2.5 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors resize-none"
          />
          <p className="text-[#444] text-xs mt-1 text-right">{form.bio.length}/300</p>
        </div>

        {/* Location */}
        <div>
          <label className="block text-[#888] text-xs uppercase tracking-widest mb-1.5">Location</label>
          <input
            type="text"
            value={form.location}
            onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
            placeholder="City, Country"
            maxLength={100}
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-xl px-4 py-2.5 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
          />
        </div>

        {/* Website */}
        <div>
          <label className="block text-[#888] text-xs uppercase tracking-widest mb-1.5">Website</label>
          <input
            type="url"
            value={form.website}
            onChange={(e) => setForm((p) => ({ ...p, website: e.target.value }))}
            placeholder="https://yoursite.com"
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-xl px-4 py-2.5 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
          />
        </div>

        {/* Favorite Genres */}
        <div>
          <label className="block text-[#888] text-xs uppercase tracking-widest mb-3">Favorite Genres</label>
          <div className="flex flex-wrap gap-2">
            {GENRE_OPTIONS.map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => toggleGenre(g)}
                className={`px-3 py-1.5 rounded-full text-xs transition-all border ${
                  form.favoriteGenres.includes(g)
                    ? "bg-[#E8B84B] border-[#E8B84B] text-black font-semibold"
                    : "bg-transparent border-[rgba(255,255,255,0.1)] text-[#888] hover:border-[#E8B84B] hover:text-[#E8B84B]"
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="bg-[#E8B84B] text-black font-semibold px-8 py-2.5 rounded-full hover:bg-[#d4a43a] disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
          {saved && <p className="text-[#E8B84B] text-sm">✓ Saved!</p>}
        </div>
      </form>
    </div>
  );
}
