import { NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { loadEnv } from '@/lib/env';

export const maxDuration = 60;

type ContentBlock = {
  type: 'text';
  text: string;
  cache_control?: { type: 'ephemeral' };
};

type Message = {
  role: 'user' | 'assistant';
  content: string | ContentBlock[];
};

const SYSTEM_PROMPT = `You are Cori, an intelligent AI assistant built into the Victoria domain-investing platform. You help domain investors with:

- Domain name strategy (what to buy, what to avoid, pricing)
- Registrar setup (Namecheap, GoDaddy, Dynadot, etc.) and API access
- Domain valuation and comparables
- Outreach and negotiation tactics for selling domains
- Trend analysis and identifying emerging categories
- Technical setup (WHOIS privacy, DNS, parking pages)
- Platform features (how to use Hunt, Portfolio, Analytics)

Be concise and practical. Give specific, actionable advice. When you don't know something, say so.`;

// Sanitize messages before sending to Claude API.
// Prevents "cache_control cannot be set for empty text blocks" (HTTP 400).
function sanitizeMessages(messages: Message[]): Message[] {
  return messages.map((msg) => {
    if (typeof msg.content === 'string') return msg;

    const blocks = (msg.content as ContentBlock[]).filter((block) => {
      if (block.type === 'text') {
        // Drop empty text blocks — they are illegal when cache_control is set,
        // and useless regardless.
        return block.text && block.text.trim().length > 0;
      }
      return true;
    });

    return { ...msg, content: blocks };
  });
}

// Apply cache_control to the last eligible text block in each message to
// enable prompt caching for long conversations. Guards against empty text.
function applyPromptCaching(messages: Message[]): Message[] {
  return messages.map((msg) => {
    if (typeof msg.content === 'string') return msg;

    const blocks = msg.content as ContentBlock[];
    const lastTextIdx = blocks.reduceRight(
      (found, b, i) => (found === -1 && b.type === 'text' && b.text.trim() ? i : found),
      -1,
    );

    if (lastTextIdx === -1) return msg;

    const updated = blocks.map((b, i) =>
      i === lastTextIdx ? { ...b, cache_control: { type: 'ephemeral' as const } } : b,
    );
    return { ...msg, content: updated };
  });
}

export async function POST(req: Request) {
  try {
    const env = loadEnv();
    const body = (await req.json()) as { messages: Message[] };

    if (!Array.isArray(body.messages) || body.messages.length === 0) {
      return NextResponse.json({ ok: false, error: 'messages array required' }, { status: 400 });
    }

    const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });

    // Sanitize first, then optionally apply caching only to non-empty blocks.
    const safeMessages = applyPromptCaching(sanitizeMessages(body.messages));

    const response = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: safeMessages,
    });

    const text = response.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('');

    return NextResponse.json({ ok: true, reply: text });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    console.error('[api/cori] Error:', message);
    return NextResponse.json({ ok: false, error: `API Error: ${message}` }, { status: 500 });
  }
}
