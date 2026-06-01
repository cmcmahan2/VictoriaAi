import { drizzle, type LibSQLDatabase } from 'drizzle-orm/libsql';
import { createClient, type Client } from '@libsql/client';
import * as schema from './schema';

// Storage is serverless-friendly via libSQL/Turso (HTTP) and degrades
// gracefully: when no database is configured, getDb() returns null so the
// pipeline still runs and simply skips persistence.
//
//   TURSO_DATABASE_URL  remote libSQL URL (libsql://... or https://...)
//   TURSO_AUTH_TOKEN    auth token for the remote database
//   DB_PATH             local dev fallback, used as file:<path> when no
//                       TURSO_DATABASE_URL is set
const SCHEMA_STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    source_platform TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    local_path TEXT,
    source_caption TEXT,
    transcript TEXT,
    title TEXT,
    description TEXT,
    tags TEXT,
    hashtags TEXT,
    hook TEXT,
    youtube_video_id TEXT,
    error TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
  )`,
];

export type DB = LibSQLDatabase<typeof schema>;

let _db: DB | null = null;
let _schemaReady: Promise<void> | null = null;

function createDbClient(): Client | null {
  const url = process.env.TURSO_DATABASE_URL;
  if (url) {
    return createClient({ url, authToken: process.env.TURSO_AUTH_TOKEN });
  }
  // Local dev fallback: a file-backed libSQL database.
  if (process.env.DB_PATH) {
    return createClient({ url: `file:${process.env.DB_PATH}` });
  }
  return null;
}

async function ensureSchema(client: Client): Promise<void> {
  for (const stmt of SCHEMA_STATEMENTS) {
    await client.execute(stmt);
  }
}

// Returns a Drizzle DB handle, or null when no database is configured.
async function getDb(): Promise<DB | null> {
  if (_db) return _db;

  const client = createDbClient();
  if (!client) return null;

  if (!_schemaReady) {
    _schemaReady = ensureSchema(client);
  }
  await _schemaReady;

  _db = drizzle(client, { schema });
  return _db;
}

export { getDb };
