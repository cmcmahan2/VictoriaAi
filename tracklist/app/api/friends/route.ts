import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

const USER_SELECT = {
  id: true,
  username: true,
  displayName: true,
  avatarUrl: true,
  bio: true,
  favoriteGenres: true,
  _count: { select: { ratings: true, reviews: true, followers: true } },
};

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user) return NextResponse.json({ friends: [], following: [], followers: [], suggestions: [] }, { status: 401 });

  const myId = (session.user as { id?: string }).id;
  if (!myId) return NextResponse.json({ friends: [], following: [], followers: [], suggestions: [] });

  // Get following + follower IDs
  const [followingRows, followerRows] = await Promise.all([
    prisma.follow.findMany({ where: { followerId: myId }, select: { followingId: true } }),
    prisma.follow.findMany({ where: { followingId: myId }, select: { followerId: true } }),
  ]);

  const followingIds = new Set(followingRows.map((f) => f.followingId));
  const followerIds = new Set(followerRows.map((f) => f.followerId));

  // Mutual = following each other
  const friendIds = [...followingIds].filter((id) => followerIds.has(id));

  const [followingUsers, followerUsers, friendUsers] = await Promise.all([
    prisma.user.findMany({ where: { id: { in: [...followingIds] } }, select: USER_SELECT }),
    prisma.user.findMany({ where: { id: { in: [...followerIds] } }, select: USER_SELECT }),
    prisma.user.findMany({ where: { id: { in: friendIds } }, select: USER_SELECT }),
  ]);

  const addMeta = (users: typeof followingUsers, isFollowingSet: Set<string>, isMutualSet?: Set<string>) =>
    users.map((u) => ({
      ...u,
      isFollowing: isFollowingSet.has(u.id),
      isMutual: isMutualSet?.has(u.id) ?? false,
    }));

  const mutualSet = new Set(friendIds);

  // Suggestions: find users with similar genre taste who aren't followed yet
  const myGenres = (await prisma.user.findUnique({ where: { id: myId }, select: { favoriteGenres: true } }))?.favoriteGenres ?? [];

  // Also look at genres from highly-rated albums
  const topRatings = await prisma.rating.findMany({
    where: { userId: myId, value: { gte: 4 } },
    include: { album: { select: { genres: true } } },
    take: 50,
  });
  const ratingGenres = topRatings.flatMap((r) => r.album.genres);
  const allMyGenres = [...new Set([...myGenres.map((g) => g.toLowerCase()), ...ratingGenres])];

  let suggestions: typeof followingUsers = [];
  if (allMyGenres.length > 0) {
    const usersWithSimilarGenres = await prisma.user.findMany({
      where: {
        id: { notIn: [myId, ...followingIds] },
        favoriteGenres: { hasSome: allMyGenres },
      },
      select: USER_SELECT,
      take: 20,
    });
    suggestions = usersWithSimilarGenres;
  }

  // Fallback: most active users not followed
  if (suggestions.length < 5) {
    const active = await prisma.user.findMany({
      where: { id: { notIn: [myId, ...followingIds, ...suggestions.map((s) => s.id)] } },
      orderBy: { ratings: { _count: "desc" } },
      select: USER_SELECT,
      take: 10,
    });
    suggestions = [...suggestions, ...active].slice(0, 15);
  }

  return NextResponse.json({
    friends: addMeta(friendUsers, followingIds, mutualSet),
    following: addMeta(followingUsers, followingIds, mutualSet),
    followers: addMeta(followerUsers, followingIds, mutualSet),
    suggestions: suggestions.map((u) => ({ ...u, isFollowing: false, isMutual: false })),
  });
}
