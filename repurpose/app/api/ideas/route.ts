import { NextRequest, NextResponse } from 'next/server';
import { generateMatchupIdeas } from '../../../modules/matchup/ideas';

export const runtime = 'nodejs';

// POST: generate a list of sports-debate matchup ideas for the welcome screen.
// Body: { count?, sportFilter?, theme? }
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json().catch(() => ({}))) as {
      count?: number;
      sportFilter?: string | null;
      theme?: string | null;
    };

    const key = process.env.ANTHROPIC_API_KEY;
    if (!key) {
      return NextResponse.json(
        { error: { message: 'ANTHROPIC_API_KEY is not configured' } },
        { status: 400 },
      );
    }

    const ideas = await generateMatchupIdeas(body, key);
    return NextResponse.json({ ideas });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
