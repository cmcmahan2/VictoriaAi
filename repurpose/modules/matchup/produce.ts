import fs from 'node:fs';
import path from 'node:path';
import { loadEnv } from '../../lib/env';
import { generateMatchupPlan, type MatchupPlan } from './script';
import { fetchPlayerPhoto } from '../visuals/photos';
import { buildScenes, planToRenderScenes } from '../visuals/scenes';
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
  input: { matchup?: string; plan?: MatchupPlan; speed?: number },
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

  // 2. Expand the plan into ordered scenes; captions double as the narration
  //    beats so scenes and voice stay perfectly aligned.
  const renderScenes = planToRenderScenes(plan);
  const beats = renderScenes.map((s) => s.caption.trim());

  // 3. Render scenes + synthesize voice in parallel.
  const [scenes, clips] = await Promise.all([
    buildScenes(plan, renderScenes, photoA?.localPath ?? null, photoB?.localPath ?? null, jobDir),
    synthesizeBeats(beats, jobDir),
  ]);

  // 4. Stitch into the final vertical Short (speed = narration pacing).
  const videoPath = path.join(jobDir, 'final.mp4');
  await assembleVideo(scenes, clips.map((c) => c.audioPath), videoPath, { speed: input.speed });

  const attributions = [photoA?.attribution, photoB?.attribution].filter(Boolean) as string[];
  return { plan, videoPath, attributions };
}
