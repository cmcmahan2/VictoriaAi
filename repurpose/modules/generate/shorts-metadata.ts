import Anthropic from '@anthropic-ai/sdk';

// Structured metadata Claude produces for a YouTube Short.
export type ShortsMetadata = {
  title: string;        // <= 100 chars, hook-forward
  description: string;  // first line is the hook; includes a short CTA
  tags: string[];       // 10-15 search tags (no leading '#')
  hashtags: string[];   // 3-5 hashtags, always includes '#Shorts'
  hook: string;         // the opening line / on-screen text idea
};

export type GenerateInput = {
  sourcePlatform?: string | null;
  sourceCaption?: string | null;
  transcript?: string | null;
  // Optional steering from the user (channel niche, tone, etc.)
  channelContext?: string | null;
};

const MODEL = 'claude-sonnet-4-6';

// Long, stable system prompt → prompt-cached (CLAUDE.md convention).
const SYSTEM_PROMPT = `You are a YouTube Shorts growth strategist. You write metadata that maximizes click-through and watch-time for short-form vertical videos repurposed from TikTok, Instagram Reels, and other YouTube Shorts.

Rules:
- Output ONLY valid JSON — no prose, no markdown fences, no explanation.
- "title": <= 100 characters, hook-forward, no clickbait that misrepresents the video. Front-load the most curiosity-inducing words. Title Case or sentence case, your call per the content.
- "description": 2-4 short lines. Line 1 is the strongest hook. Include a light, natural call-to-action (subscribe / follow for more). Do NOT stuff keywords unnaturally.
- "tags": 10-15 specific, relevant search tags as plain strings WITHOUT a leading '#'. Prefer concrete entities and phrases people actually search over generic words.
- "hashtags": 3-5 hashtags WITH a leading '#'. ALWAYS include "#Shorts". Keep them tightly relevant.
- "hook": one punchy line (the opening spoken line or on-screen text) that would stop a scroll in the first 1.5 seconds.
- Never invent facts not supported by the provided caption/transcript. If context is thin, stay generic but compelling rather than fabricating specifics.
- Match the apparent tone/niche of the source content.`;

function buildUserPrompt(input: GenerateInput): string {
  const parts: string[] = [];
  if (input.channelContext) parts.push(`CHANNEL CONTEXT:\n${input.channelContext}`);
  if (input.sourcePlatform) parts.push(`SOURCE PLATFORM: ${input.sourcePlatform}`);
  if (input.sourceCaption) parts.push(`ORIGINAL CAPTION:\n${input.sourceCaption}`);
  if (input.transcript) {
    // Cap transcript to keep token use sane; the first chunk carries the hook.
    parts.push(`TRANSCRIPT (may be truncated):\n${input.transcript.slice(0, 6000)}`);
  }
  if (parts.length === 0) {
    parts.push('No caption or transcript was available for this clip.');
  }

  return `Here is everything known about a short video being repurposed to YouTube Shorts.

${parts.join('\n\n')}

Return a JSON object with this exact schema:
{
  "title": "string",
  "description": "string",
  "tags": ["string", "..."],
  "hashtags": ["#Shorts", "..."],
  "hook": "string"
}`;
}

// Parse Claude's text into ShortsMetadata, tolerant of stray fences and
// mid-response truncation (CLAUDE.md "Structured JSON" + "Truncation safety").
export function parseMetadata(raw: string): ShortsMetadata {
  const match = raw.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('No JSON object found in Claude response');

  let jsonText = match[0];
  let parsed: Partial<ShortsMetadata>;
  try {
    parsed = JSON.parse(jsonText);
  } catch {
    // Best-effort recovery: trim to the last complete property and close it.
    const lastComma = jsonText.lastIndexOf(',');
    if (lastComma > 0) {
      jsonText = jsonText.slice(0, lastComma) + '}';
      parsed = JSON.parse(jsonText);
    } else {
      throw new Error('Claude returned malformed JSON for metadata');
    }
  }

  return {
    title: (parsed.title || '').trim(),
    description: (parsed.description || '').trim(),
    tags: Array.isArray(parsed.tags) ? parsed.tags.map((t) => String(t).replace(/^#/, '').trim()) : [],
    hashtags: Array.isArray(parsed.hashtags) ? parsed.hashtags.map((h) => String(h).trim()) : [],
    hook: (parsed.hook || '').trim(),
  };
}

export async function generateShortsMetadata(
  input: GenerateInput,
  apiKey?: string,
): Promise<ShortsMetadata> {
  const key = apiKey || process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error('ANTHROPIC_API_KEY is required');

  const client = new Anthropic({ apiKey: key });

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 1024,
    system: [
      {
        type: 'text',
        text: SYSTEM_PROMPT,
        cache_control: { type: 'ephemeral' },
      },
    ],
    messages: [{ role: 'user', content: buildUserPrompt(input) }],
  });

  const text = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('');

  const metadata = parseMetadata(text);

  // Guarantee #Shorts is present even if the model forgot.
  if (!metadata.hashtags.some((h) => h.toLowerCase() === '#shorts')) {
    metadata.hashtags.unshift('#Shorts');
  }

  return metadata;
}
