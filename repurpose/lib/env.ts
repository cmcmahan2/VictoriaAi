// Centralized env access + capability flags, mirroring app-engine/lib/env.ts.
// Only ANTHROPIC_API_KEY is strictly required to boot; everything else is
// optional so the pipeline can run partially (e.g. generate metadata without
// YouTube credentials wired up yet).
export type Env = {
  ANTHROPIC_API_KEY: string;
  GOOGLE_CLIENT_ID: string | undefined;
  GOOGLE_CLIENT_SECRET: string | undefined;
  GOOGLE_REDIRECT_URI: string;
  YOUTUBE_REFRESH_TOKEN: string | undefined;
  OPENAI_API_KEY: string | undefined;
  MEDIA_DIR: string;
};

function requireEnv(key: string): string {
  const v = process.env[key];
  if (!v) throw new Error(`Missing required environment variable: ${key}`);
  return v;
}

function optionalEnv(key: string): string | undefined {
  return process.env[key] || undefined;
}

export function loadEnv(): Env {
  return {
    ANTHROPIC_API_KEY: requireEnv('ANTHROPIC_API_KEY'),
    GOOGLE_CLIENT_ID: optionalEnv('GOOGLE_CLIENT_ID'),
    GOOGLE_CLIENT_SECRET: optionalEnv('GOOGLE_CLIENT_SECRET'),
    GOOGLE_REDIRECT_URI:
      optionalEnv('GOOGLE_REDIRECT_URI') || 'http://localhost:3002/api/auth/youtube',
    YOUTUBE_REFRESH_TOKEN: optionalEnv('YOUTUBE_REFRESH_TOKEN'),
    OPENAI_API_KEY: optionalEnv('OPENAI_API_KEY'),
    MEDIA_DIR: optionalEnv('MEDIA_DIR') || './tmp-media',
  };
}

export const capabilities = {
  // Claude is the one hard requirement.
  hasClaude: () => !!process.env.ANTHROPIC_API_KEY,
  // OAuth client configured (enough to start the consent flow).
  hasYouTubeOAuth: () =>
    !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET),
  // Refresh token present → can publish unattended.
  canPublish: () =>
    !!(
      process.env.GOOGLE_CLIENT_ID &&
      process.env.GOOGLE_CLIENT_SECRET &&
      process.env.YOUTUBE_REFRESH_TOKEN
    ),
  // Transcription available for richer Claude context.
  hasTranscription: () => !!process.env.OPENAI_API_KEY,
};
