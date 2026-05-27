"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const result = await signIn("credentials", { email, password, redirect: false });
    setLoading(false);
    if (result?.error) {
      setError("Invalid email or password.");
    } else {
      router.push("/");
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left — branding */}
      <div className="hidden lg:flex flex-col justify-between w-96 bg-[#111] border-r border-[rgba(255,255,255,0.06)] p-10 shrink-0">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex gap-1">
            <span className="w-3 h-3 rounded-full bg-[#E8B84B]" />
            <span className="w-3 h-3 rounded-full bg-[#888]" />
            <span className="w-3 h-3 rounded-full bg-[#444]" />
          </div>
          <span className="text-[#F5F2EB] font-bold text-lg" style={{ fontFamily: "Playfair Display, serif" }}>Tracklist</span>
        </Link>
        <div>
          <blockquote className="text-[#F5F2EB] text-xl font-light leading-relaxed mb-4" style={{ fontFamily: "Playfair Display, serif" }}>
            &ldquo;Music gives a soul to the universe, wings to the mind, flight to the imagination, and life to everything.&rdquo;
          </blockquote>
          <p className="text-[#555] text-sm">— Plato</p>
        </div>
        <div className="space-y-3">
          {["Rate albums out of 5 stars", "Write and share reviews", "Build a listening diary", "See what friends are loving"].map((f) => (
            <div key={f} className="flex items-center gap-2 text-[#888] text-sm">
              <span className="text-[#E8B84B]">✓</span>
              {f}
            </div>
          ))}
        </div>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <Link href="/" className="flex items-center gap-2 justify-center mb-8 lg:hidden">
            <div className="flex gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-[#E8B84B]" />
              <span className="w-2.5 h-2.5 rounded-full bg-[#888]" />
              <span className="w-2.5 h-2.5 rounded-full bg-[#444]" />
            </div>
            <span className="text-[#F5F2EB] font-bold" style={{ fontFamily: "Playfair Display, serif" }}>Tracklist</span>
          </Link>

          <h1 className="text-2xl font-bold text-[#F5F2EB] mb-1" style={{ fontFamily: "Playfair Display, serif" }}>
            Welcome back
          </h1>
          <p className="text-[#888] text-sm mb-8">Sign in to your account</p>

          {/* Google */}
          <button
            onClick={() => signIn("google", { callbackUrl: "/" })}
            className="w-full border border-[rgba(255,255,255,0.1)] text-[#F5F2EB] py-2.5 rounded-full hover:border-[rgba(255,255,255,0.3)] hover:bg-[rgba(255,255,255,0.03)] transition-all flex items-center justify-center gap-2.5 text-sm mb-4"
          >
            <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
              <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
              <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
              <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
              <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <div className="relative my-5">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[rgba(255,255,255,0.08)]" />
            </div>
            <div className="relative flex justify-center text-xs text-[#555]">
              <span className="bg-[#0D0D0D] px-3">or sign in with email</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-[#888] mb-1.5 uppercase tracking-wide">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-xl px-4 py-3 text-[#F5F2EB] focus:outline-none focus:border-[#E8B84B] transition-colors text-sm"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs text-[#888] uppercase tracking-wide">Password</label>
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-xl px-4 py-3 text-[#F5F2EB] focus:outline-none focus:border-[#E8B84B] transition-colors text-sm"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#E8B84B] text-black font-semibold py-3 rounded-full hover:bg-[#d4a43a] disabled:opacity-50 transition-colors"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="text-center text-sm text-[#888] mt-6">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-[#E8B84B] hover:underline font-medium">Create one free</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
