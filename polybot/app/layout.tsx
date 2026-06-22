import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Polybot — Polymarket Arbitrage Finder",
  description: "Find Polymarket-internal arbitrage and track every bet's P&L.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
