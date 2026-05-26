"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { UserAvatar } from "../ui/UserAvatar";

export function Navbar() {
  const { data: session } = useSession();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  }

  const user = session?.user as { id?: string; name?: string | null; email?: string | null; image?: string | null } | undefined;

  return (
    <nav className="sticky top-0 z-50 border-b border-[rgba(255,255,255,0.08)] bg-[#0D0D0D]/95 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
        <Link href="/" className="text-[#E8B84B] font-bold text-lg tracking-tight shrink-0" style={{ fontFamily: "Playfair Display, serif" }}>
          Tracklist
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-md">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search albums, artists…"
            className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-full px-4 py-1.5 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
          />
        </form>

        <div className="flex items-center gap-4 ml-auto">
          {session ? (
            <div className="relative">
              <button
                onClick={() => setMenuOpen((v) => !v)}
                className="flex items-center gap-2 hover:opacity-80 transition-opacity"
              >
                <UserAvatar username={user?.name ?? "U"} avatarUrl={user?.image} size={32} />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-10 bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-lg py-1 w-44 shadow-xl">
                  <Link href={`/user/${user?.name}`} className="block px-4 py-2 text-sm text-[#F5F2EB] hover:bg-[#222]" onClick={() => setMenuOpen(false)}>
                    Profile
                  </Link>
                  <button
                    onClick={() => { setMenuOpen(false); signOut(); }}
                    className="block w-full text-left px-4 py-2 text-sm text-[#888] hover:bg-[#222]"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Link href="/login" className="text-sm text-[#888] hover:text-[#F5F2EB] transition-colors">
                Log in
              </Link>
              <Link href="/register" className="text-sm bg-[#E8B84B] text-black font-medium px-4 py-1.5 rounded-full hover:bg-[#d4a43a] transition-colors">
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
