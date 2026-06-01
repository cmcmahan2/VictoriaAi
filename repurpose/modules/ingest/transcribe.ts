// Optional transcription for richer Claude context. When OPENAI_API_KEY is
// unset, callers should skip this and fall back to the source caption.
// Stubbed for the step-1 scaffold; the Whisper call lands alongside step 2.

export async function transcribeAudio(_localPath: string): Promise<string> {
  throw new Error(
    'transcribe.ts is a step-1 stub. Whisper transcription is implemented in step 2.',
  );
}
