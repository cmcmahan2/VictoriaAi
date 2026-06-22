import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function pct(n: number, dp = 2) {
  return `${n.toFixed(dp)}%`;
}

export function usd(n: number, dp = 2) {
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
}

export function cents(n: number) {
  return `${(n * 100).toFixed(1)}¢`;
}
