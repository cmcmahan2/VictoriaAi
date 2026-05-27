"use client"

import { useEffect } from "react"
import Link from "next/link"

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="max-w-md mx-auto px-4 py-24 text-center">
      <p className="text-[#E8B84B] text-4xl mb-4">♪</p>
      <h2 className="text-2xl font-bold text-[#F5F2EB] mb-2" style={{ fontFamily: "var(--font-playfair), serif" }}>
        Something went wrong
      </h2>
      <p className="text-[#888] text-sm mb-6">
        We hit a snag loading this page. Try again in a moment.
      </p>
      <div className="flex items-center justify-center gap-3">
        <button
          onClick={() => unstable_retry()}
          className="bg-[#E8B84B] text-black font-semibold px-6 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors text-sm"
        >
          Try again
        </button>
        <Link
          href="/"
          className="border border-[rgba(255,255,255,0.15)] text-[#888] px-6 py-2.5 rounded-full hover:text-[#F5F2EB] hover:border-[rgba(255,255,255,0.3)] transition-colors text-sm"
        >
          Go home
        </Link>
      </div>
    </div>
  )
}
