import { notFound } from "next/navigation"
import Image from "next/image"
import Link from "next/link"
import { prisma } from "@/lib/prisma"
import { UserAvatar } from "@/components/ui/UserAvatar"
import { ReviewCard } from "@/components/ui/ReviewCard"
import { StarRating } from "@/components/ui/StarRating"

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
        },
      },
    },
  })

  if (!user) notFound()

  const [recentRatings, recentReviews] = await Promise.all([
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
  ])

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
          <h1
            className="text-3xl font-bold text-[#F5F2EB] mb-1"
            style={{ fontFamily: "var(--font-playfair), serif" }}
          >
            {user.username}
          </h1>
          {user.bio && (
            <p className="text-[#888] text-sm mb-3 max-w-xl">{user.bio}</p>
          )}
          <p className="text-[#555] text-xs">Member since {memberSince}</p>

          <div className="flex flex-wrap gap-6 mt-4">
            <div className="text-center">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.ratings}</p>
              <p className="text-[#888] text-xs">Ratings</p>
            </div>
            <div className="text-center">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.reviews}</p>
              <p className="text-[#888] text-xs">Reviews</p>
            </div>
            <div className="text-center">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.following}</p>
              <p className="text-[#888] text-xs">Following</p>
            </div>
            <div className="text-center">
              <p className="text-[#F5F2EB] font-bold text-lg">{user._count.followers}</p>
              <p className="text-[#888] text-xs">Followers</p>
            </div>
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
        </div>

        {/* Recent Ratings Grid */}
        <div>
          {recentRatings.length > 0 && (
            <section>
              <h2
                className="text-xl font-semibold text-[#F5F2EB] mb-4"
                style={{ fontFamily: "var(--font-playfair), serif" }}
              >
                Recent Ratings
              </h2>
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
