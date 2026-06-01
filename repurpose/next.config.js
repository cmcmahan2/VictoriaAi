/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // These pull in native binaries (yt-dlp / ffmpeg) and the Google client;
    // keep them out of the bundle so they run from node_modules at runtime.
    serverComponentsExternalPackages: [
      'youtube-dl-exec',
      'fluent-ffmpeg',
      'googleapis',
    ],
  },
};

module.exports = nextConfig;
