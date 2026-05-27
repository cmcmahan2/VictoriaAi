import Link from "next/link";

interface GenreTagProps {
  genre: string;
  linked?: boolean;
}

export function GenreTag({ genre, linked = true }: GenreTagProps) {
  const label = genre.charAt(0).toUpperCase() + genre.slice(1);
  const cls = "inline-block px-2 py-0.5 rounded-full text-xs border border-[rgba(255,255,255,0.15)] text-[#888] hover:border-[#E8B84B] hover:text-[#E8B84B] transition-colors";

  if (linked) {
    return (
      <Link href={`/genre/${encodeURIComponent(genre)}`} className={cls}>
        {label}
      </Link>
    );
  }

  return (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs border border-[rgba(255,255,255,0.15)] text-[#888]">
      {label}
    </span>
  );
}
