import Image from "next/image";

interface UserAvatarProps {
  username: string;
  avatarUrl?: string | null;
  size?: number;
}

export function UserAvatar({ username, avatarUrl, size = 36 }: UserAvatarProps) {
  const initials = username.slice(0, 2).toUpperCase();

  if (avatarUrl) {
    return (
      <Image
        src={avatarUrl}
        alt={username}
        width={size}
        height={size}
        className="rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <div
      className="rounded-full bg-[#E8B84B] flex items-center justify-center text-black font-bold"
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      aria-label={username}
    >
      {initials}
    </div>
  );
}
