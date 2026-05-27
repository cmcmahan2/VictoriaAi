export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { prisma } from "@/lib/prisma";
import { StarRating } from "@/components/ui/StarRating";

interface PageProps {
  params: Promise<{ username: string }>;
}

export default async function DiaryPage({ params }: PageProps) {
  const { username } = await params;

  const user = await prisma.user.findUnique({ where: { username } });
  if (!user) notFound();

  const ratings = await prisma.rating.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: "desc" },
    include: {
      album: { select: { id: true, title: true, artistName: true, coverUrl: true, releaseYear: true } },
    },
  });

  // Group by month
  const grouped: Record<string, typeof ratings> = {};
  for (const r of ratings) {
    const key = new Date(r.createdAt).toLocaleDateString("en-US", { year: "numeric", month: "long" });
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(r);
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <div className="mb-8">
        <Link href={`/user/${username}`} className="text-[#888] text-sm hover:text-[#F5F2EB] transition-colors">
          ← {username}
        </Link>
        <h1 className="text-3xl font-bold text-[#F5F2EB] mt-2" style={{ fontFamily: "Playfair Display, serif" }}>
          Diary
        </h1>
        <p className="text-[#888] mt-1">{ratings.length} albums rated</p>
      </div>

      {ratings.length === 0 ? (
        <div className="text-center py-16 text-[#888]">
          <p>No ratings yet.</p>
        </div>
      ) : (
        <div className="space-y-10">
          {Object.entries(grouped).map(([month, monthRatings]) => (
            <section key={month}>
              <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4 pb-2 border-b border-[rgba(255,255,255,0.06)]">
                {month}
              </h2>
              <div className="space-y-2">
                {monthRatings.map((r) => {
                  const day = new Date(r.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" });
                  return (
                    <div key={r.id} className="flex items-center gap-3 py-2 hover:bg-[rgba(255,255,255,0.02)] rounded-lg px-2 -mx-2 transition-colors">
                      <span className="text-[#555] text-xs w-12 shrink-0">{day}</span>
                      <Link href={`/album/${r.album.id}`} className="shrink-0">
                        {r.album.coverUrl ? (
                          <Image
                            src={r.album.coverUrl}
                            alt={r.album.title}
                            width={40}
                            height={40}
                            className="rounded object-cover"
                          />
                        ) : (
                          <div className="w-10 h-10 bg-[#1a1a1a] rounded flex items-center justify-center text-[#444]">♪</div>
                        )}
                      </Link>
                      <div className="flex-1 min-w-0">
                        <Link href={`/album/${r.album.id}`} className="text-[#F5F2EB] text-sm font-medium hover:text-[#E8B84B] transition-colors block truncate">
                          {r.album.title}
                        </Link>
                        <p className="text-[#555] text-xs truncate">{r.album.artistName}</p>
                      </div>
                      <StarRating value={r.value} readonly size="sm" />
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
