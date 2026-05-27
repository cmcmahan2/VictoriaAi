"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { UserAvatar } from "../ui/UserAvatar";

export function Navbar() {
  const { data: session } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
      setSearchOpen(false);
    }
  }

  const user = session?.user as { id?: string; name?: string | null; email?: string | null; image?: string | null } | undefined;

  const navLinks = [
    { href: "/search", label: "Albums" },
    { href: "/charts", label: "Charts" },
    { href: "/members", label: "Members" },
    { href: "/hot-takes", label: "Hot Takes" },
    ...(session ? [{ href: "/feed", label: "Feed" }] : []),
  ];

  return (
    <>
      <nav className="sticky top-0 z-50 border-b border-[rgba(255,255,255,0.08)] bg-[#0D0D0D]/95 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">
          {/* Logo */}
          <Link href="/" className="shrink-0 flex items-center gap-2">
            <div className="flex gap-1">
              <span className="w-3 h-3 rounded-full bg-[#E8B84B]" />
              <span className="w-3 h-3 rounded-full bg-[#888]" />
              <span className="w-3 h-3 rounded-full bg-[#444]" />
            </div>
            <span className="text-[#F5F2EB] font-bold text-base tracking-tight hidden sm:block" style={{ fontFamily: "Playfair Display, serif" }}>
              Tracklist
            </span>
          </Link>

          {/* Desktop Nav Links */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  pathname?.startsWith(link.href) && link.href !== "/"
                    ? "text-[#F5F2EB]"
                    : "text-[#888] hover:text-[#F5F2EB]"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* Search — desktop */}
          <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-sm ml-2">
            <div className="relative w-full">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-[#555] w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search albums, artists…"
                className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.08)] rounded-full pl-9 pr-4 py-1.5 text-sm text-[#F5F2EB] placeholder-[#444] focus:outline-none focus:border-[#E8B84B] transition-colors"
              />
            </div>
          </form>

          {/* Mobile Search toggle */}
          <button
            className="md:hidden text-[#888] hover:text-[#F5F2EB] transition-colors ml-auto"
            onClick={() => setSearchOpen((v) => !v)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>

          {/* Auth */}
          <div className="flex items-center gap-3 ml-auto md:ml-0 shrink-0">
            {session ? (
              <div className="relative">
                <button
                  onClick={() => setMenuOpen((v) => !v)}
                  className="flex items-center gap-2 hover:opacity-80 transition-opacity"
                >
                  <UserAvatar username={user?.name ?? "U"} avatarUrl={user?.image} size={30} />
                </button>
                {menuOpen && (
                  <div className="absolute right-0 top-10 bg-[#111] border border-[rgba(255,255,255,0.1)] rounded-xl py-1.5 w-48 shadow-2xl">
                    <Link
                      href={`/user/${user?.name}`}
                      className="flex items-center gap-2.5 px-4 py-2 text-sm text-[#F5F2EB] hover:bg-[#1a1a1a] transition-colors"
                      onClick={() => setMenuOpen(false)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                      Profile
                    </Link>
                    <Link
                      href={`/user/${user?.name}/diary`}
                      className="flex items-center gap-2.5 px-4 py-2 text-sm text-[#F5F2EB] hover:bg-[#1a1a1a] transition-colors"
                      onClick={() => setMenuOpen(false)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                      Diary
                    </Link>
                    <Link
                      href={`/user/${user?.name}/lists`}
                      className="flex items-center gap-2.5 px-4 py-2 text-sm text-[#F5F2EB] hover:bg-[#1a1a1a] transition-colors"
                      onClick={() => setMenuOpen(false)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="3" cy="6" r="1"/><circle cx="3" cy="12" r="1"/><circle cx="3" cy="18" r="1"/></svg>
                      Lists
                    </Link>
                    <Link
                      href="/feed"
                      className="flex items-center gap-2.5 px-4 py-2 text-sm text-[#F5F2EB] hover:bg-[#1a1a1a] transition-colors"
                      onClick={() => setMenuOpen(false)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 15a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 4.17h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 11.1a16 16 0 0 0 6 6l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 21.73 18.5"/></svg>
                      Feed
                    </Link>
                    <div className="border-t border-[rgba(255,255,255,0.06)] my-1" />
                    <button
                      onClick={() => { setMenuOpen(false); signOut(); }}
                      className="flex items-center gap-2.5 w-full text-left px-4 py-2 text-sm text-[#888] hover:bg-[#1a1a1a] transition-colors"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <>
                <Link href="/login" className="text-sm text-[#888] hover:text-[#F5F2EB] transition-colors hidden sm:block">
                  Sign in
                </Link>
                <Link href="/register" className="text-sm bg-[#E8B84B] text-black font-semibold px-4 py-1.5 rounded-full hover:bg-[#d4a43a] transition-colors">
                  Create account
                </Link>
              </>
            )}
          </div>
        </div>

        {/* Mobile search bar */}
        {searchOpen && (
          <div className="md:hidden px-4 pb-3">
            <form onSubmit={handleSearch}>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search albums, artists…"
                autoFocus
                className="w-full bg-[#1a1a1a] border border-[rgba(255,255,255,0.1)] rounded-full px-4 py-2 text-sm text-[#F5F2EB] placeholder-[#555] focus:outline-none focus:border-[#E8B84B] transition-colors"
              />
            </form>
          </div>
        )}
      </nav>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden bg-[#0D0D0D]/98 backdrop-blur-sm border-t border-[rgba(255,255,255,0.08)]">
        <div className="flex items-center justify-around h-16 px-2">
          <Link href="/" className={`flex flex-col items-center gap-0.5 px-3 py-2 ${pathname === "/" ? "text-[#E8B84B]" : "text-[#555]"}`}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
            <span className="text-[10px]">Home</span>
          </Link>
          <Link href="/search" className={`flex flex-col items-center gap-0.5 px-3 py-2 ${pathname?.startsWith("/search") ? "text-[#E8B84B]" : "text-[#555]"}`}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <span className="text-[10px]">Albums</span>
          </Link>
          <Link href="/charts" className={`flex flex-col items-center gap-0.5 px-3 py-2 ${pathname?.startsWith("/charts") ? "text-[#E8B84B]" : "text-[#555]"}`}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            <span className="text-[10px]">Charts</span>
          </Link>
          <Link href="/hot-takes" className={`flex flex-col items-center gap-0.5 px-3 py-2 ${pathname?.startsWith("/hot-takes") ? "text-[#E8B84B]" : "text-[#555]"}`}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>
            <span className="text-[10px]">Hot Takes</span>
          </Link>
          {session ? (
            <Link href="/feed" className={`flex flex-col items-center gap-0.5 px-3 py-2 ${pathname?.startsWith("/feed") ? "text-[#E8B84B]" : "text-[#555]"}`}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              <span className="text-[10px]">Feed</span>
            </Link>
          ) : (
            <Link href="/register" className={`flex flex-col items-center gap-0.5 px-3 py-2 ${pathname?.startsWith("/register") ? "text-[#E8B84B]" : "text-[#555]"}`}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <span className="text-[10px]">Join</span>
            </Link>
          )}
          {session && (
            <Link href={`/user/${user?.name}`} className={`flex flex-col items-center gap-0.5 px-3 py-2 ${pathname?.startsWith("/user") ? "text-[#E8B84B]" : "text-[#555]"}`}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
              <span className="text-[10px]">Profile</span>
            </Link>
          )}
        </div>
      </nav>
    </>
  );
}
