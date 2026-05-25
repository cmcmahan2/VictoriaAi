import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import * as schema from './schema';
import path from 'path';
import fs from 'fs';

const DB_PATH = process.env.DB_PATH || path.join(process.cwd(), 'data', 'flip-engine.db');

let _db: ReturnType<typeof drizzle> | null = null;

function getDb() {
  if (_db) return _db;

  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const sqlite = new Database(DB_PATH);
  sqlite.pragma('journal_mode = WAL');
  sqlite.pragma('foreign_keys = ON');

  // Auto-create tables if they don't exist (dev convenience)
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS trends (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      velocity TEXT NOT NULL,
      commercial_score INTEGER NOT NULL,
      sources TEXT NOT NULL,
      keywords TEXT NOT NULL,
      discovered_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS hunt_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      niche TEXT NOT NULL,
      trend_ids TEXT NOT NULL,
      total_generated INTEGER NOT NULL DEFAULT 0,
      total_available INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS domain_candidates (
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
    );

    CREATE TABLE IF NOT EXISTS owned_domains (
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
    );

    CREATE TABLE IF NOT EXISTS outreach_prospects (
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
    );

    CREATE TABLE IF NOT EXISTS listings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      owned_domain_id INTEGER NOT NULL,
      marketplace TEXT NOT NULL,
      ask_price REAL NOT NULL,
      minimum_price REAL,
      listed_at INTEGER NOT NULL,
      views INTEGER NOT NULL DEFAULT 0,
      offers INTEGER NOT NULL DEFAULT 0,
      sold_at INTEGER
    );

    CREATE TABLE IF NOT EXISTS purchase_audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      domain TEXT NOT NULL,
      action TEXT NOT NULL,
      cost REAL,
      registrar TEXT,
      reasoning TEXT,
      trend_basis TEXT,
      created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS niche_word_lists (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      niche TEXT NOT NULL,
      words TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );
  `);

  _db = drizzle(sqlite, { schema });
  return _db;
}

export { getDb };
export type DB = ReturnType<typeof drizzle>;
