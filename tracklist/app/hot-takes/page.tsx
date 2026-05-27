export const dynamic = "force-dynamic";

import Link from "next/link";
import Image from "next/image";
import { prisma } from "@/lib/prisma";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { StarRating } from "@/components/ui/StarRating";

async function getHotTakes() {
  const reviews = await prisma.review.findMany({
    where: { rating: { not: null } },
    orderBy: { createdAt: "desc" },
    take: 300,
    include: {
      user: { select: { username: true, avatarUrl: true } },
      album: { select: { id: true, title: true, artistName: true, coverUrl: true, avgRating: true } },
    },
  });

  return reviews
    .filter((r) => r.rating != null && r.album.avgRating != null && Math.abs(r.rating - r.album.avgRating) >= 1.5)
    .sort((a, b) => Math.abs((b.rating ?? 0) - (b.album.avgRating ?? 0)) - Math.abs((a.rating ?? 0) - (a.album.avgRating ?? 0)))
    .slice(0, 30);
}

export default async function HotTakesPage() {
  const hotTakes = await getHotTakes();

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#F5F2EB] mb-2" style={{ fontFamily: "Playfair Display, serif" }}>
          🔥 Hot Takes
        </h1>
        <p className="text-[#888]">Reviews that diverge wildly from the community&apos;s verdict.</p>
      </div>

      {hotTakes.length === 0 ? (
        <div className="text-center py-20 text-[#888]">
          <p>No hot takes yet — rates and reviews will appear here when they diverge significantly from community ratings.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {hotTakes.map((review) => {
            const diff = (review.rating ?? 0) - (review.album.avgRating ?? 0);
            const isHot = diff < 0;
            return (
              <div key={review.id} className="bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 hover:border-[rgba(255,255,255,0.15)] transition-colors">
                <div className="flex gap-4">
                  {review.album.coverUrl && (
                    <Link href={`/album/${review.album.id}`} className="shrink-0">
                      <Image
                        src={review.album.coverUrl}
                        alt={review.album.title}
                        width={64}
                        height={64}
                        className="rounded object-cover"
                      />
                    </Link>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <Link href={`/album/${review.album.id}`} className="text-[#F5F2EB] font-semibold hover:text-[#E8B84B] transition-colors">
                        {review.album.title}
                      </Link>
                      <span className={`text-sm font-bold shrink-0 ${isHot ? "text-red-400" : "text-green-400"}`}>
                        {isHot ? "▼" : "▲"} {Math.abs(diff).toFixed(1)} vs avg
                      </span>
                    </div>
                    <p className="text-[#888] text-xs mb-2">{review.album.artistName}</p>

                    <div className="flex items-center gap-3 mb-2">
                      <Link href={`/user/${review.user.username}`} className="flex items-center gap-1.5">
                        <UserAvatar username={review.user.username} avatarUrl={review.user.avatarUrl} size={20} />
                        <span className="text-[#888] text-xs hover:text-[#E8B84B] transition-colors">{review.user.username}</span>
                      </Link>
                      <span className="text-[#555] text-xs">gave it</span>
                      {review.rating != null && <StarRating value={review.rating} readonly size="sm" />}
                      <span className="text-[#555] text-xs">avg: {review.album.avgRating?.toFixed(1)}</span>
                    </div>

                    <p className="text-[#F5F2EB] text-sm line-clamp-3">{review.body}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
