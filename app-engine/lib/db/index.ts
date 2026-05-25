import { drizzle, type LibSQLDatabase } from 'drizzle-orm/libsql';
import { createClient, type Client } from '@libsql/client';
import * as schema from './schema';

// Storage is serverless-friendly via libSQL/Turso (HTTP) and degrades
// gracefully: when no database is configured, getDb() returns null so the
// trend hunt still runs and simply skips persistence.
//
//   TURSO_DATABASE_URL  remote libSQL URL (libsql://... or https://...)
//   TURSO_AUTH_TOKEN    auth token for the remote database
//   DB_PATH             local dev fallback, used as file:<path> when no
//                       TURSO_DATABASE_URL is set
const SCHEMA_STATEMENTS = [
  `CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    velocity TEXT NOT NULL,
    commercial_score INTEGER NOT NULL,
    sources TEXT NOT NULL,
    keywords TEXT NOT NULL,
    discovered_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS hunt_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    niche TEXT NOT NULL,
    trend_ids TEXT NOT NULL,
    total_generated INTEGER NOT NULL DEFAULT 0,
    total_available INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS domain_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    domain TEXT NOT NULL,
    tld TEXT NOT NULL,
    generation_strategy TEXT NOT NULL,
    available INTEGER,
    buy_price REAL,
    tm_status TEXT,
    score INTEGER,
    est_low REAL,
    est_median REAL,
    est_high REAL,
    annual_renewal REAL,
    status TEXT NOT NULL DEFAULT 'candidate'
  )`,
  `CREATE TABLE IF NOT EXISTS owned_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    registrar TEXT NOT NULL,
    registered_at INTEGER NOT NULL,
    cost_basis REAL NOT NULL,
    current_valuation REAL,
    renewal_date INTEGER,
    renewal_cost REAL,
    listing_status TEXT DEFAULT 'unlisted',
    sold_at INTEGER,
    sale_price REAL,
    net_profit REAL
  )`,
  `CREATE TABLE IF NOT EXISTS outreach_prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owned_domain_id INTEGER NOT NULL,
    company TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'identified',
    pitch_variant TEXT,
    pitch_body TEXT,
    sent_at INTEGER,
    opened_at INTEGER,
    replied_at INTEGER,
    notes TEXT
  )`,
  `CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owned_domain_id INTEGER NOT NULL,
    marketplace TEXT NOT NULL,
    ask_price REAL NOT NULL,
    minimum_price REAL,
    listed_at INTEGER NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    offers INTEGER NOT NULL DEFAULT 0,
    sold_at INTEGER
  )`,
  `CREATE TABLE IF NOT EXISTS purchase_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    action TEXT NOT NULL,
    cost REAL,
    registrar TEXT,
    reasoning TEXT,
    trend_basis TEXT,
    created_at INTEGER NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS niche_word_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    niche TEXT NOT NULL,
    words TEXT NOT NULL,
    created_at INTEGER NOT NULL
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
