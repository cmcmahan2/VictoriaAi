// Google OAuth2 helpers for the YouTube Data API v3.
// Step 1 provides the consent-URL builder (pure config, no network) so the
// auth route is wired; token exchange + refresh land with the publish step.
import { loadEnv } from '../../lib/env';

export const YOUTUBE_UPLOAD_SCOPE = 'https://www.googleapis.com/auth/youtube.upload';

// Build the Google consent screen URL the user visits to grant upload access.
export function buildConsentUrl(): string {
  const env = loadEnv();
  if (!env.GOOGLE_CLIENT_ID) {
    throw new Error('GOOGLE_CLIENT_ID is not configured');
  }

  const params = new URLSearchParams({
    client_id: env.GOOGLE_CLIENT_ID,
    redirect_uri: env.GOOGLE_REDIRECT_URI,
    response_type: 'code',
    scope: YOUTUBE_UPLOAD_SCOPE,
    access_type: 'offline', // request a refresh token
    prompt: 'consent',
  });

  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

// Exchange the ?code= for tokens (incl. refresh_token). Implemented in the
// publish step using googleapis' OAuth2 client.
export async function exchangeCodeForTokens(
  _code: string,
): Promise<{ refreshToken: string | null }> {
  throw new Error(
    'exchangeCodeForTokens is a step-1 stub. Token exchange lands with the publish step.',
  );
}
