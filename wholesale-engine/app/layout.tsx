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
      </body>
    </html>
  );
}
