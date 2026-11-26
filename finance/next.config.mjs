/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', // static site: host anywhere (Vercel, Netlify, GitHub Pages)
  reactStrictMode: true,
  images: { unoptimized: true },
};
export default nextConfig;
