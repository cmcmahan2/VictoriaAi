export const dynamic = "force-dynamic";

import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { UserAvatar } from "@/components/ui/UserAvatar";

export default async function WatchlistPage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = await params;
  const session = await getServerSession(authOptions);
  const myId = (session?.user as { id?: string } | undefined)?.id;

  const user = await prisma.user.findUnique({
    where: { username },
    select: { id: true, username: true, avatarUrl: true, displayName: true },
  });

  if (!user) notFound();

  const isMe = myId === user.id;
  if (!isMe) redirect(`/user/${username}`);

  const watchlist = await prisma.watchlist.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: "desc" },
    include: { album: true },
  });

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <div className="flex items-center gap-4 mb-8">
        <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={48} />
        <div>
          <h1 className="text-2xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
            Want to Listen
          </h1>
          <p className="text-[#888] text-sm">{watchlist.length} album{watchlist.length !== 1 ? "s" : ""} saved</p>
        </div>
      </div>

      {watchlist.length === 0 ? (
        <div className="text-center py-16 bg-[#111] rounded-2xl border border-[rgba(255,255,255,0.06)]">
          <p className="text-[#888] text-lg mb-2">Your watchlist is empty.</p>
          <p className="text-[#555] text-sm mb-5">Hit the bookmark button on any album page to save it for later.</p>
          <Link href="/search" className="bg-[#E8B84B] text-black font-semibold px-6 py-2.5 rounded-full hover:bg-[#d4a43a] transition-colors text-sm">
            Browse albums →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {watchlist.map(({ album }) => (
            <Link key={album.id} href={`/album/${album.id}`} className="group">
              <div className="aspect-square rounded-lg overflow-hidden border border-[rgba(255,255,255,0.08)] group-hover:border-[rgba(255,255,255,0.25)] transition-all mb-2">
                {album.coverUrl ? (
                  <Image src={album.coverUrl} alt={album.title} width={200} height={200} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" sizes="200px" />
                ) : (
                  <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center text-[#444] text-4xl">♪</div>
                )}
              </div>
              <p className="text-[#F5F2EB] text-sm font-medium truncate group-hover:text-[#E8B84B] transition-colors">{album.title}</p>
              <p className="text-[#555] text-xs truncate">{album.artistName}</p>
              <p className="text-[#444] text-xs">{album.releaseYear}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
