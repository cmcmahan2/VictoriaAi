import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Wholesale Engine — Real Estate Deal Finder',
  description: 'AI-powered wholesale real estate deal scoring for US markets',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0d1117] text-gray-100 min-h-screen antialiased">
        {children}
        {/* Suppress browser extension errors (e.g. MetaMask) from surfacing as Next.js overlays */}
        <script dangerouslySetInnerHTML={{ __html: `
          window.addEventListener('error', function(e) {
            if (e && e.message && (
              e.message.includes('MetaMask') ||
              e.message.includes('chrome-extension') ||
              e.message.includes('moz-extension')
            )) { e.stopImmediatePropagation(); e.preventDefault(); }
          }, true);
          window.addEventListener('unhandledrejection', function(e) {
            if (e && e.reason && String(e.reason).includes('MetaMask')) {
              e.preventDefault();
            }
          });
        `}} />
      </body>
    </html>
  );
}
