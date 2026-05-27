"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

export function WatchlistButton({ albumId }: { albumId: string }) {
  const { data: session } = useSession();
  const router = useRouter();
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session) { setLoading(false); return; }
    fetch(`/api/watchlist/check?albumId=${albumId}`)
      .then((r) => r.json())
      .then((d) => { setSaved(d.saved); setLoading(false); });
  }, [albumId, session]);

  async function toggle() {
    if (!session) { router.push("/login"); return; }
    const prev = saved;
    setSaved(!prev);
    const res = await fetch("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ albumId }),
    });
    const data = await res.json();
    setSaved(data.saved);
  }

  if (loading) return <div className="w-32 h-9 bg-[#1a1a1a] rounded-full animate-pulse" />;

  return (
    <button
      onClick={toggle}
      className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all border ${
        saved
          ? "bg-[#E8B84B] border-[#E8B84B] text-black"
          : "bg-transparent border-[rgba(255,255,255,0.15)] text-[#888] hover:border-[#E8B84B] hover:text-[#E8B84B]"
      }`}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill={saved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
      </svg>
      {saved ? "Saved" : "Want to Listen"}
    </button>
  );
}
