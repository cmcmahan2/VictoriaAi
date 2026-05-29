import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function unixNow(): number {
  return Math.floor(Date.now() / 1000);
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
}

export function formatScore(score: number): string {
  return score.toString();
}

export function scoreColor(score: number): string {
  if (score >= 75) return 'text-green-400 border-green-400/30 bg-green-400/10';
  if (score >= 50) return 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10';
  return 'text-red-400 border-red-400/30 bg-red-400/10';
}

export function scoreLabel(score: number): string {
  if (score >= 75) return 'Hot Deal';
  if (score >= 50) return 'Potential';
  return 'Weak';
}
