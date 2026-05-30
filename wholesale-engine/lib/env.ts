export type Env = {
  ANTHROPIC_API_KEY: string | undefined;
  ZILLOW_API_KEY: string | undefined;
  ATTOM_API_KEY: string | undefined;
  RENTCAST_API_KEY: string | undefined;
};

function optionalEnv(key: string): string | undefined {
  return process.env[key] || undefined;
}

export function loadEnv(): Env {
  return {
    ANTHROPIC_API_KEY: optionalEnv('ANTHROPIC_API_KEY'),
    ZILLOW_API_KEY: optionalEnv('ZILLOW_API_KEY'),
    ATTOM_API_KEY: optionalEnv('ATTOM_API_KEY'),
    RENTCAST_API_KEY: optionalEnv('RENTCAST_API_KEY'),
  };
}

export const capabilities = {
  hasClaude: () => !!process.env.ANTHROPIC_API_KEY,
  hasZillow: () => !!process.env.ZILLOW_API_KEY,
  hasAttom: () => !!process.env.ATTOM_API_KEY,
  hasRentcast: () => !!process.env.RENTCAST_API_KEY,
  hasDatabase: () => !!(process.env.TURSO_DATABASE_URL || process.env.DB_PATH),
};
