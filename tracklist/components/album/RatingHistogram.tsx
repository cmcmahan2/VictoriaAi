interface RatingHistogramProps {
  distribution: Record<string, number>;
  total: number;
}

export function RatingHistogram({ distribution, total }: RatingHistogramProps) {
  const bars = [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5];

  return (
    <div className="space-y-1">
      {bars.map((star) => {
        const count = distribution[String(star)] ?? 0;
        const pct = total > 0 ? (count / total) * 100 : 0;
        return (
          <div key={star} className="flex items-center gap-2 text-xs">
            <span className="text-[#888] w-6 text-right">{star}</span>
            <div className="flex-1 bg-[#1a1a1a] rounded-full h-2 overflow-hidden">
              <div
                className="h-2 bg-[#E8B84B] rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-[#555] w-8">{count}</span>
          </div>
        );
      })}
    </div>
  );
}
