// drizzle-kit config for the libSQL/Turso driver. Only used by the
// db:generate / db:studio CLI scripts, not by the Next.js build.
const config = {
  schema: './lib/db/schema.ts',
  out: './lib/db/migrations',
  dialect: 'sqlite',
  driver: 'turso',
  dbCredentials: {
    url: process.env.TURSO_DATABASE_URL || `file:${process.env.DB_PATH || './data/flip-engine.db'}`,
    authToken: process.env.TURSO_AUTH_TOKEN,
  },
};

export default config;
