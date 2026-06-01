import fs from 'node:fs';
import OpenAI from 'openai';

// Optional transcription for richer Claude context. The Whisper endpoint
// accepts mp4 directly, so no ffmpeg audio extraction is needed (clips must be
// under the API's 25MB limit — fine for Shorts). When OPENAI_API_KEY is unset,
// callers should skip this and fall back to the source caption.
export async function transcribeAudio(localPath: string): Promise<string> {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error('OPENAI_API_KEY is required for transcription');

  const stat = fs.statSync(localPath);
  const TWENTY_FIVE_MB = 25 * 1024 * 1024;
  if (stat.size > TWENTY_FIVE_MB) {
    throw new Error(
      `Clip is ${(stat.size / 1024 / 1024).toFixed(1)}MB, over Whisper's 25MB limit`,
    );
  }

  const client = new OpenAI({ apiKey: key });
  const res = await client.audio.transcriptions.create({
    file: fs.createReadStream(localPath),
    model: 'whisper-1',
  });
  return res.text;
}
