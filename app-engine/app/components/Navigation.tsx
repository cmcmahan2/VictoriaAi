'use client';

import { usePathname } from 'next/navigation';

const VERSION = 'v1.20';

const links = [
  { href: '/hunt',      label: 'Appraise',   icon: '🔍' },
  { href: '/portfolio', label: 'Portfolio',  icon: '📦' },
  { href: '/outreach',  label: 'Outreach',   icon: '📧' },
  { href: '/analytics', label: 'Analytics',  icon: '📊' },
  { href: '/cori',      label: 'Cori',       icon: '💬' },
  { href: '/settings',  label: 'Settings',   icon: '⚙️' },
];

export function Navigation() {
  const pathname = usePathname();
  const currentLabel = links.find((l) => l.href === pathname)?.label ?? 'Hunt';

  return (
    <>
      {/* ── Desktop sidebar (hidden on mobile) ── */}
      <aside className="hidden md:flex w-52 min-h-screen bg-[#161b22] border-r border-[#30363d] flex-col shrink-0">
        <div className="px-4 py-5 border-b border-[#30363d]">
          <span className="text-sm font-semibold text-[#e6edf3] tracking-wide">FLIP ENGINE</span>
        </div>
        <nav className="flex-1 py-2">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                pathname === l.href
                  ? 'text-[#e6edf3] bg-[#1c2128]'
                  : 'text-[#8b949e] hover:text-[#e6edf3] hover:bg-[#1c2128]'
              }`}
            >
              <span>{l.icon}</span>
              {l.label}
            </a>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-[#30363d]">
          <span className="text-xs text-[#6e7681]">{VERSION}</span>
        </div>
      </aside>

      {/* ── Mobile top header (hidden on desktop) ── */}
      <header className="md:hidden fixed top-0 inset-x-0 z-40 h-14 bg-[#161b22] border-b border-[#30363d] flex items-center px-4 gap-2">
        <span className="text-sm font-semibold text-[#e6edf3] tracking-wide">FLIP ENGINE</span>
        <span className="text-[#6e7681] text-xs">/ {currentLabel}</span>
        <span className="ml-auto text-[10px] text-[#6e7681]">{VERSION}</span>
      </header>

      {/* ── Mobile bottom tab bar (hidden on desktop) ── */}
      {/* paddingBottom: safe-area-inset-bottom keeps content above iPhone home bar */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-[#161b22] border-t border-[#30363d] flex items-stretch"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {links.map((l) => {
          const active = pathname === l.href;
          return (
            <a
              key={l.href}
              href={l.href}
              className={`relative flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[3.5rem] transition-colors ${
                active ? 'text-[#e6edf3]' : 'text-[#6e7681]'
              }`}
            >
              {/* Active green underline at the bottom of the tab */}
              {active && (
                <span className="absolute top-0 inset-x-2 h-0.5 bg-[#238636] rounded-b-full" />
              )}
              <span className="text-xl leading-none">{l.icon}</span>
              <span className="text-[9px] font-medium leading-none tracking-wide mt-0.5">
                {l.label}
              </span>
            </a>
          );
        })}
      </nav>
    </>
  );
}
