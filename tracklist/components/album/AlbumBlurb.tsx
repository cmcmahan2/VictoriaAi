"use client";

import { useEffect, useState } from "react";

export function AlbumBlurb({ albumId }: { albumId: string }) {
  const [description, setDescription] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/album-blurb/${albumId}`)
      .then((r) => r.json())
      .then((data: { description?: string | null }) => setDescription(data.description ?? null))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [albumId]);

  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        <div className="h-3 bg-[#1a1a1a] rounded w-full" />
        <div className="h-3 bg-[#1a1a1a] rounded w-4/5" />
        <div className="h-3 bg-[#1a1a1a] rounded w-3/5" />
      </div>
    );
  }

  if (!description) return null;

  return (
    <p className="text-[#aaa] text-sm leading-relaxed italic border-l-2 border-[#E8B84B] pl-4">
      {description}
    </p>
  );
}
