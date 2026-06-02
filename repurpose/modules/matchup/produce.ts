import fs from 'node:fs';
import path from 'node:path';
import { loadEnv } from '../../lib/env';
import { generateMatchupPlan, type MatchupPlan } from './script';
import { fetchPlayerPhoto } from '../visuals/photos';
import { buildScenes } from '../visuals/scenes';
import { synthesizeBeats } from '../voice/tts';
import { assembleVideo } from '../video/assemble';

export type ProduceResult = {
  plan: MatchupPlan;
  videoPath: string;
  attributions: string[];
};

// One prompt → finished vertical Short. Each stage degrades gracefully:
// missing photos fall back to initials cards; the rest is required.
export async function produceMatchupVideo(
  input: { matchup?: string; plan?: MatchupPlan },
  apiKey?: string,
): Promise<ProduceResult> {
  const env = loadEnv();
  const plan = input.plan ?? (await generateMatchupPlan(input.matchup as string, apiKey));

  const root = path.resolve(env.MEDIA_DIR);
  const jobDir = path.join(root, `matchup-${Date.now()}`);
  fs.mkdirSync(jobDir, { recursive: true });

  // 1. Player photos (best-effort, legal sources w/ attribution).
  const [photoA, photoB] = await Promise.all([
    fetchPlayerPhoto(plan.playerA.wikiTitle || plan.playerA.name, plan.playerA.name, jobDir),
    fetchPlayerPhoto(plan.playerB.wikiTitle || plan.playerB.name, plan.playerB.name, jobDir),
  ]);

  // 2. Narration beats — the single source of truth for both scenes and voice.
  const beats = (plan.narration.length ? plan.narration : [plan.hook, plan.verdict])
    .map((b) => b.trim())
    .filter(Boolean);

  // 3. Render scenes + synthesize voice in parallel.
  const [scenes, clips] = await Promise.all([
    buildScenes(plan, beats, photoA?.localPath ?? null, photoB?.localPath ?? null, jobDir),
    synthesizeBeats(beats, jobDir),
  ]);

  // 4. Stitch into the final vertical Short.
  const videoPath = path.join(jobDir, 'final.mp4');
  await assembleVideo(scenes, clips.map((c) => c.audioPath), videoPath);

  const attributions = [photoA?.attribution, photoB?.attribution].filter(Boolean) as string[];
  return { plan, videoPath, attributions };
}
