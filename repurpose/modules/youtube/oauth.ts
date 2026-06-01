// Google OAuth2 helpers for the YouTube Data API v3.
import { google } from 'googleapis';
import type { OAuth2Client } from 'google-auth-library';
import { loadEnv } from '../../lib/env';

export const YOUTUBE_UPLOAD_SCOPE = 'https://www.googleapis.com/auth/youtube.upload';

// A bare OAuth2 client configured from env (no credentials set yet).
export function oauthClient(): OAuth2Client {
  const env = loadEnv();
  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET) {
    throw new Error('GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured');
  }
  return new google.auth.OAuth2(
    env.GOOGLE_CLIENT_ID,
    env.GOOGLE_CLIENT_SECRET,
    env.GOOGLE_REDIRECT_URI,
  );
}

// URL of the Google consent screen the user visits to grant upload access.
export function buildConsentUrl(): string {
  return oauthClient().generateAuthUrl({
    access_type: 'offline', // request a refresh token
    prompt: 'consent',
    scope: [YOUTUBE_UPLOAD_SCOPE],
  });
}

// Exchange the ?code= from the consent redirect for tokens. The refresh_token
// is what the user stores in YOUTUBE_REFRESH_TOKEN for unattended uploads.
export async function exchangeCodeForTokens(
  code: string,
): Promise<{ refreshToken: string | null }> {
  const { tokens } = await oauthClient().getToken(code);
  return { refreshToken: tokens.refresh_token ?? null };
}

// An OAuth2 client primed with the stored refresh token, ready to authorize
// API calls (the library refreshes the access token automatically).
export function authorizedClient(): OAuth2Client {
  const env = loadEnv();
  if (!env.YOUTUBE_REFRESH_TOKEN) {
    throw new Error('YOUTUBE_REFRESH_TOKEN is not configured');
  }
  const client = oauthClient();
  client.setCredentials({ refresh_token: env.YOUTUBE_REFRESH_TOKEN });
  return client;
}
