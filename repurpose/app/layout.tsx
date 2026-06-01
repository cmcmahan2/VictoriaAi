import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Repurpose Engine',
  description: 'Paste a Short, auto-generate metadata with Claude, publish to YouTube.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0d1117] text-[#e6edf3]">
        <main className="min-h-screen">{children}</main>
      </body>
    </html>
  );
}
