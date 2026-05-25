export type Env = {
  ANTHROPIC_API_KEY: string;
  NAMECHEAP_API_USER: string | undefined;
  NAMECHEAP_API_KEY: string | undefined;
  NAMECHEAP_CLIENT_IP: string | undefined;
  GODADDY_API_KEY: string | undefined;
  GODADDY_API_SECRET: string | undefined;
  RESEND_API_KEY: string | undefined;
  NAMEBIO_API_KEY: string | undefined;
  REDDIT_CLIENT_ID: string | undefined;
  REDDIT_CLIENT_SECRET: string | undefined;
  PRODUCT_HUNT_TOKEN: string | undefined;
};

function requireEnv(key: string): string {
  const v = process.env[key];
  if (!v) throw new Error(`Missing required environment variable: ${key}`);
  return v;
}

function optionalEnv(key: string): string | undefined {
  return process.env[key] || undefined;
}

export function loadEnv(): Env {
  return {
    ANTHROPIC_API_KEY: requireEnv('ANTHROPIC_API_KEY'),
    NAMECHEAP_API_USER: optionalEnv('NAMECHEAP_API_USER'),
    NAMECHEAP_API_KEY: optionalEnv('NAMECHEAP_API_KEY'),
    NAMECHEAP_CLIENT_IP: optionalEnv('NAMECHEAP_CLIENT_IP'),
    GODADDY_API_KEY: optionalEnv('GODADDY_API_KEY'),
    GODADDY_API_SECRET: optionalEnv('GODADDY_API_SECRET'),
    RESEND_API_KEY: optionalEnv('RESEND_API_KEY'),
    NAMEBIO_API_KEY: optionalEnv('NAMEBIO_API_KEY'),
    REDDIT_CLIENT_ID: optionalEnv('REDDIT_CLIENT_ID'),
    REDDIT_CLIENT_SECRET: optionalEnv('REDDIT_CLIENT_SECRET'),
    PRODUCT_HUNT_TOKEN: optionalEnv('PRODUCT_HUNT_TOKEN'),
  };
}

export const capabilities = {
  hasNamecheap: () => !!(process.env.NAMECHEAP_API_USER && process.env.NAMECHEAP_API_KEY),
  hasGodaddy: () => !!(process.env.GODADDY_API_KEY && process.env.GODADDY_API_SECRET),
  hasResend: () => !!process.env.RESEND_API_KEY,
  hasNamebio: () => !!process.env.NAMEBIO_API_KEY,
  hasReddit: () => !!(process.env.REDDIT_CLIENT_ID && process.env.REDDIT_CLIENT_SECRET),
  hasProductHunt: () => !!process.env.PRODUCT_HUNT_TOKEN,
};
