"use client";

import { useEffect, useRef } from "react";
import type { Candle } from "@/lib/priceHistory";

export interface TradeMarker {
  time: number; // UNIX seconds
  text: string;
  side: "buy" | "sell";
}

/**
 * TradingView-style candlestick chart using their open-source Lightweight
 * Charts library, with the bot's trades overlaid as markers. The library is
 * imported dynamically inside an effect so it never runs during SSR.
 */
export function ChartPanel({
  candles,
  markers,
  label,
  loading,
}: {
  candles: Candle[];
  markers: TradeMarker[];
  label: string;
  loading?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;
    let disposed = false;
    let chart: any;

    (async () => {
      const lc = await import("lightweight-charts");
      if (disposed || !containerRef.current) return;

      chart = lc.createChart(containerRef.current, {
        layout: { background: { color: "#0f1620" }, textColor: "#7d8ba0" },
        grid: {
          vertLines: { color: "#1c2735" },
          horzLines: { color: "#1c2735" },
        },
        rightPriceScale: { borderColor: "#1c2735" },
        timeScale: { borderColor: "#1c2735", timeVisible: true },
        autoSize: true,
        crosshair: { mode: lc.CrosshairMode.Normal },
      });

      const series = chart.addCandlestickSeries({
        upColor: "#34d399",
        downColor: "#f87171",
        borderUpColor: "#34d399",
        borderDownColor: "#f87171",
        wickUpColor: "#34d399",
        wickDownColor: "#f87171",
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      series.setData(candles as any);

      if (markers.length) {
        series.setMarkers(
          markers
            .slice()
            .sort((a, b) => a.time - b.time)
            .map((m) => ({
              time: m.time as any,
              position: m.side === "buy" ? "belowBar" : "aboveBar",
              color: m.side === "buy" ? "#34d399" : "#fbbf24",
              shape: m.side === "buy" ? "arrowUp" : "arrowDown",
              text: m.text,
            })),
        );
      }

      chart.timeScale().fitContent();
    })();

    return () => {
      disposed = true;
      if (chart) chart.remove();
    };
  }, [candles, markers]);

  return (
    <div className="rounded-xl border border-edge bg-panel">
      <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <div className="text-sm font-medium text-slate-200">{label}</div>
        <div className="text-xs text-muted">{loading ? "loading…" : `${candles.length} bars`}</div>
      </div>
      <div ref={containerRef} className="h-[360px] w-full" />
      {candles.length === 0 && !loading && (
        <div className="px-4 py-8 text-center text-sm text-muted">No price history for this market.</div>
      )}
    </div>
  );
}
