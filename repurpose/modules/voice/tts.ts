import fs from 'node:fs';
import path from 'node:path';
import OpenAI from 'openai';
import { loadEnv } from '../../lib/env';

// One narration beat synthesized to an mp3 on disk.
export type VoiceClip = { text: string; audioPath: string };

async function elevenLabsTTS(text: string, outPath: string): Promise<void> {
  const env = loadEnv();
  const res = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${env.ELEVENLABS_VOICE_ID}`,
    {
      method: 'POST',
      headers: {
        'xi-api-key': env.ELEVENLABS_API_KEY as string,
        'Content-Type': 'application/json',
        accept: 'audio/mpeg',
      },
      body: JSON.stringify({
        text,
        model_id: 'eleven_multilingual_v2',
        voice_settings: { stability: 0.5, similarity_boost: 0.75 },
      }),
    },
  );
  if (!res.ok) {
    throw new Error(`ElevenLabs TTS ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
  fs.writeFileSync(outPath, Buffer.from(await res.arrayBuffer()));
}

async function openaiTTS(text: string, outPath: string): Promise<void> {
  const env = loadEnv();
  const client = new OpenAI({ apiKey: env.OPENAI_API_KEY });
  const resp = await client.audio.speech.create({
    model: 'tts-1',
    voice: env.OPENAI_TTS_VOICE as
      | 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer',
    input: text,
  });
  fs.writeFileSync(outPath, Buffer.from(await resp.arrayBuffer()));
}

// Synthesize each narration beat to its own mp3 (so each scene can show for
// exactly its line's duration during assembly).
export async function synthesizeBeats(beats: string[], outDir: string): Promise<VoiceClip[]> {
  const env = loadEnv();
  fs.mkdirSync(outDir, { recursive: true });

  const useEleven = env.TTS_PROVIDER === 'elevenlabs' && !!env.ELEVENLABS_API_KEY;
  const useOpenAI = !useEleven && !!env.OPENAI_API_KEY;
  if (!useEleven && !useOpenAI) {
    throw new Error('No TTS provider configured. Set ELEVENLABS_API_KEY or OPENAI_API_KEY.');
  }

  const clips: VoiceClip[] = [];
  for (let i = 0; i < beats.length; i++) {
    const text = beats[i]?.trim();
    if (!text) continue;
    const audioPath = path.join(outDir, `vo-${String(i).padStart(2, '0')}.mp3`);
    if (useEleven) await elevenLabsTTS(text, audioPath);
    else await openaiTTS(text, audioPath);
    clips.push({ text, audioPath });
  }
  return clips;
}
