// drizzle-kit 0.21 config format
export default {
  schema: './lib/db/schema.ts',
  out: './drizzle',
  driver: 'turso' as const,
  dbCredentials: {
    url: process.env.TURSO_DATABASE_URL ?? `file:${process.env.DB_PATH ?? './wholesale.db'}`,
    authToken: process.env.TURSO_AUTH_TOKEN ?? '',
  },
};
