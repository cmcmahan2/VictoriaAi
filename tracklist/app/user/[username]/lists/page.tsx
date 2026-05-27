export const dynamic = "force-dynamic";

import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { prisma } from "@/lib/prisma";

interface PageProps {
  params: Promise<{ username: string }>;
}

export default async function UserListsPage({ params }: PageProps) {
  const { username } = await params;

  const user = await prisma.user.findUnique({ where: { username } });
  if (!user) notFound();

  const lists = await prisma.list.findMany({
    where: { userId: user.id, isPublic: true },
    orderBy: { createdAt: "desc" },
    include: {
      _count: { select: { entries: true } },
      entries: {
        orderBy: { rank: "asc" },
        take: 5,
      },
    },
  });

  const allAlbumIds = lists.flatMap((l) => l.entries.map((e) => e.albumId));
  const albums = await prisma.album.findMany({
    where: { id: { in: allAlbumIds } },
    select: { id: true, coverUrl: true, title: true },
  });
  const albumMap = new Map(albums.map((a) => [a.id, a]));

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <Link href={`/user/${username}`} className="text-[#888] text-sm hover:text-[#F5F2EB] transition-colors">
            ← {username}
          </Link>
          <h1 className="text-3xl font-bold text-[#F5F2EB] mt-2" style={{ fontFamily: "Playfair Display, serif" }}>
            Lists
          </h1>
        </div>
        <Link
          href="/lists/new"
          className="bg-[#E8B84B] text-black font-semibold px-4 py-2 rounded-full text-sm hover:bg-[#d4a43a] transition-colors"
        >
          + New List
        </Link>
      </div>

      {lists.length === 0 ? (
        <div className="text-center py-16 text-[#888]">
          <p className="mb-4">No lists yet.</p>
          <Link href="/lists/new" className="text-[#E8B84B] hover:underline">Create your first list</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {lists.map((list) => (
            <Link
              key={list.id}
              href={`/lists/${list.id}`}
              className="bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 hover:border-[rgba(255,255,255,0.2)] transition-colors group"
            >
              {/* Cover mosaic */}
              <div className="flex gap-1 mb-3 h-16">
                {list.entries.slice(0, 4).map((entry) => {
                  const album = albumMap.get(entry.albumId);
                  return album?.coverUrl ? (
                    <Image
                      key={entry.id}
                      src={album.coverUrl}
                      alt={album.title ?? ""}
                      width={64}
                      height={64}
                      className="w-16 h-16 object-cover rounded flex-shrink-0"
                    />
                  ) : (
                    <div key={entry.id} className="w-16 h-16 bg-[#1a1a1a] rounded flex-shrink-0 flex items-center justify-center text-[#444]">♪</div>
                  );
                })}
                {list.entries.length < 4 && Array.from({ length: 4 - list.entries.length }).map((_, i) => (
                  <div key={i} className="w-16 h-16 bg-[#1a1a1a] rounded flex-shrink-0" />
                ))}
              </div>
              <h3 className="text-[#F5F2EB] font-semibold group-hover:text-[#E8B84B] transition-colors mb-1">
                {list.title}
              </h3>
              {list.description && (
                <p className="text-[#888] text-xs line-clamp-2 mb-2">{list.description}</p>
              )}
              <p className="text-[#555] text-xs">{list._count.entries} album{list._count.entries !== 1 ? "s" : ""}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
