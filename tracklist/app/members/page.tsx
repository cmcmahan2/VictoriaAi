export const dynamic = "force-dynamic";

import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { UserAvatar } from "@/components/ui/UserAvatar";

export default async function MembersPage() {
  const users = await prisma.user.findMany({
    orderBy: { createdAt: "desc" },
    take: 50,
    include: {
      _count: { select: { ratings: true, reviews: true, followers: true } },
    },
  });

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-[#F5F2EB]" style={{ fontFamily: "Playfair Display, serif" }}>
          Members
        </h1>
        <p className="text-[#888] mt-1">{users.length} members</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {users.map((user) => (
          <Link
            key={user.id}
            href={`/user/${user.username}`}
            className="flex items-center gap-4 bg-[#111] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 hover:border-[rgba(255,255,255,0.2)] transition-colors group"
          >
            <UserAvatar username={user.username} avatarUrl={user.avatarUrl} size={48} />
            <div className="flex-1 min-w-0">
              <p className="text-[#F5F2EB] font-semibold group-hover:text-[#E8B84B] transition-colors">{user.username}</p>
              {user.bio && <p className="text-[#888] text-xs truncate mt-0.5">{user.bio}</p>}
              <div className="flex gap-3 mt-1.5">
                <span className="text-[#555] text-xs">{user._count.ratings} ratings</span>
                <span className="text-[#555] text-xs">{user._count.reviews} reviews</span>
                <span className="text-[#555] text-xs">{user._count.followers} followers</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
