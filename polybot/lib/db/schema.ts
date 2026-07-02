import { integer, real, sqliteTable, text } from "drizzle-orm/sqlite-core";

/**
 * The bet track record — the core asset of the product. Every play the bot
 * finds or places is persisted here so the record is authoritative,
 * survives browser resets, and can back a public, verifiable results page.
 */
export const bets = sqliteTable("bets", {
  id: text("id").primaryKey(),
  marketId: text("market_id").notNull(),
  question: text("question").notNull(),
  type: text("type").notNull(), // binary | multi | logical
  auto: integer("auto", { mode: "boolean" }).notNull().default(false),
  legs: text("legs").notNull(), // JSON: {label, price, shares, cost}[]
  stake: real("stake").notNull(),
  expectedReturn: real("expected_return").notNull(),
  expectedProfit: real("expected_profit").notNull(),
  status: text("status").notNull().default("open"), // open | won | lost
  actualProfit: real("actual_profit"),
  placedAt: integer("placed_at").notNull(), // epoch ms
  resolvedAt: integer("resolved_at"), // epoch ms
  note: text("note"),
});

export type BetRow = typeof bets.$inferSelect;
export type NewBetRow = typeof bets.$inferInsert;
