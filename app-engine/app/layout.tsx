import type { Metadata, Viewport } from 'next';
import './globals.css';
import { Navigation } from './components/Navigation';

export const metadata: Metadata = {
  title: 'Domain Flip Engine',
  description: 'Profit-optimized domain flipping platform',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  viewportFit: 'cover', // enables safe-area-inset-* on iPhone
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0d1117] text-[#e6edf3] flex overflow-x-hidden">
        <Navigation />
        {/* pt/pb on mobile account for the fixed top header (h-14) and bottom nav (h-16) */}
        {/* pt-14 clears fixed top header; pb-20 clears fixed bottom nav + iPhone home bar */}
        <main className="flex-1 min-h-screen overflow-auto pt-14 pb-20 md:pt-0 md:pb-0">
          {children}
        </main>
      </body>
    </html>
  );
}
