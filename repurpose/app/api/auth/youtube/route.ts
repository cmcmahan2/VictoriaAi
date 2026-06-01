import { NextRequest, NextResponse } from 'next/server';
import { buildConsentUrl, exchangeCodeForTokens } from '../../../../modules/youtube/oauth';
import { capabilities } from '../../../../lib/env';

// GET /api/auth/youtube
//   - no ?code   → redirect the user to Google's consent screen
//   - with ?code → exchange for tokens (token exchange lands with publish step)
export async function GET(req: NextRequest) {
  if (!capabilities.hasYouTubeOAuth()) {
    return NextResponse.json(
      { error: { message: 'Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to enable YouTube auth' } },
      { status: 400 },
    );
  }

  const code = req.nextUrl.searchParams.get('code');

  if (!code) {
    return NextResponse.redirect(buildConsentUrl());
  }

  try {
    const { refreshToken } = await exchangeCodeForTokens(code);
    return NextResponse.json({
      message:
        'Copy this refresh token into YOUTUBE_REFRESH_TOKEN in .env.local to enable unattended uploads.',
      refreshToken,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Token exchange failed';
    return NextResponse.json({ error: { message } }, { status: 501 });
  }
}
