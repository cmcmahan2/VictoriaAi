"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { UserAvatar } from "@/components/ui/UserAvatar";

interface Notification {
  id: string;
  type: string;
  message: string;
  link: string | null;
  read: boolean;
  createdAt: string;
  sender: { username: string; avatarUrl: string | null } | null;
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function typeIcon(type: string) {
  switch (type) {
    case "like": return "♥";
    case "follow": return "✦";
    case "comment": return "💬";
    case "review": return "★";
    default: return "•";
  }
}

export function NotificationBell() {
  const { data: session } = useSession();
  const [notifs, setNotifs] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!session) return;
    fetch("/api/notifications")
      .then((r) => r.json())
      .then((d) => setNotifs(Array.isArray(d) ? d : []));
  }, [session]);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function openPanel() {
    setOpen((v) => !v);
    if (!open) {
      // Mark all as read
      const unread = notifs.filter((n) => !n.read);
      if (unread.length > 0) {
        fetch("/api/notifications", { method: "PATCH" });
        setNotifs((prev) => prev.map((n) => ({ ...n, read: true })));
      }
    }
  }

  if (!session) return null;

  const unreadCount = notifs.filter((n) => !n.read).length;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={openPanel}
        className="relative w-9 h-9 flex items-center justify-center rounded-full hover:bg-[rgba(255,255,255,0.06)] transition-colors"
        aria-label="Notifications"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#888]">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 bg-[#E8B84B] rounded-full text-[9px] font-bold text-black flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 w-80 bg-[#111] border border-[rgba(255,255,255,0.1)] rounded-2xl shadow-2xl z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-[rgba(255,255,255,0.06)]">
            <p className="text-[#F5F2EB] text-sm font-semibold">Notifications</p>
          </div>

          {notifs.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="text-[#555] text-sm">No notifications yet.</p>
              <p className="text-[#444] text-xs mt-1">Follow people and rate albums to get started.</p>
            </div>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {notifs.map((n) => (
                <li key={n.id}>
                  {n.link ? (
                    <Link
                      href={n.link}
                      onClick={() => setOpen(false)}
                      className={`flex items-start gap-3 px-4 py-3 hover:bg-[rgba(255,255,255,0.04)] transition-colors ${!n.read ? "bg-[rgba(232,184,75,0.04)]" : ""}`}
                    >
                      {n.sender ? (
                        <UserAvatar username={n.sender.username} avatarUrl={n.sender.avatarUrl} size={32} />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-[#1a1a1a] flex items-center justify-center text-[#E8B84B] text-xs">
                          {typeIcon(n.type)}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-[#F5F2EB] text-xs leading-snug">{n.message}</p>
                        <p className="text-[#555] text-[10px] mt-0.5">{timeAgo(n.createdAt)}</p>
                      </div>
                      {!n.read && <div className="w-1.5 h-1.5 bg-[#E8B84B] rounded-full mt-1.5 shrink-0" />}
                    </Link>
                  ) : (
                    <div className={`flex items-start gap-3 px-4 py-3 ${!n.read ? "bg-[rgba(232,184,75,0.04)]" : ""}`}>
                      <div className="w-8 h-8 rounded-full bg-[#1a1a1a] flex items-center justify-center text-[#E8B84B] text-xs">
                        {typeIcon(n.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[#F5F2EB] text-xs leading-snug">{n.message}</p>
                        <p className="text-[#555] text-[10px] mt-0.5">{timeAgo(n.createdAt)}</p>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
