import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Domain Flip Engine',
  description: 'Profit-optimized domain flipping platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0d1117] text-[#e6edf3] flex">
        <Sidebar />
        <main className="flex-1 min-h-screen overflow-auto">{children}</main>
      </body>
    </html>
  );
}

function Sidebar() {
  const links = [
    { href: '/hunt',     label: 'Hunt',     icon: '🎯' },
    { href: '/search',   label: 'Search',   icon: '🔍' },
    { href: '/portfolio', label: 'Portfolio', icon: '📦' },
    { href: '/outreach', label: 'Outreach', icon: '📧' },
    { href: '/analytics', label: 'Analytics', icon: '📊' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  return (
    <aside className="w-52 min-h-screen bg-[#161b22] border-r border-[#30363d] flex flex-col shrink-0">
      <div className="px-4 py-5 border-b border-[#30363d]">
        <span className="text-sm font-semibold text-[#e6edf3] tracking-wide">FLIP ENGINE</span>
      </div>
      <nav className="flex-1 py-2">
        {links.map((l) => (
          <a
            key={l.href}
            href={l.href}
            className="flex items-center gap-3 px-4 py-2.5 text-sm text-[#8b949e] hover:text-[#e6edf3] hover:bg-[#1c2128] transition-colors"
          >
            <span>{l.icon}</span>
            {l.label}
          </a>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-[#30363d]">
        <span className="text-xs text-[#6e7681]">v0.1.0 — Module 1</span>
      </div>
    </aside>
  );
}
