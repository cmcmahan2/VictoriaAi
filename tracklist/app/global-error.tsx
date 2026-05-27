"use client"

export default function GlobalError({
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  return (
    <html lang="en">
      <body style={{ background: "#0D0D0D", color: "#F5F2EB", fontFamily: "sans-serif" }}>
        <div style={{ maxWidth: 420, margin: "0 auto", padding: "96px 16px", textAlign: "center" }}>
          <p style={{ color: "#E8B84B", fontSize: 36, marginBottom: 16 }}>♪</p>
          <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Something went wrong</h2>
          <p style={{ color: "#888", fontSize: 14, marginBottom: 24 }}>
            We hit a snag. Try again in a moment.
          </p>
          <button
            onClick={() => unstable_retry()}
            style={{ background: "#E8B84B", color: "#000", fontWeight: 600, padding: "10px 24px", borderRadius: 9999, border: "none", cursor: "pointer", fontSize: 14 }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  )
}
