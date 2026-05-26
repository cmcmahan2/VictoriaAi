"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const res = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });

    if (!res.ok) {
      const data = await res.json();
      setError(data.error ?? "Registration failed.");
      setLoading(false);
      return;
    }

    await signIn("credentials", { email, password, redirect: false });
    router.push("/");
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-3xl font-bold text-[#F5F2EB] mb-2 text-center" style={{ fontFamily: "Playfair Display, serif" }}>
          Join Tracklist
        </h1>
        <p className="text-[#888] text-center mb-8 text-sm">Create an account to start reviewing music</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-[#888] mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              pattern="[a-zA-Z0-9_-]+"
              title="Letters, numbers, underscores, hyphens only"
              className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-4 py-2.5 text-[#F5F2EB] focus:outline-none focus:border-[#E8B84B] transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm text-[#888] mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-4 py-2.5 text-[#F5F2EB] focus:outline-none focus:border-[#E8B84B] transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm text-[#888] mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg px-4 py-2.5 text-[#F5F2EB] focus:outline-none focus:border-[#E8B84B] transition-colors"
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#E8B84B] text-black font-semibold py-2.5 rounded-full hover:bg-[#d4a43a] disabled:opacity-50 transition-colors"
          >
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-[rgba(255,255,255,0.08)]" />
          </div>
          <div className="relative flex justify-center text-xs text-[#555]">
            <span className="bg-[#0D0D0D] px-3">or</span>
          </div>
        </div>

        <button
          onClick={() => signIn("google", { callbackUrl: "/" })}
          className="w-full border border-[rgba(255,255,255,0.1)] text-[#F5F2EB] py-2.5 rounded-full hover:border-[rgba(255,255,255,0.3)] transition-colors flex items-center justify-center gap-2 text-sm"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
            <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>

        <p className="text-center text-sm text-[#888] mt-6">
          Already have an account?{" "}
          <Link href="/login" className="text-[#E8B84B] hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
