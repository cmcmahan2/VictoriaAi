// drizzle-kit 0.21 Config types only expose D1 credentials in TypeScript;
// the actual SQLite driver works at runtime with these keys.
const config = {
  schema: './lib/db/schema.ts',
  out: './lib/db/migrations',
  driver: 'better-sqlite',
  dbCredentials: {
    url: process.env.DB_PATH || './data/flip-engine.db',
  },
};

export default config;
