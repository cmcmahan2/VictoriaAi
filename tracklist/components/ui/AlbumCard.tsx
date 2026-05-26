import Image from "next/image";
import Link from "next/link";
import { StarRating } from "./StarRating";

interface AlbumCardProps {
  id: string;
  title: string;
  artistName: string;
  coverUrl?: string | null;
  avgRating?: number | null;
  ratingCount?: number;
  releaseYear?: number;
}

export function AlbumCard({ id, title, artistName, coverUrl, avgRating, ratingCount, releaseYear }: AlbumCardProps) {
  return (
    <Link href={`/album/${id}`} className="group block">
      <div className="border border-[rgba(255,255,255,0.08)] rounded-lg overflow-hidden bg-[#111] hover:border-[rgba(255,255,255,0.2)] transition-colors">
        <div className="relative aspect-square">
          {coverUrl ? (
            <Image
              src={coverUrl}
              alt={`${title} by ${artistName}`}
              fill
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
              className="object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <div className="w-full h-full bg-[#1a1a1a] flex items-center justify-center">
              <span className="text-[#444] text-4xl">♪</span>
            </div>
          )}
        </div>
        <div className="p-3">
          <p className="text-[#F5F2EB] font-medium text-sm leading-tight truncate">{title}</p>
          <p className="text-[#888] text-xs mt-0.5 truncate">{artistName}{releaseYear ? ` · ${releaseYear}` : ""}</p>
          {avgRating != null && (
            <div className="mt-2 flex items-center gap-2">
              <StarRating value={avgRating} readonly size="sm" />
              {ratingCount != null && (
                <span className="text-[#888] text-xs">{ratingCount.toLocaleString()}</span>
              )}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}

export function AlbumCardSkeleton() {
  return (
    <div className="border border-[rgba(255,255,255,0.08)] rounded-lg overflow-hidden bg-[#111] animate-pulse">
      <div className="aspect-square bg-[#1a1a1a]" />
      <div className="p-3 space-y-2">
        <div className="h-4 bg-[#1a1a1a] rounded w-3/4" />
        <div className="h-3 bg-[#1a1a1a] rounded w-1/2" />
      </div>
    </div>
  );
}
