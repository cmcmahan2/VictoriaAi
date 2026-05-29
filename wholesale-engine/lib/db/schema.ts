import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';

export const searchSessions = sqliteTable('search_sessions', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  market: text('market').notNull(),
  zipCodes: text('zip_codes'),
  filters: text('filters').notNull().default('{}'),
  propertyCount: integer('property_count').notNull().default(0),
  createdAt: integer('created_at').notNull(),
});

export const properties = sqliteTable('properties', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  sessionId: integer('session_id'),
  externalId: text('external_id').notNull(),
  address: text('address').notNull(),
  city: text('city').notNull(),
  state: text('state').notNull(),
  zip: text('zip').notNull(),
  price: real('price').notNull(),
  bedrooms: integer('bedrooms'),
  bathrooms: real('bathrooms'),
  sqft: integer('sqft'),
  yearBuilt: integer('year_built'),
  propertyType: text('property_type'),
  daysOnMarket: integer('days_on_market'),
  priceReductions: integer('price_reductions').notNull().default(0),
  source: text('source').notNull(),
  distressSignals: text('distress_signals').notNull().default('[]'),
  wholesaleScore: integer('wholesale_score'),
  arvEstimate: real('arv_estimate'),
  repairEstimate: real('repair_estimate'),
  mao: real('mao'),
  projectedProfit: real('projected_profit'),
  equitySpread: real('equity_spread'),
  scoreSummary: text('score_summary'),
  scoredAt: integer('scored_at'),
  discoveredAt: integer('discovered_at').notNull(),
});

export const markets = sqliteTable('markets', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull().unique(),
  state: text('state').notNull(),
  medianPrice: real('median_price'),
  avgDaysOnMarket: integer('avg_days_on_market'),
  investorActivity: text('investor_activity'),
  lastUpdated: integer('last_updated').notNull(),
});

export const savedSearches = sqliteTable('saved_searches', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  market: text('market').notNull(),
  zipCodes: text('zip_codes'),
  filters: text('filters').notNull().default('{}'),
  createdAt: integer('created_at').notNull(),
});

export const buyers = sqliteTable('buyers', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  email: text('email'),
  phone: text('phone'),
  markets: text('markets').notNull().default('[]'),
  maxPrice: real('max_price'),
  propertyTypes: text('property_types').notNull().default('[]'),
  notes: text('notes'),
  createdAt: integer('created_at').notNull(),
});

export const alerts = sqliteTable('alerts', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  email: text('email').notNull(),
  market: text('market').notNull(),
  minScore: integer('min_score').notNull().default(75),
  maxPrice: real('max_price'),
  frequency: text('frequency').notNull().default('daily'),
  active: integer('active', { mode: 'boolean' }).notNull().default(true),
  createdAt: integer('created_at').notNull(),
});
