import { existsSync, mkdirSync } from "fs";
import { dirname } from "path";
import { createClient, type Client } from "@libsql/client";
import { drizzle, type LibSQLDatabase } from "drizzle-orm/libsql";
import * as schema from "./schema";

/**
 * Server-side persistence via libSQL (Turso in prod, local file in dev),
 * mirroring app-engine's setup.
 *
 *   TURSO_DATABASE_URL  remote libSQL URL (libsql://... or https://...)
 *   TURSO_AUTH_TOKEN    auth token for the remote database
 *   DB_PATH             local dev fallback file (default ./data/polybot.db)
 *
 * The schema is created idempotently on first access, so there's no separate
 * migration step to run for local development.
 */
const SCHEMA_STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS bets (
    id TEXT PRIMARY KEY,
    market_id TEXT NOT NULL,
    question TEXT NOT NULL,
    type TEXT NOT NULL,
    auto INTEGER NOT NULL DEFAULT 0,
    legs TEXT NOT NULL,
    stake REAL NOT NULL,
    expected_return REAL NOT NULL,
    expected_profit REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    actual_profit REAL,
    placed_at INTEGER NOT NULL,
    resolved_at INTEGER,
    note TEXT
  )`,
  `CREATE INDEX IF NOT EXISTS idx_bets_placed_at ON bets (placed_at)`,
  `CREATE INDEX IF NOT EXISTS idx_bets_status ON bets (status)`,
];

let dbPromise: Promise<LibSQLDatabase<typeof schema>> | null = null;

function makeClient(): Client {
  const remote = process.env.TURSO_DATABASE_URL;
  if (remote) {
    return createClient({ url: remote, authToken: process.env.TURSO_AUTH_TOKEN });
  }
  const path = process.env.DB_PATH || "./data/polybot.db";
  const dir = dirname(path);
  if (dir && dir !== "." && !existsSync(dir)) mkdirSync(dir, { recursive: true });
  return createClient({ url: `file:${path}` });
}

/** Get the (lazily initialized, schema-ensured) database handle. */
export function getDb(): Promise<LibSQLDatabase<typeof schema>> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const client = makeClient();
      for (const stmt of SCHEMA_STATEMENTS) {
        await client.execute(stmt);
      }
      return drizzle(client, { schema });
    })();
  }
  return dbPromise;
}
