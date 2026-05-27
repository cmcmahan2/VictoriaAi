export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { UserAvatar } from "@/components/ui/UserAvatar";

function Bar({ pct, color = "#E8B84B" }: { pct: number; color?: string }) {
  return (
    <div className="flex-1 h-2 bg-[#1a1a1a] rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

export default async function StatsPage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = await params;

  const user = await prisma.user.findUnique({
    where: { username },
    select: { id: true, username: true, avatarUrl: true, displayName: true, createdAt: true },
  });
  if (!user) notFound();

  const [ratings, reviews] = await Promise.all([
    prisma.rating.findMany({
      where: { userId: user.id },
      include: { album: { select: { genres: true, releaseYear: true, artistName: true, artistId: true } } },
    }),
    prisma.review.findMany({
      where: { userId: user.id },
      select: { id: true, rating: true, createdAt: true },
    }),
  ]);

  if (ratings.length === 0) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-10 text-center">
        <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={64} />
        <p className="text-[#888] mt-4">No ratings yet.</p>
        <Link href={`/user/${username}`} className="text-[#E8B84B] text-sm hover:underline mt-2 block">← Back to profile</Link>
      </div>
    );
  }

  // Genre breakdown
  const genreCounts: Record<string, { count: number; totalRating: number }> = {};
  for (const r of ratings) {
    for (const g of r.album.genres) {
      if (!genreCounts[g]) genreCounts[g] = { count: 0, totalRating: 0 };
      genreCounts[g].count++;
      genreCounts[g].totalRating += r.value;
    }
  }
  const topGenres = Object.entries(genreCounts)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 10)
    .map(([g, d]) => ({ genre: g, count: d.count, avg: d.totalRating / d.count }));
  const maxGenreCount = topGenres[0]?.count ?? 1;

  // Rating distribution
  const dist: Record<string, number> = { "0.5": 0, "1": 0, "1.5": 0, "2": 0, "2.5": 0, "3": 0, "3.5": 0, "4": 0, "4.5": 0, "5": 0 };
  for (const r of ratings) dist[String(r.value)] = (dist[String(r.value)] ?? 0) + 1;
  const maxDist = Math.max(...Object.values(dist));

  // Decade breakdown
  const decadeCounts: Record<string, number> = {};
  for (const r of ratings) {
    const decade = Math.floor(r.album.releaseYear / 10) * 10;
    decadeCounts[decade] = (decadeCounts[decade] ?? 0) + 1;
  }
  const decades = Object.entries(decadeCounts).sort((a, b) => Number(a[0]) - Number(b[0]));
  const maxDecade = Math.max(...Object.values(decadeCounts));

  // Top artists
  const artistCounts: Record<string, { name: string; id: string; count: number; totalRating: number }> = {};
  for (const r of ratings) {
    const { artistName, artistId } = r.album;
    if (!artistCounts[artistId]) artistCounts[artistId] = { name: artistName, id: artistId, count: 0, totalRating: 0 };
    artistCounts[artistId].count++;
    artistCounts[artistId].totalRating += r.value;
  }
  const topArtists = Object.values(artistCounts).sort((a, b) => b.count - a.count).slice(0, 8);

  // Overall stats
  const avgRating = ratings.reduce((s, r) => s + r.value, 0) / ratings.length;
  const monthsActive = Math.ceil((Date.now() - user.createdAt.getTime()) / (1000 * 60 * 60 * 24 * 30));

  // Monthly activity (last 12 months)
  const now = new Date();
  const monthActivity: Record<string, number> = {};
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    monthActivity[`${d.getFullYear()}-${d.getMonth()}`] = 0;
  }
  for (const r of ratings) {
    const d = r.createdAt;
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (key in monthActivity) monthActivity[key]++;
  }
  const monthValues = Object.values(monthActivity);
  const maxMonth = Math.max(...monthValues, 1);
  const monthLabels = Object.keys(monthActivity).map((k) => {
    const [y, m] = k.split("-");
    return new Date(Number(y), Number(m), 1).toLocaleDateString("en-US", { month: "short" });
  });

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link href={`/user/${username}`}>
          <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={56} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
            {user.displayName ?? user.username}&apos;s Stats
          </h1>
          <Link href={`/user/${username}`} className="text-[#555] text-xs hover:text-[#E8B84B] transition-colors">← Back to profile</Link>
        </div>
      </div>

      {/* Top-level numbers */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
        {[
          { label: "Albums Rated", value: ratings.length },
          { label: "Reviews Written", value: reviews.length },
          { label: "Avg Rating", value: `★ ${avgRating.toFixed(2)}` },
          { label: "Months Active", value: monthsActive },
        ].map((s) => (
          <div key={s.label} className="bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-xl p-4 text-center">
            <p className="text-[#F5F2EB] text-2xl font-bold">{s.value}</p>
            <p className="text-[#555] text-xs mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Genre Breakdown */}
        <section>
          <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Top Genres</h2>
          <div className="space-y-2.5">
            {topGenres.map((g) => (
              <div key={g.genre}>
                <div className="flex items-center justify-between mb-1">
                  <Link href={`/genre/${encodeURIComponent(g.genre)}`} className="text-[#F5F2EB] text-xs hover:text-[#E8B84B] transition-colors">
                    {g.genre}
                  </Link>
                  <div className="flex items-center gap-2">
                    <span className="text-[#E8B84B] text-[10px]">★ {g.avg.toFixed(1)}</span>
                    <span className="text-[#555] text-[10px]">{g.count}</span>
                  </div>
                </div>
                <Bar pct={(g.count / maxGenreCount) * 100} />
              </div>
            ))}
          </div>
        </section>

        {/* Rating Distribution */}
        <section>
          <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Rating Distribution</h2>
          <div className="space-y-2">
            {Object.entries(dist).reverse().map(([val, count]) => (
              <div key={val} className="flex items-center gap-3">
                <span className="text-[#E8B84B] text-xs w-6 text-right">{val}</span>
                <Bar pct={maxDist > 0 ? (count / maxDist) * 100 : 0} />
                <span className="text-[#555] text-xs w-6">{count}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Decade Breakdown */}
        <section>
          <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">By Decade</h2>
          <div className="space-y-2.5">
            {decades.map(([decade, count]) => (
              <div key={decade}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[#F5F2EB] text-xs">{decade}s</span>
                  <span className="text-[#555] text-[10px]">{count}</span>
                </div>
                <Bar pct={(count / maxDecade) * 100} color="#888" />
              </div>
            ))}
          </div>
        </section>

        {/* Top Artists */}
        <section>
          <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Top Artists</h2>
          <div className="space-y-2">
            {topArtists.map((a, i) => (
              <Link key={a.id} href={`/artist/${a.id}`} className="flex items-center gap-3 group">
                <span className="text-[#444] text-xs w-4">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-[#F5F2EB] text-sm truncate group-hover:text-[#E8B84B] transition-colors">{a.name}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[#E8B84B] text-xs">★ {(a.totalRating / a.count).toFixed(1)}</p>
                  <p className="text-[#555] text-[10px]">{a.count} rated</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>

      {/* Monthly Activity Chart */}
      <section className="mt-8">
        <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest mb-4">Activity (Last 12 Months)</h2>
        <div className="flex items-end gap-1.5 h-24">
          {monthValues.map((v, i) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t bg-[#E8B84B] opacity-70 hover:opacity-100 transition-opacity"
                style={{ height: `${Math.max((v / maxMonth) * 80, v > 0 ? 4 : 0)}px` }}
                title={`${v} ratings`}
              />
            </div>
          ))}
        </div>
        <div className="flex gap-1.5 mt-1">
          {monthLabels.map((l, i) => (
            <div key={i} className="flex-1 text-center text-[#444] text-[8px]">{l}</div>
          ))}
        </div>
      </section>
    </div>
  );
}
