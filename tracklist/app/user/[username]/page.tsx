export const dynamic = "force-dynamic"

import { notFound } from "next/navigation"
import Image from "next/image"
import Link from "next/link"
import { prisma } from "@/lib/prisma"
import { UserAvatar } from "@/components/ui/UserAvatar"
import { ReviewCard } from "@/components/ui/ReviewCard"
import { StarRating } from "@/components/ui/StarRating"
import { FollowButton } from "@/components/social/FollowButton"

interface PageProps {
  params: Promise<{ username: string }>
}

export default async function UserProfilePage({ params }: PageProps) {
  const { username } = await params

  const user = await prisma.user.findUnique({
    where: { username },
    include: {
      _count: {
        select: {
          ratings: true,
          reviews: true,
          following: true,
          followers: true,
          lists: true,
        },
      },
    },
  })

  if (!user) notFound()

  const [recentRatings, recentReviews, recentLists] = await Promise.all([
    prisma.rating.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "desc" },
      take: 8,
      include: {
        album: { select: { id: true, title: true, artistName: true, coverUrl: true } },
      },
    }),
    prisma.review.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "desc" },
      take: 5,
      include: {
        album: { select: { id: true, title: true } },
        user: { select: { id: true, username: true, avatarUrl: true } },
      },
    }),
    prisma.list.findMany({
      where: { userId: user.id, isPublic: true },
      orderBy: { createdAt: "desc" },
      take: 3,
      include: {
        _count: { select: { entries: true } },
        entries: { orderBy: { rank: "asc" }, take: 4 },
      },
    }),
  ])

  const listAlbumIds = recentLists.flatMap((l) => l.entries.map((e) => e.albumId))
  const listAlbums = await prisma.album.findMany({
    where: { id: { in: listAlbumIds } },
    select: { id: true, coverUrl: true, title: true },
  })
  const albumMap = new Map(listAlbums.map((a) => [a.id, a]))

  const memberSince = new Date(user.createdAt).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
  })

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      {/* Profile Header */}
      <div className="flex flex-col sm:flex-row items-start gap-6 mb-10">
        <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={96} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="flex-1">
              <h1
                className="text-3xl font-bold text-[#F5F2EB] mb-0.5"
                style={{ fontFamily: "var(--font-playfair), serif" }}
              >
                {(user as typeof user & { displayName?: string | null }).displayName ?? user.username}
              </h1>
              {(user as typeof user & { displayName?: string | null }).displayName && (
                <p className="text-[#555] text-sm mb-1">@{user.username}</p>
              )}
              {user.bio && (
                <p className="text-[#888] text-sm mb-2 max-w-xl">{user.bio}</p>
              )}
              <div className="flex flex-wrap items-center gap-3 text-xs text-[#555]">
                <span>Member since {memberSince}</span>
                {(user as typeof user & { location?: string | null }).location && (
                  <span>📍 {(user as typeof user & { location?: string | null }).location}</span>
                )}
                {(user as typeof user & { website?: string | null }).website && (
                  <a href={(user as typeof user & { website?: string | null }).website!} target="_blank" rel="noopener noreferrer" className="text-[#E8B84B] hover:underline">
                    🔗 Website
                  </a>
                )}
              </div>
              {((user as typeof user & { favoriteGenres?: string[] }).favoriteGenres ?? []).length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {((user as typeof user & { favoriteGenres?: string[] }).favoriteGenres ?? []).slice(0, 6).map((g) => (
                    <Link key={g} href={`/genre/${encodeURIComponent(g.toLowerCase())}`} className="text-[10px] bg-[#1a1a1a] text-[#888] rounded-full px-2.5 py-0.5 hover:text-[#E8B84B] transition-colors">
                      {g}
                    </Link>
                  ))}
                </div>
              )}
            </div>
            <FollowButton targetUserId={user.id} />
            <Link
              href={`/user/${username}/taste-match`}
              className="text-xs bg-[#111] border border-[rgba(255,255,255,0.1)] text-[#888] rounded-full px-3 py-1.5 hover:border-[#E8B84B] hover:text-[#E8B84B] transition-all"
            >
              Taste Match →
            </Link>
          </div>

          <div className="flex flex-wrap gap-6 mt-4">
            <Link href={`/user/${username}/diary`} className="text-center hover:opacity-80 transition-opacity">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.ratings}</p>
              <p className="text-[#888] text-xs">Ratings</p>
            </Link>
            <div className="text-center">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.reviews}</p>
              <p className="text-[#888] text-xs">Reviews</p>
            </div>
            <Link href={`/user/${username}/lists`} className="text-center hover:opacity-80 transition-opacity">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.lists}</p>
              <p className="text-[#888] text-xs">Lists</p>
            </Link>
            <div className="text-center">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.following}</p>
              <p className="text-[#888] text-xs">Following</p>
            </div>
            <div className="text-center">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.followers}</p>
              <p className="text-[#888] text-xs">Followers</p>
            </div>
          </div>

          {/* Sub-nav */}
          <div className="flex gap-4 mt-5 border-b border-[rgba(255,255,255,0.06)] pb-1 overflow-x-auto scrollbar-none">
            <Link href={`/user/${username}`} className="text-[#E8B84B] text-sm font-medium pb-1 border-b-2 border-[#E8B84B] shrink-0">
              Profile
            </Link>
            <Link href={`/user/${username}/diary`} className="text-[#888] text-sm hover:text-[#F5F2EB] pb-1 border-b-2 border-transparent hover:border-[rgba(255,255,255,0.2)] transition-colors shrink-0">
              Diary
            </Link>
            <Link href={`/user/${username}/lists`} className="text-[#888] text-sm hover:text-[#F5F2EB] pb-1 border-b-2 border-transparent hover:border-[rgba(255,255,255,0.2)] transition-colors shrink-0">
              Lists
            </Link>
            <Link href={`/user/${username}/stats`} className="text-[#888] text-sm hover:text-[#F5F2EB] pb-1 border-b-2 border-transparent hover:border-[rgba(255,255,255,0.2)] transition-colors shrink-0">
              Stats
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        <div className="lg:col-span-2 space-y-10">
          {/* Recent Reviews */}
          {recentReviews.length > 0 && (
            <section>
              <h2
                className="text-xl font-semibold text-[#F5F2EB] mb-4"
                style={{ fontFamily: "var(--font-playfair), serif" }}
              >
                Recent Reviews
              </h2>
              <div className="space-y-4">
                {recentReviews.map((review) => (
                  <ReviewCard
                    key={review.id}
                    id={review.id}
                    body={review.body}
                    rating={review.rating}
                    likes={review.likes}
                    createdAt={review.createdAt.toISOString()}
                    user={review.user}
                    albumId={review.album.id}
                    albumTitle={review.album.title}
                    showAlbum
                  />
                ))}
              </div>
            </section>
          )}

          {/* Recent Lists */}
          {recentLists.length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-[#F5F2EB]" style={{ fontFamily: "var(--font-playfair), serif" }}>
                  Lists
                </h2>
                <Link href={`/user/${username}/lists`} className="text-[#888] text-sm hover:text-[#E8B84B] transition-colors">
                  See all →
                </Link>
              </div>
              <div className="space-y-3">
                {recentLists.map((list) => (
                  <Link
                    key={list.id}
                    href={`/lists/${list.id}`}
                    className="flex items-center gap-3 bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-3 hover:border-[rgba(255,255,255,0.2)] transition-colors group"
                  >
                    <div className="flex gap-1 shrink-0">
                      {list.entries.slice(0, 3).map((entry) => {
                        const album = albumMap.get(entry.albumId)
                        return album?.coverUrl ? (
                          <Image key={entry.id} src={album.coverUrl} alt="" width={40} height={40} className="w-10 h-10 rounded object-cover" />
                        ) : (
                          <div key={entry.id} className="w-10 h-10 bg-[#1a1a1a] rounded" />
                        )
                      })}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[#F5F2EB] text-sm font-medium group-hover:text-[#E8B84B] transition-colors truncate">{list.title}</p>
                      <p className="text-[#555] text-xs">{list._count.entries} albums</p>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Recent Ratings Grid */}
        <div>
          {recentRatings.length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2
                  className="text-xl font-semibold text-[#F5F2EB]"
                  style={{ fontFamily: "var(--font-playfair), serif" }}
                >
                  Recent Ratings
                </h2>
                <Link href={`/user/${username}/diary`} className="text-[#888] text-sm hover:text-[#E8B84B] transition-colors">
                  All →
                </Link>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {recentRatings.map((rating) => (
                  <Link
                    key={rating.id}
                    href={`/album/${rating.album.id}`}
                    className="group relative"
                    title={`${rating.album.title} — ${rating.value}/5`}
                  >
                    <div className="aspect-square rounded overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.2)] transition-colors">
                      {rating.album.coverUrl ? (
                        <Image
                          src={rating.album.coverUrl}
                          alt={rating.album.title}
                          width={80}
                          height={80}
                          className="w-full h-full object-cover"
                          sizes="80px"
                        />
                      ) : (
                        <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-lg">
                          ♪
                        </div>
                      )}
                    </div>
                    <div className="mt-1">
                      <StarRating value={rating.value} readonly size="sm" />
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {recentRatings.length === 0 && recentReviews.length === 0 && (
            <div className="text-center py-16 text-[#888]">
              <p className="text-lg mb-2">No activity yet</p>
              <Link href="/search" className="text-[#E8B84B] hover:underline text-sm">
                Find albums to rate
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
