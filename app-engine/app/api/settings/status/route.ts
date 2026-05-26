import { NextResponse } from 'next/server';
import { capabilities } from '@/lib/env';

export async function GET() {
  return NextResponse.json({
    godaddy: capabilities.hasGodaddy(),
    namecheap: capabilities.hasNamecheap(),
    resend: capabilities.hasResend(),
    namebio: capabilities.hasNamebio(),
    reddit: capabilities.hasReddit(),
    productHunt: capabilities.hasProductHunt(),
  });
}
