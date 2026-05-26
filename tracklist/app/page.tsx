import { Suspense } from "react"
import Link from "next/link"
import { prisma } from "@/lib/prisma"
import { AlbumCard, AlbumCardSkeleton } from "@/components/ui/AlbumCard"
import { ReviewCard, ReviewCardSkeleton } from "@/components/ui/ReviewCard"

async function TrendingAlbums() {
  const albums = await prisma.album.findMany({
    where: { ratingCount: { gt: 0 } },
    orderBy: [{ ratingCount: "desc" }, { avgRating: "desc" }],
    take: 8,
  })

  if (albums.length === 0) {
    return (
      <div className="text-center py-12 text-[#888]">
        <p>No albums rated yet.</p>
        <Link href="/search" className="text-[#E8B84B] hover:underline mt-2 inline-block">
          Search for albums to get started
        </Link>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
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

async function RecentReviews() {
  const reviews = await prisma.review.findMany({
    orderBy: { createdAt: "desc" },
    take: 6,
    include: {
      user: { select: { id: true, username: true, avatarUrl: true } },
      album: { select: { id: true, title: true } },
    },
  })

  if (reviews.length === 0) {
    return (
      <p className="text-[#888] text-center py-8">No reviews yet — be the first!</p>
    )
  }

  return (
    <div className="space-y-4">
      {reviews.map((review) => (
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
  )
}

function TrendingSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <AlbumCardSkeleton key={i} />
      ))}
    </div>
  )
}

function ReviewsSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <ReviewCardSkeleton key={i} />
      ))}
    </div>
  )
}

export default function HomePage() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-10">
      {/* Hero */}
      <section className="text-center mb-14">
        <h1
          className="text-4xl md:text-6xl font-bold text-[#E8B84B] mb-4"
          style={{ fontFamily: "var(--font-playfair), serif" }}
        >
          Tracklist
        </h1>
        <p className="text-[#888] text-lg max-w-xl mx-auto">
          Discover, rate, and review the albums that define your taste. Share your love of music.
        </p>
        <div className="mt-6 flex gap-3 justify-center">
          <Link
            href="/search"
            className="bg-[#E8B84B] text-black font-semibold px-6 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors"
          >
            Search Albums
          </Link>
          <Link
            href="/register"
            className="border border-[rgba(255,255,255,0.2)] text-[#F5F2EB] px-6 py-2.5 rounded-full hover:border-[rgba(255,255,255,0.4)] transition-colors"
          >
            Create Account
          </Link>
        </div>
      </section>

      {/* Trending */}
      <section className="mb-12">
        <h2
          className="text-2xl font-semibold text-[#F5F2EB] mb-6"
          style={{ fontFamily: "var(--font-playfair), serif" }}
        >
          Trending Albums
        </h2>
        <Suspense fallback={<TrendingSkeleton />}>
          <TrendingAlbums />
        </Suspense>
      </section>

      {/* Recent Reviews */}
      <section>
        <h2
          className="text-2xl font-semibold text-[#F5F2EB] mb-6"
          style={{ fontFamily: "var(--font-playfair), serif" }}
        >
          Recent Reviews
        </h2>
        <Suspense fallback={<ReviewsSkeleton />}>
          <RecentReviews />
        </Suspense>
      </section>
    </div>
  )
}
