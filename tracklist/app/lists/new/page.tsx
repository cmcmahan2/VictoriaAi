"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import Link from "next/link";

export default function NewListPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (status === "unauthenticated") {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center">
        <p className="text-[#888] mb-4">Sign in to create lists.</p>
        <Link href="/login" className="text-[#E8B84B] hover:underline">Sign in</Link>
      </div>
    );
  }

  const user = session?.user as { name?: string | null } | undefined;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/lists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim(), description: description.trim(), isPublic }),
      });
      if (!res.ok) throw new Error("Failed to create list");
      const list = await res.json();
      router.push(`/lists/${list.id}`);
    } catch {
      setError("Failed to create list. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-10">
      <div className="mb-8">
        <Link href={`/user/${user?.name}`} className="text-[#888] text-sm hover:text-[#F5F2EB] transition-colors">
          ← Back
        </Link>
        <h1 className="text-3xl font-bold text-[#F5F2EB] mt-2" style={{ fontFamily: "Playfair Display, serif" }}>
          New List
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-[#888] text-sm mb-1.5">Title *</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="My favourite albums..."
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-4 py-3 text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
            required
          />
        </div>
        <div>
          <label className="block text-[#888] text-sm mb-1.5">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What's this list about?"
            rows={3}
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-4 py-3 text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors resize-none"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsPublic((v) => !v)}
            className={`w-12 h-6 rounded-full transition-colors relative ${isPublic ? "bg-[#E8B84B]" : "bg-[#333]"}`}
          >
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${isPublic ? "translate-x-6" : ""}`} />
          </button>
          <span className="text-[#888] text-sm">{isPublic ? "Public" : "Private"}</span>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading || !title.trim()}
          className="w-full bg-[#E8B84B] text-black font-semibold py-3 rounded-lg hover:bg-[#d4a43a] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Creating..." : "Create List"}
        </button>
      </form>
    </div>
  );
}
