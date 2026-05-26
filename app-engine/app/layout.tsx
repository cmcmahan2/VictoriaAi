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
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0d1117] text-[#e6edf3] flex overflow-x-hidden">
        <Navigation />
        {/* pt/pb on mobile account for the fixed top header (h-14) and bottom nav (h-16) */}
        <main className="flex-1 min-h-screen overflow-auto pt-14 pb-16 md:pt-0 md:pb-0">
          {children}
        </main>
      </body>
    </html>
  );
}
