import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PocketPlan',
  description: 'Personal budget, debt payoff and savings plan — stored only on this device.',
  manifest: './manifest.webmanifest',
  appleWebApp: { capable: true, title: 'PocketPlan', statusBarStyle: 'black-translucent' },
  icons: { icon: './icon.svg', apple: './apple-touch-icon.png' },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  viewportFit: 'cover',
  themeColor: '#0b0d12',
  colorScheme: 'dark',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-CA">
      <body>{children}</body>
    </html>
  );
}
