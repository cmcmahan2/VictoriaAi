import { NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { loadEnv } from '@/lib/env';

export const maxDuration = 30;

const SYSTEM = `You are a domain sales outreach specialist. You write short, direct cold emails that get replies — never spammy, never salesy.

Rules:
- Output ONLY valid JSON. No prose, no markdown fences.
- Generate exactly 4 distinct buyer types.
- Each email body is 3-4 sentences MAX. Short emails get more replies.
- Subject lines are plain and curiosity-inducing — never "Great opportunity!" style.
- "findThem" is a specific, actionable tip: exact LinkedIn search string, a website to browse, or a community to check.
- Reference what the buyer actually does — make it feel personal, not templated.
- The sender signs off as [Your name] — keep it human.`;

const prompt = (domain: string, context: string) => `
Sell the domain: ${domain}
${context ? `Context: ${context}` : ''}

Return JSON with this exact shape:
{
  "targets": [
    {
      "type": "Short buyer label",
      "description": "One sentence on who they are",
      "findThem": "Specific actionable tip to find these buyers",
      "subjects": ["Subject option 1", "Subject option 2"],
      "email": "Hi [Name],\\n\\n<3-4 sentence email body referencing their specific work>\\n\\n[Your name]"
    }
  ]
}`;

export type OutreachTarget = {
  type: string;
  description: string;
  findThem: string;
  subjects: string[];
  email: string;
};

export async function POST(req: Request) {
  try {
    const env = loadEnv();
    const body = (await req.json().catch(() => ({}))) as { domain?: string; context?: string };

    const domain = (body.domain || '').toLowerCase().trim().replace(/^https?:\/\//, '').replace(/\/.*$/, '');
    if (!domain || !domain.includes('.')) {
      return NextResponse.json({ ok: false, error: 'Enter a valid domain name' }, { status: 400 });
    }

    const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
    const response = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      system: SYSTEM,
      messages: [{ role: 'user', content: prompt(domain, body.context || '') }],
    });

    const text = response.content
      .filter((b) => b.type === 'text')
      .map((b) => (b as { text: string }).text)
      .join('');

    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('No valid JSON returned');

    const parsed = JSON.parse(match[0]) as { targets: OutreachTarget[] };

    return NextResponse.json({
      ok: true,
      domain,
      targets: parsed.targets || [],
      usage: { inputTokens: response.usage.input_tokens, outputTokens: response.usage.output_tokens },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/outreach] Error:', message);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
