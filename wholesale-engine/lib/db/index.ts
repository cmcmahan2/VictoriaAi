import { drizzle, type LibSQLDatabase } from 'drizzle-orm/libsql';
import { createClient, type Client } from '@libsql/client';
import * as schema from './schema';

export type DB = LibSQLDatabase<typeof schema>;

let _db: DB | null = null;
let _schemaReady: Promise<void> | null = null;

const SCHEMA_STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS search_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    zip_codes TEXT,
    filters TEXT NOT NULL DEFAULT '{}',
    property_count INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    external_id TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip TEXT NOT NULL,
    price REAL NOT NULL,
    bedrooms INTEGER,
    bathrooms REAL,
    sqft INTEGER,
    year_built INTEGER,
    property_type TEXT,
    days_on_market INTEGER,
    price_reductions INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    distress_signals TEXT NOT NULL DEFAULT '[]',
    wholesale_score INTEGER,
    arv_estimate REAL,
    repair_estimate REAL,
    mao REAL,
    projected_profit REAL,
    equity_spread REAL,
    score_summary TEXT,
    scored_at INTEGER,
    discovered_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    median_price REAL,
    avg_days_on_market INTEGER,
    investor_activity TEXT,
    last_updated INTEGER NOT NULL
  )`,
];

function createDbClient(): Client | null {
  const url = process.env.TURSO_DATABASE_URL;
  if (url) {
    return createClient({ url, authToken: process.env.TURSO_AUTH_TOKEN });
  }
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

export async function getDb(): Promise<DB | null> {
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
