"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { StarRating } from "@/components/ui/StarRating";

interface AlbumRatingSectionProps {
  albumId: string;
}

export function AlbumRatingSection({ albumId }: AlbumRatingSectionProps) {
  const { data: session } = useSession();
  const [rating, setRating] = useState<number>(0);
  const [reviewBody, setReviewBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!rating) return;
    setSubmitting(true);

    try {
      if (rating) {
        await fetch("/api/ratings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ albumId, value: rating }),
        });
      }

      if (reviewBody.trim()) {
        await fetch("/api/reviews", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ albumId, body: reviewBody.trim(), rating }),
        });
      }

      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  }

  if (!session) {
    return (
      <p className="text-[#888] text-sm">
        <a href="/login" className="text-[#E8B84B] hover:underline">Log in</a> to rate and review this album.
      </p>
    );
  }

  if (submitted) {
    return (
      <div className="bg-[#1a1a1a] border border-[rgba(255,255,255,0.08)] rounded-lg p-4">
        <p className="text-[#E8B84B] text-sm font-medium">Your rating was saved!</p>
        <button onClick={() => setSubmitted(false)} className="text-[#888] text-xs mt-1 hover:underline">Edit</button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <p className="text-[#888] text-sm mb-2">Your rating</p>
        <StarRating value={rating} onChange={setRating} size="lg" />
      </div>

      <textarea
        value={reviewBody}
        onChange={(e) => setReviewBody(e.target.value)}
        placeholder="Write a review… (optional)"
        rows={3}
        className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-3 py-2 text-sm text-[#F5F2EB] placeholder-[#444] focus:outline-none focus:border-[#E8B84B] resize-none transition-colors"
      />

      <button
        type="submit"
        disabled={!rating || submitting}
        className="bg-[#E8B84B] text-black text-sm font-semibold px-5 py-2 rounded-full hover:bg-[#d4a43a] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Saving…" : "Save Rating"}
      </button>
    </form>
  );
}
