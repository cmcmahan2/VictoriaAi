"use client";

import { useState } from "react";

const LABELS: Record<number, string> = {
  0.5: "Painful",
  1: "Bad",
  1.5: "Poor",
  2: "Mediocre",
  2.5: "It's fine",
  3: "Good",
  3.5: "Really good",
  4: "Great",
  4.5: "Excellent",
  5: "Perfection",
};

interface StarRatingProps {
  value?: number;
  onChange?: (value: number) => void;
  readonly?: boolean;
  size?: "sm" | "md" | "lg";
}

export function StarRating({ value = 0, onChange, readonly = false, size = "md" }: StarRatingProps) {
  const [hover, setHover] = useState<number | null>(null);

  const sizePx = size === "sm" ? 16 : size === "lg" ? 28 : 22;
  const displayed = hover ?? value;

  const stars = Array.from({ length: 5 }, (_, i) => {
    const full = i + 1;
    const half = i + 0.5;
    const fillFull = displayed >= full;
    const fillHalf = !fillFull && displayed >= half;
    return { full, half, fillFull, fillHalf };
  });

  function handleKey(e: React.KeyboardEvent, v: number) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onChange?.(v);
    }
  }

  return (
    <div
      className="flex items-center gap-0.5"
      role={readonly ? "img" : "group"}
      aria-label={`Rating: ${value} out of 5`}
    >
      {stars.map(({ full, half, fillFull, fillHalf }) => (
        <div key={full} className="relative" style={{ width: sizePx, height: sizePx }}>
          {/* Half star left side */}
          {!readonly && (
            <button
              className="absolute left-0 top-0 w-1/2 h-full z-10 focus:outline-none"
              aria-label={`Rate ${half} stars — ${LABELS[half]}`}
              title={LABELS[half]}
              onMouseEnter={() => setHover(half)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onChange?.(half)}
              onKeyDown={(e) => handleKey(e, half)}
              tabIndex={0}
            />
          )}
          {/* Full star right side */}
          {!readonly && (
            <button
              className="absolute right-0 top-0 w-1/2 h-full z-10 focus:outline-none"
              aria-label={`Rate ${full} stars — ${LABELS[full]}`}
              title={LABELS[full]}
              onMouseEnter={() => setHover(full)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onChange?.(full)}
              onKeyDown={(e) => handleKey(e, full)}
              tabIndex={0}
            />
          )}
          {/* Star SVG */}
          <svg
            width={sizePx}
            height={sizePx}
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id={`half-${full}`} x1="0" x2="1" y1="0" y2="0">
                <stop offset="50%" stopColor="#E8B84B" />
                <stop offset="50%" stopColor="transparent" />
              </linearGradient>
            </defs>
            <path
              d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
              fill={fillFull ? "#E8B84B" : fillHalf ? `url(#half-${full})` : "transparent"}
              stroke="#E8B84B"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      ))}
      {!readonly && hover && (
        <span className="ml-2 text-xs text-[#888]">{LABELS[hover]}</span>
      )}
    </div>
  );
}
