interface GenreTagProps {
  genre: string;
  href?: string;
}

export function GenreTag({ genre, href }: GenreTagProps) {
  const label = genre.charAt(0).toUpperCase() + genre.slice(1);

  if (href) {
    return (
      <a
        href={href}
        className="inline-block px-2 py-0.5 rounded-full text-xs border border-[rgba(255,255,255,0.15)] text-[#888] hover:border-[#E8B84B] hover:text-[#E8B84B] transition-colors"
      >
        {label}
      </a>
    );
  }

  return (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs border border-[rgba(255,255,255,0.15)] text-[#888]">
      {label}
    </span>
  );
}
