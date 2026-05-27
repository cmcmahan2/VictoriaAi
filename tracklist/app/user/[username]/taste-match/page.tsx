export const dynamic = "force-dynamic";

import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { UserAvatar } from "@/components/ui/UserAvatar";

function computeMatch(
  myRatings: Array<{ albumId: string; value: number }>,
  theirRatings: Array<{ albumId: string; value: number }>
): { score: number; sharedCount: number; agreements: Array<{ albumId: string; myValue: number; theirValue: number }> } {
  const myMap = new Map(myRatings.map((r) => [r.albumId, r.value]));
  const agreements: Array<{ albumId: string; myValue: number; theirValue: number }> = [];

  for (const r of theirRatings) {
    const mine = myMap.get(r.albumId);
    if (mine != null) {
      agreements.push({ albumId: r.albumId, myValue: mine, theirValue: r.value });
    }
  }

  if (agreements.length === 0) return { score: 0, sharedCount: 0, agreements: [] };

  // Score: avg (1 - |diff| / 4) per shared album — higher means more similar
  const rawScore = agreements.reduce((sum, a) => sum + (1 - Math.abs(a.myValue - a.theirValue) / 4), 0) / agreements.length;
  const score = Math.round(rawScore * 100);

  return { score, sharedCount: agreements.length, agreements };
}

function scoreLabel(score: number) {
  if (score >= 85) return { label: "Music Soulmates", color: "#E8B84B" };
  if (score >= 70) return { label: "Great Match", color: "#6dbf67" };
  if (score >= 50) return { label: "Good Match", color: "#888" };
  if (score >= 30) return { label: "Some Overlap", color: "#888" };
  return { label: "Different Taste", color: "#555" };
}

export default async function TasteMatchPage({ params }: { params: Promise<{ username: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session?.user) redirect("/login");

  const myId = (session.user as { id?: string }).id;
  const myName = (session.user as { name?: string | null }).name;
  if (!myId) redirect("/login");

  const { username } = await params;

  const [me, them] = await Promise.all([
    prisma.user.findUnique({
      where: { id: myId },
      select: { username: true, avatarUrl: true, displayName: true, ratings: { select: { albumId: true, value: true } } },
    }),
    prisma.user.findUnique({
      where: { username },
      select: { id: true, username: true, avatarUrl: true, displayName: true, bio: true, ratings: { select: { albumId: true, value: true } } },
    }),
  ]);

  if (!them) notFound();
  if (!me) redirect("/login");

  // Can't match with yourself
  if (them.id === myId) redirect(`/user/${username}`);

  const { score, sharedCount, agreements } = computeMatch(me.ratings, them.ratings);

  // Get top agreements (albums you both rated similarly)
  const topAgreements = agreements
    .filter((a) => Math.abs(a.myValue - a.theirValue) <= 1)
    .slice(0, 6);

  const topDisagreements = agreements
    .filter((a) => Math.abs(a.myValue - a.theirValue) >= 2)
    .sort((a, b) => Math.abs(b.myValue - b.theirValue) - Math.abs(a.myValue - a.theirValue))
    .slice(0, 4);

  const albumIds = [...new Set([...topAgreements, ...topDisagreements].map((a) => a.albumId))];
  const albums = await prisma.album.findMany({ where: { id: { in: albumIds } } });
  const albumMap = new Map(albums.map((a) => [a.id, a]));

  const { label, color } = scoreLabel(score);

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link href={`/user/${myName}`}>
          <UserAvatar username={me.username} avatarUrl={me.avatarUrl} size={56} />
        </Link>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div
              className="text-5xl font-bold mb-1"
              style={{ color, fontFamily: "Playfair Display, serif" }}
            >
              {score}%
            </div>
            <div className="text-sm font-semibold" style={{ color }}>{label}</div>
          </div>
        </div>
        <Link href={`/user/${username}`}>
          <UserAvatar username={them.username} avatarUrl={them.avatarUrl} size={56} />
        </Link>
      </div>

      <div className="text-center mb-8">
        <p className="text-[#888] text-sm">
          You and <Link href={`/user/${username}`} className="text-[#F5F2EB] hover:text-[#E8B84B] transition-colors">{them.displayName ?? them.username}</Link>{" "}
          {sharedCount > 0
            ? `have rated ${sharedCount} album${sharedCount !== 1 ? "s" : ""} in common.`
            : "haven't rated any albums in common yet."}
        </p>
      </div>

      {/* Score bar */}
      <div className="mb-10">
        <div className="w-full h-2 bg-[#1a1a1a] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000"
            style={{ width: `${score}%`, backgroundColor: color }}
          />
        </div>
      </div>

      {sharedCount === 0 ? (
        <div className="text-center py-8 bg-[#111] rounded-2xl border border-[rgba(255,255,255,0.06)]">
          <p className="text-[#888] text-sm mb-3">Rate more albums to see how you compare!</p>
          <Link href="/search" className="text-[#E8B84B] text-sm hover:underline">Browse albums →</Link>
        </div>
      ) : (
        <>
          {/* Agreements */}
          {topAgreements.length > 0 && (
            <section className="mb-8">
              <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">You Both Love</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {topAgreements.map((a) => {
                  const album = albumMap.get(a.albumId);
                  if (!album) return null;
                  return (
                    <Link key={a.albumId} href={`/album/${a.albumId}`} className="flex items-center gap-3 bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-xl p-3 hover:border-[rgba(255,255,255,0.15)] transition-colors group">
                      {album.coverUrl ? (
                        <Image src={album.coverUrl} alt={album.title} width={40} height={40} className="rounded w-10 h-10 object-cover shrink-0" />
                      ) : (
                        <div className="w-10 h-10 bg-[#1a1a1a] rounded shrink-0 flex items-center justify-center text-[#444]">♪</div>
                      )}
                      <div className="min-w-0">
                        <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{album.title}</p>
                        <p className="text-[#E8B84B] text-[10px]">
                          You: {"★".repeat(Math.round(a.myValue))} · Them: {"★".repeat(Math.round(a.theirValue))}
                        </p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </section>
          )}

          {/* Disagreements */}
          {topDisagreements.length > 0 && (
            <section className="mb-8">
              <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">You Disagree On</h2>
              <div className="space-y-2">
                {topDisagreements.map((a) => {
                  const album = albumMap.get(a.albumId);
                  if (!album) return null;
                  return (
                    <Link key={a.albumId} href={`/album/${a.albumId}`} className="flex items-center gap-3 bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-xl p-3 hover:border-[rgba(255,255,255,0.15)] transition-colors group">
                      {album.coverUrl ? (
                        <Image src={album.coverUrl} alt={album.title} width={36} height={36} className="rounded w-9 h-9 object-cover shrink-0" />
                      ) : (
                        <div className="w-9 h-9 bg-[#1a1a1a] rounded shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{album.title}</p>
                        <p className="text-[#555] text-[10px]">{album.artistName}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-[#888] text-[10px]">You: {"★".repeat(Math.round(a.myValue))}</p>
                        <p className="text-[#888] text-[10px]">Them: {"★".repeat(Math.round(a.theirValue))}</p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}

      <div className="text-center pt-4">
        <Link href={`/user/${username}`} className="text-[#888] text-sm hover:text-[#F5F2EB] transition-colors">
          ← Back to {them.displayName ?? them.username}&apos;s profile
        </Link>
      </div>
    </div>
  );
}
