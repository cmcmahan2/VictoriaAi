export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { ReviewComments } from "@/components/album/ReviewComments";

function stars(n: number | null) {
  if (n == null) return null;
  const full = Math.round(n);
  return "★".repeat(full) + "☆".repeat(5 - full);
}

function timeAgo(date: Date) {
  const diff = Date.now() - date.getTime();
  const d = Math.floor(diff / 86400000);
  if (d === 0) return "today";
  if (d === 1) return "yesterday";
  if (d < 30) return `${d} days ago`;
  return date.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}

export default async function ReviewPage({ params }: { params: Promise<{ reviewId: string }> }) {
  const { reviewId } = await params;

  const review = await prisma.review.findUnique({
    where: { id: reviewId },
    include: {
      user: { select: { id: true, username: true, avatarUrl: true, displayName: true } },
      album: true,
    },
  });

  if (!review) notFound();

  // Related reviews of the same album
  const otherReviews = await prisma.review.findMany({
    where: { albumId: review.albumId, id: { not: reviewId } },
    orderBy: { likes: "desc" },
    take: 3,
    include: { user: { select: { username: true, avatarUrl: true } } },
  });

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      {/* Album context bar */}
      <Link href={`/album/${review.album.id}`} className="flex items-center gap-3 mb-8 group">
        {review.album.coverUrl ? (
          <Image src={review.album.coverUrl} alt={review.album.title} width={56} height={56} className="rounded-lg" />
        ) : (
          <div className="w-14 h-14 bg-[#1a1a1a] rounded-lg flex items-center justify-center text-[#444]">♪</div>
        )}
        <div>
          <p className="text-[#888] text-xs uppercase tracking-widest">Review of</p>
          <p className="text-[#F5F2EB] font-semibold group-hover:text-[#E8B84B] transition-colors">{review.album.title}</p>
          <p className="text-[#555] text-xs">{review.album.artistName} · {review.album.releaseYear}</p>
        </div>
      </Link>

      {/* Review card */}
      <div className="bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-2xl p-6 mb-8">
        <div className="flex items-center gap-3 mb-4">
          <Link href={`/user/${review.user.username}`}>
            <UserAvatar username={review.user.username} avatarUrl={review.user.avatarUrl} size={40} />
          </Link>
          <div>
            <Link href={`/user/${review.user.username}`} className="text-[#F5F2EB] font-semibold hover:text-[#E8B84B] transition-colors text-sm">
              {review.user.displayName ?? review.user.username}
            </Link>
            <p className="text-[#555] text-xs">{timeAgo(review.createdAt)}</p>
          </div>
          {review.rating != null && (
            <div className="ml-auto">
              <span className="text-[#E8B84B] text-lg">{stars(review.rating)}</span>
              <span className="text-[#888] text-xs ml-1">{review.rating}/5</span>
            </div>
          )}
        </div>

        <p className="text-[#F5F2EB] leading-relaxed text-sm whitespace-pre-wrap">{review.body}</p>

        <div className="flex items-center gap-4 mt-5 pt-4 border-t border-[rgba(255,255,255,0.06)]">
          <span className="text-[#555] text-xs">♥ {review.likes} likes</span>
          <Link href={`/album/${review.album.id}`} className="text-[#555] text-xs hover:text-[#E8B84B] transition-colors ml-auto">
            See all reviews →
          </Link>
        </div>
      </div>

      {/* Comments */}
      <section className="mb-10">
        <h2 className="text-lg font-semibold text-[#F5F2EB] mb-4" style={{ fontFamily: "Playfair Display, serif" }}>
          Comments
        </h2>
        <ReviewComments reviewId={reviewId} />
      </section>

      {/* Other reviews of same album */}
      {otherReviews.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">
            More reviews of {review.album.title}
          </h2>
          <div className="space-y-4">
            {otherReviews.map((r) => (
              <Link key={r.id} href={`/review/${r.id}`} className="block bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-xl p-4 hover:border-[rgba(255,255,255,0.15)] transition-colors group">
                <div className="flex items-center gap-2 mb-2">
                  <UserAvatar username={r.user.username} avatarUrl={r.user.avatarUrl} size={22} />
                  <span className="text-[#888] text-xs">{r.user.username}</span>
                  {r.rating != null && <span className="text-[#E8B84B] text-xs ml-auto">{"★".repeat(Math.round(r.rating))}</span>}
                </div>
                <p className="text-[#F5F2EB] text-sm line-clamp-2 group-hover:text-[#E8B84B] transition-colors">{r.body}</p>
                <p className="text-[#555] text-xs mt-1.5">♥ {r.likes} likes</p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
