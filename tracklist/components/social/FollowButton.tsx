"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

interface Props {
  targetUserId: string;
}

export function FollowButton({ targetUserId }: Props) {
  const { data: session } = useSession();
  const router = useRouter();
  const [following, setFollowing] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  const me = (session?.user as { id?: string })?.id;

  useEffect(() => {
    if (!me || me === targetUserId) return;
    fetch(`/api/follow?targetUserId=${targetUserId}`)
      .then((r) => r.json())
      .then((d) => setFollowing(d.following));
  }, [me, targetUserId]);

  if (!session || me === targetUserId) return null;

  async function toggle() {
    if (loading) return;
    if (!session) { router.push("/login"); return; }
    setLoading(true);
    try {
      const res = await fetch("/api/follow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ targetUserId }),
      });
      const data = await res.json();
      setFollowing(data.following);
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  if (following === null) {
    return <div className="w-24 h-9 bg-[#1a1a1a] rounded-full animate-pulse" />;
  }

  return (
    <button
      onClick={toggle}
      disabled={loading}
      className={`px-5 py-2 rounded-full text-sm font-semibold transition-colors ${
        following
          ? "bg-[rgba(255,255,255,0.08)] text-[#F5F2EB] hover:bg-[rgba(255,255,255,0.12)]"
          : "bg-[#E8B84B] text-black hover:bg-[#d4a43a]"
      } disabled:opacity-50`}
    >
      {loading ? "..." : following ? "Following" : "Follow"}
    </button>
  );
}
