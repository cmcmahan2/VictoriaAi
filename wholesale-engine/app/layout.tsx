import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Wholesale Engine — Real Estate Deal Finder',
  description: 'AI-powered wholesale real estate deal scoring for US markets',
};

// Runs in <head> before the Next.js runtime registers its own error handlers,
// so our capture-phase listeners fire first and can swallow noise thrown by
// browser extensions (MetaMask, etc.) that would otherwise trip the dev overlay.
const SUPPRESS_EXTENSION_ERRORS = `
(function () {
  function isExtensionNoise(s) {
    if (!s) return false;
    return (
      s.indexOf('MetaMask') !== -1 ||
      s.indexOf('chrome-extension') !== -1 ||
      s.indexOf('moz-extension') !== -1 ||
      s.indexOf('inpage.js') !== -1 ||
      s.indexOf('Failed to connect to MetaMask') !== -1
    );
  }
  window.addEventListener('error', function (e) {
    var msg = (e && e.message) || '';
    var src = (e && e.filename) || '';
    if (isExtensionNoise(msg) || isExtensionNoise(src)) {
      e.stopImmediatePropagation();
      e.preventDefault();
      return false;
    }
  }, true);
  window.addEventListener('unhandledrejection', function (e) {
    var reason = e && e.reason;
    var msg = reason ? (reason.message || String(reason)) : '';
    var stack = reason && reason.stack ? reason.stack : '';
    if (isExtensionNoise(msg) || isExtensionNoise(stack)) {
      e.stopImmediatePropagation();
      e.preventDefault();
      return false;
    }
  }, true);
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <script dangerouslySetInnerHTML={{ __html: SUPPRESS_EXTENSION_ERRORS }} />
      </head>
      <body className="bg-[#0d1117] text-gray-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
