import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';

export const trends = sqliteTable('trends', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  velocity: text('velocity').notNull(), // 'rising' | 'peak' | 'declining'
  commercialScore: integer('commercial_score').notNull(),
  sources: text('sources').notNull(),   // JSON string[]
  keywords: text('keywords').notNull(), // JSON string[]
  discoveredAt: integer('discovered_at').notNull(),
});

export const huntSessions = sqliteTable('hunt_sessions', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  niche: text('niche').notNull(),
  trendIds: text('trend_ids').notNull(), // JSON number[]
  totalGenerated: integer('total_generated').notNull().default(0),
  totalAvailable: integer('total_available').notNull().default(0),
  createdAt: integer('created_at').notNull(),
});

export const domainCandidates = sqliteTable('domain_candidates', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  sessionId: integer('session_id').notNull(),
  domain: text('domain').notNull(),
  tld: text('tld').notNull(),
  generationStrategy: text('generation_strategy').notNull(),
  available: integer('available', { mode: 'boolean' }),       // null = unchecked
  buyPrice: real('buy_price'),
  tmStatus: text('tm_status'),                                // 'CLEAR' | 'CAUTION' | 'BLOCKED'
  score: integer('score'),
  estLow: real('est_low'),
  estMedian: real('est_median'),
  estHigh: real('est_high'),
  annualRenewal: real('annual_renewal'),
  status: text('status').notNull().default('candidate'),     // 'candidate' | 'registered' | 'listed' | 'sold' | 'dropped'
});

export const ownedDomains = sqliteTable('owned_domains', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  domain: text('domain').notNull().unique(),
  registrar: text('registrar').notNull(),
  registeredAt: integer('registered_at').notNull(),
  costBasis: real('cost_basis').notNull(),
  currentValuation: real('current_valuation'),
  renewalDate: integer('renewal_date'),
  renewalCost: real('renewal_cost'),
  listingStatus: text('listing_status').default('unlisted'), // 'unlisted' | 'listed' | 'sold'
  soldAt: integer('sold_at'),
  salePrice: real('sale_price'),
  netProfit: real('net_profit'),
});

export const outreachProspects = sqliteTable('outreach_prospects', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  ownedDomainId: integer('owned_domain_id').notNull(),
  company: text('company').notNull(),
  contactName: text('contact_name'),
  email: text('email'),
  status: text('status').notNull().default('identified'), // 'identified' | 'drafted' | 'sent' | 'opened' | 'replied' | 'negotiating' | 'closed' | 'lost'
  pitchVariant: text('pitch_variant'),                    // 'direct' | 'curious' | 'playful'
  pitchBody: text('pitch_body'),
  sentAt: integer('sent_at'),
  openedAt: integer('opened_at'),
  repliedAt: integer('replied_at'),
  notes: text('notes'),
});

export const listings = sqliteTable('listings', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  ownedDomainId: integer('owned_domain_id').notNull(),
  marketplace: text('marketplace').notNull(),   // 'sedo' | 'afternic' | 'dan' | 'self'
  askPrice: real('ask_price').notNull(),
  minimumPrice: real('minimum_price'),
  listedAt: integer('listed_at').notNull(),
  views: integer('views').notNull().default(0),
  offers: integer('offers').notNull().default(0),
  soldAt: integer('sold_at'),
});

export const purchaseAuditLog = sqliteTable('purchase_audit_log', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  domain: text('domain').notNull(),
  action: text('action').notNull(),  // 'registered' | 'renewal' | 'dropped' | 'sold'
  cost: real('cost'),
  registrar: text('registrar'),
  reasoning: text('reasoning'),
  trendBasis: text('trend_basis'),
  createdAt: integer('created_at').notNull(),
});

export const nicheWordLists = sqliteTable('niche_word_lists', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  niche: text('niche').notNull(),
  words: text('words').notNull(), // JSON string[]
  createdAt: integer('created_at').notNull(),
});
