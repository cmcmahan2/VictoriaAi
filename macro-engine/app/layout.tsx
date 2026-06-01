import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Macro Engine",
  description: "Personal macro research cockpit — plan, radar, and stock researcher.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
