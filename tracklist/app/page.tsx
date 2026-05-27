export const dynamic = "force-dynamic"

import { Suspense } from "react"
import Link from "next/link"
import Image from "next/image"
import { prisma } from "@/lib/prisma"
import { getNewReleases } from "@/lib/spotify"
import { AlbumCard, AlbumCardSkeleton } from "@/components/ui/AlbumCard"
import { ReviewCard, ReviewCardSkeleton } from "@/components/ui/ReviewCard"
import { UserAvatar } from "@/components/ui/UserAvatar"
import { TrendingTopics } from "@/components/home/TrendingTopics"
import { NewReleasesStrip } from "@/components/home/NewReleasesStrip"

async function JustRated() {
  const ratings = await prisma.rating.findMany({
    orderBy: { createdAt: "desc" },
    take: 16,
    include: {
      album: { select: { id: true, coverUrl: true, title: true } },
      user: { select: { username: true } },
    },
  }).catch(() => [])

  if (ratings.length === 0) return null

  return (
    <section className="mb-10 -mx-4 px-4 overflow-hidden">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[#888] text-xs uppercase tracking-widest">Just Rated</p>
        <Link href="/search" className="text-[#888] text-xs hover:text-[#E8B84B] transition-colors">More →</Link>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-none">
        {ratings.map((r) => (
          <Link
            key={r.id}
            href={`/album/${r.album.id}`}
            className="shrink-0 group"
            title={`${r.album.title} — rated by ${r.user.username}`}
          >
            <div className="w-14 h-14 rounded overflow-hidden border border-[rgba(255,255,255,0.06)] group-hover:border-[rgba(255,255,255,0.2)] transition-colors">
              {r.album.coverUrl ? (
                <Image src={r.album.coverUrl} alt={r.album.title} width={56} height={56} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-lg">♪</div>
              )}
            </div>
          </Link>
        ))}
      </div>
    </section>
  )
}

async function PopularReviewsThisWeek() {
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
  const reviews = await prisma.review.findMany({
    where: { createdAt: { gte: sevenDaysAgo } },
    orderBy: { likes: "desc" },
    take: 5,
    include: {
      user: { select: { id: true, username: true, avatarUrl: true } },
      album: { select: { id: true, title: true, coverUrl: true, artistName: true, releaseYear: true } },
    },
  }).catch(() => [])

  if (reviews.length === 0) {
    const fallback = await prisma.review.findMany({
      orderBy: { likes: "desc" },
      take: 5,
      include: {
        user: { select: { id: true, username: true, avatarUrl: true } },
        album: { select: { id: true, title: true, coverUrl: true, artistName: true, releaseYear: true } },
      },
    }).catch(() => [])
    if (fallback.length === 0) return <p className="text-[#888] text-sm">No reviews yet.</p>
    return <ReviewList reviews={fallback} />
  }

  return <ReviewList reviews={reviews} />
}

function ReviewList(
  { reviews }: {
    reviews: Array<{
      id: string; body: string; rating: number | null; likes: number; createdAt: Date;
      user: { id: string; username: string; avatarUrl: string | null };
      album: { id: string; title: string; coverUrl: string | null; artistName: string; releaseYear: number };
    }>
  }
) {
  return (
    <div className="space-y-5">
      {reviews.map((r) => (
        <div key={r.id} className="flex gap-3">
          <Link href={`/album/${r.album.id}`} className="shrink-0">
            {r.album.coverUrl ? (
              <Image src={r.album.coverUrl} alt={r.album.title} width={56} height={56} className="rounded w-14 h-14 object-cover" />
            ) : (
              <div className="w-14 h-14 bg-[#1a1a1a] rounded flex items-center justify-center text-[#444]">♪</div>
            )}
          </Link>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <Link href={`/album/${r.album.id}`} className="text-[#F5F2EB] font-semibold text-sm hover:text-[#E8B84B] transition-colors">
                {r.album.title}
              </Link>
              <span className="text-[#555] text-xs">{r.album.releaseYear}</span>
            </div>
            <div className="flex items-center gap-2 mb-1">
              <Link href={`/user/${r.user.username}`}>
                <UserAvatar username={r.user.username} avatarUrl={r.user.avatarUrl} size={18} />
              </Link>
              <Link href={`/user/${r.user.username}`} className="text-[#888] text-xs hover:text-[#E8B84B] transition-colors">{r.user.username}</Link>
              {r.rating != null && (
                <span className="text-[#E8B84B] text-xs">{"★".repeat(Math.round(r.rating))}{"☆".repeat(5 - Math.round(r.rating))}</span>
              )}
            </div>
            <p className="text-[#F5F2EB] text-xs leading-relaxed line-clamp-2">{r.body}</p>
            <p className="text-[#555] text-xs mt-1">♥ {r.likes} likes</p>
          </div>
        </div>
      ))}
    </div>
  )
}

async function PopularLists() {
  const lists = await prisma.list.findMany({
    where: { isPublic: true },
    orderBy: { createdAt: "desc" },
    take: 6,
    include: {
      user: { select: { username: true } },
      _count: { select: { entries: true } },
      entries: { orderBy: { rank: "asc" }, take: 4 },
    },
  }).catch(() => [])

  if (lists.length === 0) return null

  const albumIds = lists.flatMap((l) => l.entries.map((e) => e.albumId))
  const albums = await prisma.album.findMany({
    where: { id: { in: albumIds } },
    select: { id: true, coverUrl: true },
  }).catch(() => [])
  const albumMap = new Map(albums.map((a) => [a.id, a]))

  return (
    <div className="space-y-4">
      {lists.map((list) => (
        <Link key={list.id} href={`/lists/${list.id}`} className="flex gap-3 group hover:opacity-90 transition-opacity">
          <div className="flex shrink-0">
            {list.entries.slice(0, 3).map((e) => {
              const album = albumMap.get(e.albumId)
              return album?.coverUrl ? (
                <Image key={e.id} src={album.coverUrl} alt="" width={40} height={40} className="w-10 h-10 object-cover rounded -mr-2 border border-[#0D0D0D]" />
              ) : (
                <div key={e.id} className="w-10 h-10 bg-[#1a1a1a] rounded -mr-2 border border-[#0D0D0D]" />
              )
            })}
          </div>
          <div className="flex-1 min-w-0 pl-2">
            <p className="text-[#F5F2EB] text-sm font-medium truncate group-hover:text-[#E8B84B] transition-colors">{list.title}</p>
            <p className="text-[#555] text-xs">{list.user.username} · {list._count.entries} albums</p>
          </div>
        </Link>
      ))}
    </div>
  )
}

async function PopularReviewers() {
  const topUsers = await prisma.user.findMany({
    where: { reviews: { some: {} } },
    orderBy: { createdAt: "desc" },
    take: 8,
    include: { _count: { select: { reviews: true, ratings: true } } },
  }).catch(() => [])

  if (topUsers.length === 0) return null

  return (
    <div className="flex flex-wrap gap-3">
      {topUsers.map((u) => (
        <Link key={u.id} href={`/user/${u.username}`} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <UserAvatar username={u.username} avatarUrl={u.avatarUrl} size={36} />
          <div>
            <p className="text-[#F5F2EB] text-xs font-medium">{u.username}</p>
            <p className="text-[#555] text-xs">{u._count.ratings} ratings, {u._count.reviews} reviews</p>
          </div>
        </Link>
      ))}
    </div>
  )
}

async function FeaturedAlbum() {
  const album = await prisma.album.findFirst({
    where: { ratingCount: { gt: 0 }, coverUrl: { not: null } },
    orderBy: [{ ratingCount: "desc" }],
  }).catch(() => null)

  if (!album?.coverUrl) {
    // Show a Spotify new release as the hero
    let featured: Awaited<ReturnType<typeof getNewReleases>>[0] | null = null
    try {
      const releases = await getNewReleases(20)
      featured = releases.find((r) => r.images[0]?.url) ?? null
    } catch { /* ignore */ }

    if (featured?.images[0]?.url) {
      return (
        <section className="relative mb-10 rounded-2xl overflow-hidden min-h-[360px] flex items-end">
          <Image
            src={featured.images[0].url}
            alt={featured.name}
            fill
            className="object-cover scale-110 blur-sm brightness-40"
            sizes="100vw"
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0D0D0D] via-[rgba(13,13,13,0.6)] to-transparent" />
          <div className="relative z-10 p-8 flex gap-6 items-end w-full">
            <Link href={`/album/${featured.id}`} className="shrink-0 hover:scale-105 transition-transform">
              <Image src={featured.images[0].url} alt={featured.name} width={120} height={120} className="rounded-lg shadow-2xl" />
            </Link>
            <div className="flex-1 min-w-0">
              <p className="text-[#E8B84B] text-xs uppercase tracking-widest mb-1 font-semibold">New Release</p>
              <Link href={`/album/${featured.id}`}>
                <h2 className="text-3xl font-bold text-[#F5F2EB] hover:text-[#E8B84B] transition-colors mb-1" style={{ fontFamily: "Playfair Display, serif" }}>
                  {featured.name}
                </h2>
              </Link>
              <p className="text-[#888] mb-3">{featured.artists[0]?.name} · {featured.release_date?.slice(0, 4)}</p>
              <Link href="/register" className="bg-[#E8B84B] text-black font-semibold px-6 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors text-sm">
                Be the first to rate it →
              </Link>
            </div>
          </div>
        </section>
      )
    }

    return (
      <section className="relative mb-10 rounded-2xl overflow-hidden bg-gradient-to-br from-[#1a1a1a] to-[#0D0D0D] min-h-[300px] flex items-end p-8">
        <div>
          <p className="text-[#888] text-sm uppercase tracking-widest mb-2">Featured</p>
          <h2 className="text-4xl font-bold text-[#F5F2EB] mb-1" style={{ fontFamily: "Playfair Display, serif" }}>
            Rate the music you love.
          </h2>
          <p className="text-[#888] mb-4">Save what you want to hear. Tell your friends what&apos;s good.</p>
          <Link href="/search" className="bg-[#E8B84B] text-black font-semibold px-6 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors">
            Get started — it&apos;s free!
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="relative mb-10 rounded-2xl overflow-hidden min-h-[360px] flex items-end">
      <Image
        src={album.coverUrl}
        alt={album.title}
        fill
        className="object-cover scale-110 blur-sm brightness-40"
        sizes="100vw"
        priority
      />
      <div className="absolute inset-0 bg-gradient-to-t from-[#0D0D0D] via-[rgba(13,13,13,0.6)] to-transparent" />
      <div className="relative z-10 p-8 flex gap-6 items-end w-full">
        <Link href={`/album/${album.id}`} className="shrink-0 hover:scale-105 transition-transform">
          <Image
            src={album.coverUrl}
            alt={album.title}
            width={120}
            height={120}
            className="rounded-lg shadow-2xl"
          />
        </Link>
        <div className="flex-1 min-w-0">
          <p className="text-[#888] text-xs uppercase tracking-widest mb-1">Most Rated This Week</p>
          <Link href={`/album/${album.id}`}>
            <h2 className="text-3xl font-bold text-[#F5F2EB] hover:text-[#E8B84B] transition-colors mb-1" style={{ fontFamily: "Playfair Display, serif" }}>
              {album.title}
            </h2>
          </Link>
          <p className="text-[#888] mb-3">{album.artistName} · {album.releaseYear}</p>
          {album.avgRating != null && (
            <div className="flex items-center gap-2">
              <span className="text-[#E8B84B] text-xl font-bold">★ {album.avgRating.toFixed(2)}</span>
              <span className="text-[#555] text-sm">{album.ratingCount.toLocaleString()} ratings</span>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

async function TrendingAlbums() {
  const albums = await prisma.album.findMany({
    where: { ratingCount: { gt: 0 } },
    orderBy: [{ ratingCount: "desc" }, { avgRating: "desc" }],
    take: 6,
  }).catch(() => [])

  if (albums.length === 0) {
    // Fall back to Spotify new releases with auto-caching
    let spotifyAlbums: Awaited<ReturnType<typeof getNewReleases>> = []
    try {
      spotifyAlbums = await getNewReleases(6)
    } catch {
      return null
    }
    if (!spotifyAlbums.length) return null

    return (
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        {spotifyAlbums.map((a) => (
          <Link key={a.id} href={`/album/${a.id}`} className="group">
            <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2 relative">
              {a.images[0]?.url ? (
                <Image src={a.images[0].url} alt={a.name} fill sizes="180px" className="object-cover group-hover:scale-105 transition-transform duration-300" />
              ) : (
                <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-2xl">♪</div>
              )}
            </div>
            <p className="text-[#F5F2EB] text-xs font-medium truncate group-hover:text-[#E8B84B] transition-colors">{a.name}</p>
            <p className="text-[#555] text-[10px] truncate">{a.artists[0]?.name}</p>
          </Link>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
      {albums.map((album) => (
        <AlbumCard
          key={album.id}
          id={album.id}
          title={album.title}
          artistName={album.artistName}
          coverUrl={album.coverUrl}
          avgRating={album.avgRating}
          ratingCount={album.ratingCount}
          releaseYear={album.releaseYear}
        />
      ))}
    </div>
  )
}

const BROWSE_GENRES = [
  { label: "Hip-Hop", slug: "hip-hop", emoji: "🎤" },
  { label: "R&B", slug: "r&b", emoji: "🎵" },
  { label: "Pop", slug: "pop", emoji: "✨" },
  { label: "Rock", slug: "alternative rock", emoji: "🎸" },
  { label: "Jazz", slug: "jazz rap", emoji: "🎷" },
  { label: "Electronic", slug: "electropop", emoji: "⚡" },
  { label: "Indie", slug: "indie pop", emoji: "🌿" },
  { label: "Soul", slug: "soul", emoji: "💿" },
]

async function AutoSeedIfEmpty() {
  const count = await prisma.album.count().catch(() => -1)
  if (count === 0) {
    // Fire-and-forget seed to populate DB on first visit
    try {
      const baseUrl = process.env.NEXTAUTH_URL
        ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000")
      fetch(`${baseUrl}/api/seed`, { method: "POST" }).catch(() => {})
    } catch { /* ignore */ }
  }
  return null
}

export default function HomePage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Auto-seed on first visit */}
      <Suspense fallback={null}>
        <AutoSeedIfEmpty />
      </Suspense>

      {/* Featured Hero */}
      <Suspense fallback={<div className="min-h-[360px] bg-[#111] rounded-2xl animate-pulse mb-10" />}>
        <FeaturedAlbum />
      </Suspense>

      {/* New Releases from Spotify */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[#888] text-xs uppercase tracking-widest">New This Week</p>
          <Link href="/charts" className="text-[#888] text-xs hover:text-[#E8B84B] transition-colors">Charts →</Link>
        </div>
        <NewReleasesStrip />
      </section>

      {/* Just Rated Strip */}
      <Suspense fallback={null}>
        <JustRated />
      </Suspense>

      {/* What Tracklist lets you do */}
      <section className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-10">
        {[
          { icon: "♪", text: "Keep track of every album you've listened to" },
          { icon: "♥", text: "Show some love for your favourite albums and reviews" },
          { icon: "✦", text: "Write and share reviews, follow friends" },
          { icon: "★", text: "Rate each album on a five-star scale" },
          { icon: "📓", text: "Keep a diary of your listening history" },
          { icon: "≡", text: "Compile and share lists on any topic" },
        ].map((item, i) => (
          <div key={i} className="flex items-start gap-3 bg-[#111] border border-[rgba(255,255,255,0.06)] rounded-xl p-4">
            <span className="text-[#E8B84B] text-xl shrink-0">{item.icon}</span>
            <p className="text-[#888] text-xs leading-relaxed">{item.text}</p>
          </div>
        ))}
      </section>

      {/* Browse by Genre */}
      <section className="mb-10">
        <p className="text-[#888] text-xs uppercase tracking-widest mb-4">Browse by Genre</p>
        <div className="flex flex-wrap gap-2">
          {BROWSE_GENRES.map((g) => (
            <Link
              key={g.slug}
              href={`/genre/${encodeURIComponent(g.slug)}`}
              className="flex items-center gap-1.5 bg-[#111] border border-[rgba(255,255,255,0.08)] hover:border-[#E8B84B] hover:text-[#E8B84B] text-[#888] rounded-full px-4 py-1.5 text-sm transition-all"
            >
              <span>{g.emoji}</span>
              <span>{g.label}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Trending Albums */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[#888] uppercase tracking-widest">Popular Albums</h2>
          <Link href="/search" className="text-[#888] text-xs hover:text-[#E8B84B] transition-colors">More →</Link>
        </div>
        <Suspense fallback={
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
            {Array.from({ length: 6 }).map((_, i) => <AlbumCardSkeleton key={i} />)}
          </div>
        }>
          <TrendingAlbums />
        </Suspense>
      </section>

      {/* Reviews + Lists + Topics 3-col */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-10">
        {/* Popular Reviews */}
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <p className="text-[#888] text-xs uppercase tracking-widest">Popular Reviews This Week</p>
          </div>
          <Suspense fallback={
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => <ReviewCardSkeleton key={i} />)}
            </div>
          }>
            <PopularReviewsThisWeek />
          </Suspense>
        </div>

        {/* Popular Lists + Trending Topics */}
        <div className="space-y-8">
          <div>
            <div className="flex items-center justify-between mb-4">
              <p className="text-[#888] text-xs uppercase tracking-widest">Popular Lists</p>
              <Link href="/lists/new" className="text-[#888] text-xs hover:text-[#E8B84B] transition-colors">Create →</Link>
            </div>
            <Suspense fallback={<div className="space-y-3 animate-pulse">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-10 bg-[#1a1a1a] rounded" />)}</div>}>
              <PopularLists />
            </Suspense>
          </div>

          {/* Trending Music Topics */}
          <div>
            <p className="text-[#888] text-xs uppercase tracking-widest mb-4">Trending in Music</p>
            <TrendingTopics />
          </div>
        </div>
      </div>

      {/* Popular Reviewers */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-4">
          <p className="text-[#888] text-xs uppercase tracking-widest">Popular Reviewers</p>
        </div>
        <Suspense fallback={<div className="h-12 animate-pulse bg-[#1a1a1a] rounded" />}>
          <PopularReviewers />
        </Suspense>
      </section>

      {/* CTA for guests */}
      <section className="text-center py-10 border-t border-[rgba(255,255,255,0.06)]">
        <p className="text-[#F5F2EB] text-lg font-semibold mb-1" style={{ fontFamily: "Playfair Display, serif" }}>
          Rate the albums you love. Share your taste.
        </p>
        <p className="text-[#888] text-sm mb-5">Below are some popular reviews and lists this week. Sign up to create your own.</p>
        <Link href="/register" className="bg-[#E8B84B] text-black font-semibold px-8 py-3 rounded-full hover:bg-[#d4a43a] transition-colors">
          Get started — it&apos;s free!
        </Link>
      </section>
    </div>
  )
}
