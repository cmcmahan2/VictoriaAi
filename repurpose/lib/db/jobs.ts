import { eq } from 'drizzle-orm';
import { getDb } from './index';
import { jobs, type Job, type NewJob } from './schema';

// Best-effort persistence helpers. When no database is configured getDb()
// returns null and these become no-ops (createJob returns null), so the
// pipeline keeps working without storage.

export async function createJob(fields: Partial<NewJob> & { sourceUrl: string }): Promise<number | null> {
  const db = await getDb();
  if (!db) return null;
  const now = Date.now();
  const [row] = await db
    .insert(jobs)
    .values({
      status: 'pending',
      ...fields,
      createdAt: now,
      updatedAt: now,
    })
    .returning({ id: jobs.id });
  return row?.id ?? null;
}

export async function updateJob(id: number, fields: Partial<NewJob>): Promise<void> {
  const db = await getDb();
  if (!db) return;
  await db
    .update(jobs)
    .set({ ...fields, updatedAt: Date.now() })
    .where(eq(jobs.id, id));
}

export async function getJob(id: number): Promise<Job | null> {
  const db = await getDb();
  if (!db) return null;
  const [row] = await db.select().from(jobs).where(eq(jobs.id, id)).limit(1);
  return row ?? null;
}
