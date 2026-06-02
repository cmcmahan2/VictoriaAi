import { NextRequest, NextResponse } from 'next/server';
import { generateMatchupPlan } from '../../../modules/matchup/script';

export const runtime = 'nodejs';
export const maxDuration = 120;

// POST: turn a matchup ("Jordan vs LeBron") into a full debate plan —
// research, stats, narration, and YouTube metadata.
// Body: { matchup: string }
export async function POST(req: NextRequest) {
  try {
    const { matchup } = (await req.json()) as { matchup?: string };
    if (!matchup?.trim()) {
      return NextResponse.json(
        { error: { message: 'A matchup is required (e.g. "Jordan vs LeBron")' } },
        { status: 400 },
      );
    }

    const key = process.env.ANTHROPIC_API_KEY;
    if (!key) {
      return NextResponse.json(
        { error: { message: 'ANTHROPIC_API_KEY is not configured' } },
        { status: 400 },
      );
    }

    const plan = await generateMatchupPlan(matchup, key);
    return NextResponse.json({ plan });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    return NextResponse.json({ error: { message } }, { status: 500 });
  }
}
